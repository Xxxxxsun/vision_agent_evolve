"""Run a VTool-R1 official-prompt tool-use baseline through VLMClient.

This intentionally mirrors the released VTool-R1 tool-use prompt flow while
avoiding the repo's Autogen/Jupyter dependency stack:

- use ChartQAPrompt_mix_orig / TablePrompt_mix_col_row_cot from VTool-R1
- use the released bbox tools from /root/VTool-R1/verl/tooluse/tools.py
- parse one python code block per assistant turn
- execute in a persistent per-case Python namespace
- feed generated artifact images back to the VLM
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vlm_client import ModelSettings, VLMClient
from evolution.benchmark_adapters import get_benchmark_adapter


@dataclass
class OfficialToolUseRecord:
    dataset: str
    split: str
    case_id: str
    expected: str
    answer: str
    correct: bool
    score: float
    turns: int
    tool_turns: int
    image_path: str
    artifact_paths: list[str] = field(default_factory=list)
    raw_response: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VTool-R1 official-prompt tool-use baseline.")
    parser.add_argument("--dataset", choices=["chartqa", "refocus_tablevqa"], required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--subset-id", required=True)
    parser.add_argument("--vtool-root", default="/root/VTool-R1")
    parser.add_argument("--max-reply", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.99)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    runner = OfficialToolUseRunner(
        dataset=args.dataset,
        normalized_data_root=Path(args.normalized_data_root),
        split=args.split,
        subset_id=args.subset_id,
        vtool_root=Path(args.vtool_root),
        max_reply=args.max_reply,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        workers=args.workers,
    )
    summary = runner.run(limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


class OfficialToolUseRunner:
    def __init__(
        self,
        dataset: str,
        normalized_data_root: Path,
        split: str,
        subset_id: str,
        vtool_root: Path,
        max_reply: int,
        max_tokens: int,
        temperature: float,
        top_p: float | None,
        workers: int,
    ) -> None:
        self.dataset = dataset
        self.normalized_data_root = normalized_data_root
        self.split = split
        self.subset_id = subset_id
        self.vtool_root = vtool_root
        self.max_reply = max_reply
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.workers = max(1, workers)
        self.client = VLMClient()
        self.adapter = get_benchmark_adapter(dataset, client=self.client)
        self.output_dir = PROJECT_ROOT / "artifacts" / "structured_benchmarks" / subset_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.output_dir / "per_case_official_tooluse.jsonl"
        self.summary_path = self.output_dir / "summary_official_tooluse.json"
        self.vtool_prompt = load_vtool_prompt_module(vtool_root)
        self.vtool_tools = load_vtool_tools_module(vtool_root)

    def run(self, limit: int) -> dict[str, Any]:
        cases = self.adapter.load_cases(self.normalized_data_root, self.split, limit=limit)
        self.records_path.write_text("", encoding="utf-8")
        indexed_records: list[tuple[int, OfficialToolUseRecord]] = []
        if self.workers == 1:
            for index, case in enumerate(cases, start=1):
                record = self.run_case(case, index=index, total=len(cases))
                indexed_records.append((index, record))
                self._print_progress(index, len(cases), record)
        else:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(self.run_case, case, index, len(cases)): index
                    for index, case in enumerate(cases, start=1)
                }
                for future in as_completed(futures):
                    index = futures[future]
                    record = future.result()
                    indexed_records.append((index, record))
                    self._print_progress(index, len(cases), record)
        records = [record for _, record in sorted(indexed_records, key=lambda item: item[0])]
        with self.records_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        summary = self._summary(records)
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def _print_progress(self, index: int, total: int, record: OfficialToolUseRecord) -> None:
        status = "OK" if record.correct else "FAIL"
        print(f"[{index:03d}/{total:03d}] {status} case={record.case_id} answer={record.answer!r}")

    def run_case(self, case: Any, index: int, total: int) -> OfficialToolUseRecord:
        del total
        case_dir = self.output_dir / "official_tooluse" / f"{index:04d}_{_safe_name(case.case_id)}"
        case_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths: list[str] = []
        raw_response = ""
        error = ""
        answer = ""
        turns = 0
        tool_turns = 0
        try:
            ex = self._case_to_official_ex(case)
            prompt_generator = self._make_prompt_generator()
            initial_prompt = prompt_generator.initial_prompt(ex, n_image=1)
            messages = [
                {"role": "system", "content": self.vtool_prompt.MULTIMODAL_ASSISTANT_MESSAGE},
                {"role": "user", "content": VLMClient.image_message_parts(case.image_path, initial_prompt)},
            ]
            env = self._execution_env(case, case_dir)
            client = VLMClient()

            for turn in range(self.max_reply):
                response, _ = client.chat(
                    messages,
                    ModelSettings(
                        temperature=self.temperature,
                        top_p=self.top_p,
                        max_tokens=self.max_tokens,
                        timeout=180,
                        max_retries=2,
                    ),
                )
                raw_response = response
                turns = turn + 1
                if "TERMINATE" in response:
                    answer = _extract_final_answer(response)
                    if answer:
                        break

                code = _extract_python_code(response)
                messages.append({"role": "assistant", "content": response})
                if not code:
                    answer = _extract_final_answer(response) or _extract_best_effort_answer(response)
                    break

                tool_turns += 1
                exit_code, output, new_artifacts = self._execute_code(code, env, case_dir, tool_turns)
                artifact_paths.extend(new_artifacts)
                feedback = prompt_generator.get_exec_feedback(exit_code, output, new_artifacts)
                if exit_code == 0 and output.strip() and "Output:" not in feedback:
                    feedback += f"\nText output from the executed code:\n{output.strip()}\n"
                messages.append({"role": "user", "content": self._feedback_parts(feedback, new_artifacts, case.image_path)})
            else:
                answer = _extract_final_answer(raw_response) or _extract_best_effort_answer(raw_response)
        except Exception as exc:
            error = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            answer = _extract_final_answer(raw_response) or _extract_best_effort_answer(raw_response)

        if not answer:
            answer = _extract_final_answer(raw_response) or _extract_best_effort_answer(raw_response)
        score = float(self.adapter.score_answer(answer, case))
        return OfficialToolUseRecord(
            dataset=self.dataset,
            split=self.split,
            case_id=case.case_id,
            expected=case.gold_answer,
            answer=answer,
            correct=score >= 1.0,
            score=score,
            turns=turns,
            tool_turns=tool_turns,
            image_path=case.image_path,
            artifact_paths=artifact_paths,
            raw_response=raw_response,
            error=error,
            metadata=dict(case.metadata),
        )

    def _case_to_official_ex(self, case: Any) -> dict[str, Any]:
        metadata = dict(case.metadata)
        if self.dataset == "chartqa":
            return {
                "query": case.prompt,
                "prompt": case.prompt,
                "answer": case.gold_answer,
                "figure_path": case.image_path,
                "x_values": list(metadata.get("x_values", [])),
                "y_values": list(metadata.get("y_values", [])),
            }
        return {
            "query": case.prompt,
            "prompt": case.prompt,
            "answer": case.gold_answer,
            "figure_path": case.image_path,
            "column_headers": list(metadata.get("columns", metadata.get("column_headers", []))),
            "row_starters": list(metadata.get("row_labels", [])),
        }

    def _make_prompt_generator(self) -> Any:
        if self.dataset == "chartqa":
            return self.vtool_prompt.ChartQAPrompt_mix_orig()
        return self.vtool_prompt.TablePrompt_mix_col_row_cot()

    def _execution_env(self, case: Any, case_dir: Path) -> dict[str, Any]:
        metadata = dict(case.metadata)
        env: dict[str, Any] = {
            "__builtins__": __builtins__,
            "Image": Image,
            "json": json,
            "display": self._make_display(case_dir),
            "image_1": Image.open(case.image_path).convert("RGB"),
        }
        for name in dir(self.vtool_tools):
            if name.startswith("focus_on_"):
                env[name] = getattr(self.vtool_tools, name)
        if self.dataset == "chartqa":
            env["x_values_bbox"] = dict(metadata.get("x_values_bbox", {}))
            env["y_values_bbox"] = dict(metadata.get("y_values_bbox", {}))
        else:
            env["columns_bbox"] = dict(metadata.get("columns_bbox", {}))
            env["rows_bbox"] = dict(metadata.get("row_starters", {}))
        env["_displayed_artifacts"] = []
        return env

    def _make_display(self, case_dir: Path):
        def display_image(value: Any) -> None:
            if isinstance(value, Image.Image):
                display_index = len(display_image.artifacts) + 1
                output_path = case_dir / f"display_{display_index}.png"
                value.save(output_path)
                display_image.artifacts.append(str(output_path))
                print(f"<PIL.Image {output_path}>")
            else:
                print(value)

        display_image.artifacts = []
        return display_image

    def _execute_code(self, code: str, env: dict[str, Any], case_dir: Path, tool_turn: int) -> tuple[int, str, list[str]]:
        display_fn = env["display"]
        before = len(display_fn.artifacts)
        stdout = io.StringIO()
        exit_code = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            try:
                exec(compile(code, f"official_tooluse_turn_{tool_turn}.py", "exec"), env, env)
            except Exception:
                exit_code = 1
                traceback.print_exc()
        new_artifacts = list(display_fn.artifacts[before:])
        if not new_artifacts:
            image_candidates = [
                value
                for key, value in sorted(env.items())
                if key.startswith("image_with_") and isinstance(value, Image.Image)
            ]
            if image_candidates:
                output_path = case_dir / f"artifact_turn_{tool_turn}.png"
                image_candidates[-1].save(output_path)
                new_artifacts.append(str(output_path))
        return exit_code, stdout.getvalue(), new_artifacts

    def _feedback_parts(self, feedback: str, artifact_paths: list[str], original_image_path: str) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"type": "text", "text": feedback}]
        for path in artifact_paths[:1]:
            parts.append({"type": "text", "text": "\nTool output image:"})
            parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(path)}})
        parts.append({"type": "text", "text": "\nOriginal image:"})
        parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(original_image_path)}})
        return parts

    def _summary(self, records: list[OfficialToolUseRecord]) -> dict[str, Any]:
        total = len(records)
        score = sum(record.score for record in records) / total if total else 0.0
        correct = sum(1 for record in records if record.correct)
        return {
            "config": {
                "dataset": self.dataset,
                "split": self.split,
                "subset_id": self.subset_id,
                "normalized_data_root": str(self.normalized_data_root),
                "vtool_root": str(self.vtool_root),
                "max_reply": self.max_reply,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "workers": self.workers,
                "vlm_base_url": os.environ.get("VLM_BASE_URL", ""),
                "vlm_model": os.environ.get("VLM_MODEL", ""),
                "vlm_api_key_present": bool(os.environ.get("VLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")),
            },
            "setting": "official_tooluse_prompt",
            "total": total,
            "correct": correct,
            "accuracy": score,
            "tool_usage_rate": (sum(1 for record in records if record.tool_turns > 0) / total) if total else 0.0,
            "avg_tool_turns": (sum(record.tool_turns for record in records) / total) if total else 0.0,
            "records_path": str(self.records_path),
        }


def load_vtool_prompt_module(vtool_root: Path) -> Any:
    prompt_path = vtool_root / "verl" / "tooluse" / "prompt_need.py"
    if not prompt_path.exists():
        raise FileNotFoundError(prompt_path)
    spec = importlib.util.spec_from_file_location("vtool_prompt_need", prompt_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {prompt_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_vtool_tools_module(vtool_root: Path) -> Any:
    tools_path = vtool_root / "verl" / "tooluse" / "tools.py"
    if not tools_path.exists():
        raise FileNotFoundError(tools_path)
    spec = importlib.util.spec_from_file_location("vtool_official_tools", tools_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {tools_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_python_code(response: str) -> str:
    match = re.search(r"```python\s*(.*?)```", response, flags=re.DOTALL | re.IGNORECASE)
    return "" if match is None else match.group(1).strip()


def _extract_final_answer(response: str) -> str:
    for pattern in [
        r"FINAL ANSWER:\s*(.*?)\s*TERMINATE",
        r"ANSWER:\s*(.*?)\s*TERMINATE",
        r"FINAL ANSWER:\s*([^\n\r]+)",
    ]:
        matches = list(re.finditer(pattern, response, flags=re.DOTALL | re.IGNORECASE))
        for match in reversed(matches):
            answer = _clean_answer(match.group(1))
            if _is_valid_extracted_answer(answer):
                return answer
    return ""


def _extract_best_effort_answer(response: str) -> str:
    answer = _extract_final_answer(response)
    if answer:
        return answer
    text = response.strip()
    if "```python" in text:
        before_code = text.split("```python", 1)[0].strip()
        answer = _extract_final_answer(before_code)
        if answer:
            return answer
    return text


def _clean_answer(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().strip("'\"")


def _is_valid_extracted_answer(answer: str) -> bool:
    normalized = answer.strip().lower()
    if not normalized:
        return False
    invalid_fragments = [
        "<final answer>",
        "<your answer>",
        "ends with",
        "please extract",
        "terminate",
    ]
    return not any(fragment in normalized for fragment in invalid_fragments)


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value)[:120]


if __name__ == "__main__":
    main()
