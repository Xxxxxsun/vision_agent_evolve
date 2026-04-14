"""Evaluate a deployed VTool-R1 model via OpenAI-compatible vLLM endpoint.

Replicates the two-rollout eval logic from eval_qwen.py using HTTP API
instead of local vLLM, so the model can run on a separate node.

Usage (chart):
    python scripts/eval_vtoolr1_model.py \
        --data-path /root/VTool-R1/datasets/test_full.parquet \
        --dataset-type chart \
        --output-dir ./artifacts/vtoolr1_model_eval/chart_v1 \
        --base-url http://<vllm-node>:8000/v1 \
        --model VTOOL-R1-32B-F \
        --num-workers 4

Usage (table):
    python scripts/eval_vtoolr1_model.py \
        --data-path /root/VTool-R1/datasets/table_test.parquet \
        --dataset-type table \
        --output-dir ./artifacts/vtoolr1_model_eval/table_v1 \
        --base-url http://<vllm-node>:8000/v1 \
        --model VTOOL-R1-32B-F \
        --num-workers 4
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from PIL import Image
from openai import OpenAI
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import VTool-R1 bbox tools from their repo
_vtool_repo = Path("/root/VTool-R1")
if str(_vtool_repo) not in sys.path:
    sys.path.insert(0, str(_vtool_repo))

from verl.tooluse.tools import (  # noqa: E402
    focus_on_columns_with_mask,
    focus_on_rows_with_mask,
    focus_on_columns_with_draw,
    focus_on_rows_with_draw,
    focus_on_columns_with_highlight,
    focus_on_rows_with_highlight,
    focus_on_x_values_with_mask,
    focus_on_y_values_with_mask,
    focus_on_x_values_with_draw,
    focus_on_y_values_with_draw,
    focus_on_x_values_with_highlight,
    focus_on_y_values_with_highlight,
)

# ── helpers ────────────────────────────────────────────────────────────────────

def _img_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _img_to_data_url(img: Image.Image) -> str:
    return f"data:image/png;base64,{_img_to_b64(img)}"


def _bytes_to_pil(raw) -> Image.Image:
    """Convert stored image bytes (possibly nested list/dict from parquet) to PIL."""
    if isinstance(raw, Image.Image):
        return raw
    if isinstance(raw, bytes):
        return Image.open(BytesIO(raw)).convert("RGB")
    if isinstance(raw, dict) and "bytes" in raw:
        return Image.open(BytesIO(raw["bytes"])).convert("RGB")
    if isinstance(raw, list):
        return _bytes_to_pil(raw[0])
    raise ValueError(f"Cannot convert {type(raw)} to PIL image")


def _parse_code(text: str) -> str | None:
    """Extract python code block from model response. Returns None if not found."""
    start = text.find("```python")
    if start == -1:
        return None
    code = text[start + len("```python"):]
    end = code.find("```")
    if end == -1:
        return None
    code = code[:end].strip()
    if not code:
        return None
    try:
        compile(code, "prog.py", "exec")
        return code
    except SyntaxError:
        return None


def _trim_to_action_end(text: str) -> str:
    last = text.rfind("```")
    if last == -1:
        return text
    preceding = text.rfind("```", 0, last)
    if preceding == -1:
        return text
    return text[:last + 3]


def _extract_final_answer(text: str) -> str:
    matches = re.findall(r"FINAL ANSWER:\s*(.*?)(?=\.\s|\.?\s*TERMINATE|\.?$)", text)
    if matches:
        return matches[-1].strip()
    return ""


def _similarity_score(a: float, b: float) -> float:
    if a == b:
        return 1.0
    if a == 0 or b == 0:
        return 0.0
    return 1.0 - abs(a - b) / max(abs(a), abs(b))


def _score_answer(prediction: str, ground_truth: str) -> float:
    """Replicate compute_score from refocus.py (no GPT-4o, pure similarity)."""
    sub_gts = ground_truth.split("|||")
    if not prediction:
        return 0.0
    expected_answers = len(sub_gts) or 1
    correct_answers = 0.0
    for part in prediction.split("||"):
        part = part.strip()
        candidate_scores = []
        for gt in sub_gts:
            gt = gt.strip()
            try:
                candidate_scores.append(_similarity_score(float(gt), float(part)))
            except ValueError:
                if part.lower() == gt.lower():
                    candidate_scores.append(1.0)
        if candidate_scores:
            correct_answers += max(candidate_scores)
    return correct_answers / expected_answers


# ── tool execution ─────────────────────────────────────────────────────────────

captured_output: Image.Image | None = None


def _display(obj):
    global captured_output
    captured_output = obj


def _get_tool_context(original_image: Image.Image, bbox_mapping: dict) -> dict:
    return {
        "display": _display,
        "image_1": original_image,
        "columns_bbox": bbox_mapping,
        "rows_bbox": bbox_mapping,
        "focus_on_columns_with_mask": focus_on_columns_with_mask,
        "focus_on_rows_with_mask": focus_on_rows_with_mask,
        "focus_on_columns_with_draw": focus_on_columns_with_draw,
        "focus_on_rows_with_draw": focus_on_rows_with_draw,
        "focus_on_columns_with_highlight": focus_on_columns_with_highlight,
        "focus_on_rows_with_highlight": focus_on_rows_with_highlight,
        "focus_on_x_values_with_mask": focus_on_x_values_with_mask,
        "focus_on_y_values_with_mask": focus_on_y_values_with_mask,
        "focus_on_x_values_with_draw": focus_on_x_values_with_draw,
        "focus_on_y_values_with_draw": focus_on_y_values_with_draw,
        "focus_on_x_values_with_highlight": focus_on_x_values_with_highlight,
        "focus_on_y_values_with_highlight": focus_on_y_values_with_highlight,
    }


def _exec_code(code: str, original_image: Image.Image, bbox_mapping: dict) -> Image.Image | None:
    global captured_output
    captured_output = None
    context = _get_tool_context(original_image, bbox_mapping)
    stdout_buf = StringIO()
    try:
        with redirect_stdout(stdout_buf):
            exec(code, context)  # noqa: S102
    except Exception:
        return None
    if isinstance(captured_output, Image.Image):
        return captured_output
    return None


# ── API call helpers ──────────────────────────────────────────────────────────

def _call_api(
    client: OpenAI,
    model: str,
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 1.0,
    retries: int = 5,
) -> str:
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=0.99,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise exc
    return ""


def _first_rollout(
    client: OpenAI,
    model: str,
    prompt_text: str,
    original_image: Image.Image,
) -> str:
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _img_to_data_url(original_image)}},
                {"type": "text", "text": prompt_text},
            ],
        }
    ]
    return _call_api(client, model, messages)


def _second_rollout(
    client: OpenAI,
    model: str,
    prompt_text: str,
    original_image: Image.Image,
    first_response: str,
    edited_image: Image.Image,
) -> str:
    trimmed = _trim_to_action_end(first_response)
    observation = trimmed + "\nOBSERVATION: Execution success. The output is as follows:"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _img_to_data_url(original_image)}},
                {"type": "text", "text": prompt_text},
            ],
        },
        {
            "role": "assistant",
            "content": observation,
        },
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": _img_to_data_url(edited_image)}},
            ],
        },
    ]
    return _call_api(client, model, messages)


# ── per-row eval ───────────────────────────────────────────────────────────────

def _eval_row(row: dict, client: OpenAI, model: str, dataset_type: str) -> dict:
    prompt_text: str = row["prompt"]
    ground_truth: str = str(row["answer"]).strip()
    query: str = str(row.get("query", ""))
    figure_id: str = str(row.get("figure_id", ""))

    # decode image
    raw_img = row.get("images")
    original_image = _bytes_to_pil(raw_img)

    # decode bbox mapping from metadata
    metadata_raw = row.get("metadata", "{}")
    if isinstance(metadata_raw, bytes):
        metadata_raw = metadata_raw.decode()
    try:
        metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
    except Exception:
        metadata = {}

    if dataset_type == "chart":
        chart_type = metadata.get("type", "")
        if chart_type == "v_bar":
            bbox_mapping = metadata.get("x_values_bbox", {})
        else:  # h_bar or unknown
            bbox_mapping = metadata.get("y_values_bbox", {})
    else:  # table
        bbox_mapping = metadata.get("columns_bbox", {})

    # ── first rollout ──
    first_response = _first_rollout(client, model, prompt_text, original_image)

    code = _parse_code(first_response)
    final_response = first_response
    edited_image = None
    code_error = None
    tool_used = False

    if code:
        tool_used = True
        edited_image = _exec_code(code, original_image.copy(), bbox_mapping)
        if edited_image is not None:
            # ── second rollout ──
            final_response = _second_rollout(
                client, model, prompt_text, original_image, first_response, edited_image
            )
        else:
            code_error = "exec failed or display() not called"

    prediction = _extract_final_answer(final_response)
    score = _score_answer(prediction, ground_truth)
    correct = score >= 1.0

    return {
        "figure_id": figure_id,
        "query": query,
        "ground_truth": ground_truth,
        "prediction": prediction,
        "score": score,
        "correct": correct,
        "tool_used": tool_used,
        "tool_exec_success": edited_image is not None,
        "code_error": code_error,
        "first_response": first_response,
        "final_response": final_response,
    }


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Eval VTool-R1 model via vLLM OpenAI-compatible endpoint.")
    parser.add_argument("--data-path", required=True, help="Path to test_full.parquet or table_test.parquet")
    parser.add_argument("--dataset-type", choices=["chart", "table"], default="chart")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-url", required=True, help="vLLM endpoint, e.g. http://node:8000/v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--model", required=True, help="Model name as served by vLLM")
    parser.add_argument("--limit", type=int, default=0, help="Limit rows for quick smoke test")
    parser.add_argument("--num-workers", type=int, default=4)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(args.data_path)
    if args.limit:
        df = df.iloc[: args.limit]
    rows = df.to_dict(orient="records")
    print(f"Loaded {len(rows)} rows from {args.data_path}")

    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    results = []
    per_case_path = output_dir / "per_case.jsonl"

    def _worker(row):
        return _eval_row(row, client, args.model, args.dataset_type)

    with ThreadPoolExecutor(max_workers=args.num_workers) as executor:
        futures = {executor.submit(_worker, row): i for i, row in enumerate(rows)}
        pbar = tqdm(total=len(rows))
        result_map = {}
        for future in as_completed(futures):
            idx = futures[future]
            result = future.result()
            result_map[idx] = result
            pbar.update(1)
            pbar.set_postfix(
                correct=f"{sum(r['correct'] for r in result_map.values())}/{len(result_map)}",
                tool=f"{sum(r['tool_used'] for r in result_map.values())}"
            )
        pbar.close()

    results = [result_map[i] for i in range(len(rows))]

    with open(per_case_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = len(results)
    correct = sum(r["correct"] for r in results)
    tool_used = sum(r["tool_used"] for r in results)
    tool_success = sum(r["tool_exec_success"] for r in results)
    avg_score = sum(r["score"] for r in results) / total if total else 0.0

    summary = {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "avg_score": avg_score,
        "tool_usage_rate": tool_used / total if total else 0.0,
        "tool_exec_success_rate": tool_success / tool_used if tool_used else 0.0,
        "model": args.model,
        "dataset_type": args.dataset_type,
        "data_path": args.data_path,
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))

    print(f"\nAccuracy:  {correct}/{total} = {summary['accuracy']:.4f}")
    print(f"Avg score: {avg_score:.4f}")
    print(f"Tool used: {tool_used}/{total} ({summary['tool_usage_rate']:.2%})")
    print(f"Tool exec: {tool_success}/{tool_used} succeeded")
    print(f"Results:   {output_dir}")


if __name__ == "__main__":
    main()
