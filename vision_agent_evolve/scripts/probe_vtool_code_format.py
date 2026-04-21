"""Probe VTool code-format skill vs generic Python coding skill.

This script compares:
- base model zero-shot on the VTool benchmark prompt
- base model few-shot on the same prompt
- RL model zero-shot on the same prompt
- both models on text-only Python coding tasks

It reuses the aligned VTool protocol helpers from eval_vtool_protocol.py so the
benchmark-side probe matches the repo's current execution path.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from openai import OpenAI

from eval_vtool_protocol import (
    _build_prompt_text,
    _bytes_to_pil,
    _call_api,
    _exec_code as _exec_code_original,
    _extract_final_answer_original_style,
    _first_rollout,
    _img_to_data_url,
    _metadata_dict,
    _parse_code,
    _score_answer,
    _second_rollout_messages,
    _second_rollout,
)

# Inject crop_to_columns / crop_to_rows into the exec context by prepending their
# definitions as source code before the model-generated code block.  This works
# without modifying eval_vtool_protocol.py or the VTool-R1 repo.
_CROP_TOOL_PREAMBLE = '''
def crop_to_columns(image, columns_to_show, all_columns_bounding_boxes, padding=8):
    """Crop image to only the target columns (full table height). Better than mask for counting."""
    if not all_columns_bounding_boxes or not columns_to_show:
        return image
    valid = [c for c in columns_to_show if c in all_columns_bounding_boxes]
    if not valid:
        return image
    bboxes = [all_columns_bounding_boxes[c] for c in valid]
    img_w, img_h = image.size
    x1 = max(0, int(min(b["x1"] for b in bboxes)) - padding)
    x2 = min(img_w, int(max(b["x2"] for b in bboxes)) + padding)
    return image.crop((x1, 0, x2, img_h))

def crop_to_rows(image, rows_to_show, all_rows_bounding_boxes, padding=8):
    """Crop image to header + target rows only. Better than mask for single-row lookup."""
    if not all_rows_bounding_boxes or not rows_to_show:
        return image
    img_w, img_h = image.size
    header_key = list(all_rows_bounding_boxes.keys())[0]
    keys = [header_key] + [r for r in rows_to_show if r in all_rows_bounding_boxes and r != header_key]
    bboxes = [all_rows_bounding_boxes[k] for k in keys]
    y1 = max(0, int(min(b["y1"] for b in bboxes)) - padding)
    y2 = min(img_h, int(max(b["y2"] for b in bboxes)) + padding)
    return image.crop((0, y1, img_w, y2))
'''


def _exec_code(code: str, original_image, metadata, dataset_type):
    """Wrap _exec_code_original to prepend crop tool definitions."""
    return _exec_code_original(_CROP_TOOL_PREAMBLE + "\n" + code, original_image, metadata, dataset_type)


VTOOL_REPO = Path("/root/VTool-R1")
DEFAULT_JINJA = VTOOL_REPO / "examples" / "format_prompt" / "chartQA.jinja"
DEFAULT_MANUAL_TEACHER_BANK = Path("/root/vision_agent_evolve_rl/vision_agent_evolve/config/manual_vtool_table_teacher_bank.json")

GENERIC_CODING_TASKS: list[dict[str, str]] = [
    {
        "name": "sum_even",
        "prompt": "Write Python only in one ```python``` block. Implement function sum_even(nums) that returns the sum of even integers in nums.",
        "tests": "assert sum_even([1,2,3,4,5,6]) == 12\nassert sum_even([]) == 0\nassert sum_even([1,3,5]) == 0",
    },
    {
        "name": "dedupe_pipe",
        "prompt": 'Write Python only in one ```python``` block. Implement function dedupe_pipe(text) that splits by "||", strips whitespace, drops empty items, preserves first occurrence order, and joins back with "||".',
        "tests": 'assert dedupe_pipe("A|| B ||A|| ||C") == "A||B||C"\nassert dedupe_pipe("") == ""',
    },
    {
        "name": "year_diff",
        "prompt": 'Write Python only in one ```python``` block. Implement function year_diff(a, b) where a and b are year strings like "1999" and it returns the absolute difference as int.',
        "tests": 'assert year_diff("1999", "2004") == 5\nassert year_diff("2010", "2010") == 0',
    },
    {
        "name": "max_key",
        "prompt": 'Write Python only in one ```python``` block. Implement function max_key(d) that returns the key with the largest numeric value in dict d. If d is empty return None.',
        "tests": 'assert max_key({"a": 2, "b": 5, "c": 1}) == "b"\nassert max_key({}) is None',
    },
    {
        "name": "normalize_num",
        "prompt": 'Write Python only in one ```python``` block. Implement function normalize_num(text) that removes commas and dollar signs from a numeric string and returns float.',
        "tests": 'assert normalize_num("$1,234.50") == 1234.50\nassert normalize_num("98") == 98.0',
    },
    {
        "name": "top_two",
        "prompt": "Write Python only in one ```python``` block. Implement function top_two(nums) that returns the two largest unique integers in descending order as a list.",
        "tests": "assert top_two([5,1,5,3,2]) == [5,3]\nassert top_two([4]) == [4]\nassert top_two([]) == []",
    },
    {
        "name": "parse_ratio",
        "prompt": 'Write Python only in one ```python``` block. Implement function parse_ratio(text) for strings like "12/30" and return the float ratio.',
        "tests": 'assert abs(parse_ratio("12/30") - 0.4) < 1e-9\nassert abs(parse_ratio("3/4") - 0.75) < 1e-9',
    },
    {
        "name": "count_truthy",
        "prompt": "Write Python only in one ```python``` block. Implement function count_truthy(items) that counts truthy values in the iterable.",
        "tests": "assert count_truthy([0, 1, '', 'x', None, True]) == 3\nassert count_truthy([]) == 0",
    },
    {
        "name": "pick_after_year",
        "prompt": "Write Python only in one ```python``` block. Implement function pick_after_year(rows, threshold) where rows is a list of dicts with keys year and value. Return values whose integer year is greater than threshold.",
        "tests": "rows=[{'year':'2001','value':'A'},{'year':'1999','value':'B'},{'year':'2007','value':'C'}]\nassert pick_after_year(rows, 2000) == ['A', 'C']",
    },
    {
        "name": "safe_int",
        "prompt": "Write Python only in one ```python``` block. Implement function safe_int(text, default=0) that returns int(text) if possible, otherwise default.",
        "tests": "assert safe_int('42') == 42\nassert safe_int('x') == 0\nassert safe_int('', default=-1) == -1",
    },
]


def _clear_proxy_env() -> None:
    for key in ["HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy"]:
        os.environ.pop(key, None)


def _load_rows(data_path: Path, limit: int) -> pd.DataFrame:
    df = pd.read_parquet(data_path)
    if limit > 0:
        return df.head(limit).copy()
    return df.copy()


def _make_client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key)


def _build_user_message(prompt_text: str, image) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": _img_to_data_url(image)}},
            {"type": "text", "text": prompt_text},
        ],
    }


def _load_probe_results(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _infer_question_family(query: str) -> str:
    q = query.lower()
    if any(word in q for word in ["how many", "sum", "total", "number of", "count"]):
        return "count_or_total"
    if any(word in q for word in ["same", "more than", "less than", "higher", "lower", "difference", "compare"]):
        return "comparison"
    if any(word in q for word in ["largest", "highest", "lowest", "smallest", "most", "least"]):
        return "extrema"
    return "generic"


def _family_answer_hint(query: str) -> str:
    q = query.lower()
    if "return 0 or 1 only" in q or "true or false" in q:
        return "This is a binary task. Final answer must be exactly 0 or 1."
    if any(word in q for word in ["how many", "sum", "total", "number of", "count"]):
        return "This is a counting/aggregation task. Count carefully after isolating the relevant subset."
    if any(word in q for word in ["same", "more than", "less than", "higher", "lower", "difference", "compare"]):
        return "This is a comparison task. Identify the exact rows/columns before comparing."
    return ""


def _infer_code_pattern(first_response: str) -> str:
    if "crop_to_columns" in first_response and "crop_to_rows" in first_response:
        return "crop_columns_then_rows"
    if "crop_to_columns" in first_response:
        return "crop_columns"
    if "crop_to_rows" in first_response:
        return "crop_rows"
    if "focus_on_columns_with_draw" in first_response and "focus_on_rows_with_draw" in first_response:
        return "columns_then_rows_draw"
    if "focus_on_rows_with_draw" in first_response and "focus_on_columns_with_draw" in first_response:
        return "rows_then_columns_draw"
    if "focus_on_columns_with_draw" in first_response:
        return "columns_draw"
    if "focus_on_rows_with_draw" in first_response:
        return "rows_draw"
    if "focus_on_columns_with_highlight" in first_response:
        return "columns_highlight"
    if "focus_on_rows_with_highlight" in first_response:
        return "rows_highlight"
    if "focus_on_columns_with_mask" in first_response:
        return "columns_mask"
    if "focus_on_rows_with_mask" in first_response:
        return "rows_mask"
    return "other"


def _build_example_pool(
    rows_df: pd.DataFrame,
    dataset_type: str,
    jinja_raw: str,
    results_path: Path,
) -> list[dict[str, Any]]:
    by_figure_id = {str(row["figure_id"]): row for _, row in rows_df.iterrows()}
    pool: list[dict[str, Any]] = []
    for item in _load_probe_results(results_path):
        if item.get("tool_exec_branch") != "tool_success_second_rollout":
            continue
        if not item.get("correct"):
            continue
        first_response = str(item.get("first_rollout_response", "")).strip()
        figure_id = str(item.get("figure_id", ""))
        source_row = by_figure_id.get(figure_id)
        if not first_response or source_row is None:
            continue
        source_row_dict = source_row.to_dict()
        metadata = _metadata_dict(source_row_dict)
        prompt_text = _build_prompt_text(source_row_dict, metadata, dataset_type, jinja_raw)
        query = str(source_row_dict.get("query", ""))
        pool.append(
            {
                "figure_id": figure_id,
                "query": query,
                "query_tokens": _tokenize(query),
                "family": _infer_question_family(query),
                "pattern": _infer_code_pattern(first_response),
                "prompt_text": prompt_text,
                "assistant_text": first_response,
            }
        )
    return pool


def _build_fixed_teacher_examples(
    *,
    rows_df: pd.DataFrame,
    dataset_type: str,
    jinja_raw: str,
    results_path: Path,
    teacher_bank_path: Path,
) -> list[dict[str, Any]]:
    by_figure_id = {str(row["figure_id"]): row for _, row in rows_df.iterrows()}
    result_by_figure_id = {str(item["figure_id"]): item for item in _load_probe_results(results_path)}
    fixed_examples: list[dict[str, Any]] = []
    for item in _load_json(teacher_bank_path):
        figure_id = str(item["figure_id"])
        source_row = by_figure_id.get(figure_id)
        source_result = result_by_figure_id.get(figure_id)
        if source_row is None:
            continue
        source_row_dict = source_row.to_dict()
        metadata = _metadata_dict(source_row_dict)
        prompt_text = _build_prompt_text(source_row_dict, metadata, dataset_type, jinja_raw)
        assistant_text = str(item.get("assistant_text", "")).strip()
        if not assistant_text and source_result is not None:
            assistant_text = str(source_result.get("first_rollout_response") or source_result.get("second_rollout_response") or "").strip()
        if not assistant_text:
            continue
        fixed_examples.append(
            {
                "figure_id": figure_id,
                "family": str(item.get("family", "")),
                "pattern": str(item.get("pattern", "")),
                "description": str(item.get("description", "")),
                "prompt_text": prompt_text,
                "assistant_text": assistant_text,
            }
        )
    return fixed_examples


def _score_example(target_query: str, candidate: dict[str, Any]) -> tuple[float, float, float]:
    target_tokens = _tokenize(target_query)
    overlap = len(target_tokens & candidate["query_tokens"])
    family_match = 1.0 if _infer_question_family(target_query) == candidate["family"] else 0.0
    count_bias = 1.0 if _infer_question_family(target_query) == "count_or_total" and candidate["pattern"] in {"columns_then_rows_draw", "rows_draw", "columns_draw"} else 0.0
    return (family_match, overlap, count_bias)


def _select_fewshot_examples(
    *,
    target_query: str,
    target_figure_id: str,
    example_pool: list[dict[str, Any]],
    count: int,
) -> list[dict[str, str]]:
    if count <= 0:
        return []
    ranked = sorted(
        (item for item in example_pool if item["figure_id"] != target_figure_id),
        key=lambda item: _score_example(target_query, item),
        reverse=True,
    )
    selected: list[dict[str, str]] = []
    used_patterns: set[str] = set()
    for item in ranked:
        if len(selected) >= count:
            break
        # Prefer a bit of template diversity so all demos do not collapse to one exact pattern.
        if item["pattern"] in used_patterns and len(ranked) > count * 2:
            continue
        used_patterns.add(item["pattern"])
        selected.append({"prompt_text": item["prompt_text"], "assistant_text": item["assistant_text"]})
    if len(selected) < count:
        for item in ranked:
            if len(selected) >= count:
                break
            candidate = {"prompt_text": item["prompt_text"], "assistant_text": item["assistant_text"]}
            if candidate not in selected:
                selected.append(candidate)
    return selected


def _benchmark_messages(prompt_text: str, original_image, examples: list[dict[str, str]]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for example in examples:
        messages.append({"role": "user", "content": [{"type": "text", "text": example["prompt_text"]}]})
        messages.append({"role": "assistant", "content": [{"type": "text", "text": example["assistant_text"]}]})
    messages.append(_build_user_message(prompt_text, original_image))
    return messages


def _manual_skill_system_prompt(family: str, query: str) -> str:
    family_hint = _family_answer_hint(query)
    return (
        "Follow the demonstrated VTool table protocol exactly. "
        "Use at most one ACTION 0 python block. "
        "Only use labels that appear verbatim in rows_bbox or columns_bbox. "
        "Never use cell values, dates, numbers, countries, cities, or answer strings as row/column labels unless they are exact bbox keys. "
        "Always finish with FINAL ANSWER."
        + (f" Additional task hint: {family_hint}" if family_hint else "")
    )


def _strategy_system_prompt(strategy: str, family: str, query: str) -> str:
    base = (
        "Follow the demonstrated VTool table protocol exactly. "
        "Use at most one ACTION 0 python block. "
        "Only use labels that appear verbatim in rows_bbox or columns_bbox. "
        "Never use cell values, dates, numbers, countries, cities, or answer strings as row/column labels unless they are exact bbox keys. "
        "Always finish with FINAL ANSWER."
    )
    family_hint = _family_answer_hint(query)
    if strategy == "baseline_retrieval":
        return base
    if strategy == "label_guard":
        return (
            base
            + " Before writing code, internally verify every label argument against bbox keys. "
            + "If a candidate label is not an exact bbox key, do not use it."
        )
    if strategy == "count_comparison_specialized":
        extra = (
            " For count/comparison tasks, first isolate the relevant columns, then isolate rows using existing row labels only, then count or compare."
            if family in {"count_or_total", "comparison"}
            else ""
        )
        return base + extra + (" " + family_hint if family_hint else "")
    if strategy == "plan_then_action":
        return (
            base
            + " Internally plan the needed columns, rows, and operation before writing ACTION 0. "
            + "Do not reveal the plan as separate actions."
            + (" " + family_hint if family_hint else "")
        )
    if strategy == "answer_guard":
        return base + " After tool execution, re-read the focused image and verify the final answer against the observation before terminating."
    if strategy == "combined_best":
        return (
            base
            + " Internally plan columns, rows, and operation before writing ACTION 0. "
            + "For count/comparison tasks, isolate the relevant subset before answering. "
            + "After tool execution, verify the final answer against the focused image."
            + (" " + family_hint if family_hint else "")
        )
    if strategy == "manual_skill_only":
        return _manual_skill_system_prompt(family, query)
    if strategy == "manual_skill_plus_teacher_examples":
        return _manual_skill_system_prompt(family, query) + " Follow the fixed teacher demonstrations as examples of the preferred tool-usage style."
    return base


def _fixed_teacher_examples_for_family(
    *,
    family: str,
    teacher_examples: list[dict[str, Any]],
    target_figure_id: str,
) -> list[dict[str, str]]:
    if not teacher_examples:
        return []
    if family == "count_or_total":
        preferred_order = ["count_or_total", "extrema"]
    elif family == "comparison":
        preferred_order = ["comparison"]
    elif family == "generic":
        preferred_order = ["generic", "extrema"]
    else:
        preferred_order = ["extrema", "generic"]
    selected: list[dict[str, str]] = []
    used_patterns: set[str] = set()
    for preferred_family in preferred_order:
        for item in teacher_examples:
            if item["figure_id"] == target_figure_id:
                continue
            if item["family"] != preferred_family:
                continue
            if item["pattern"] in used_patterns:
                continue
            used_patterns.add(item["pattern"])
            selected.append({"prompt_text": item["prompt_text"], "assistant_text": item["assistant_text"]})
            if len(selected) >= 2:
                break
        if len(selected) >= 2:
            break
    return selected[:2]


def _build_messages_for_strategy(
    *,
    prompt_text: str,
    original_image,
    examples: list[dict[str, str]],
    strategy: str,
    family: str,
    query: str,
) -> list[dict[str, Any]]:
    messages = _benchmark_messages(prompt_text, original_image, examples)
    system_text = _strategy_system_prompt(strategy, family, query)
    return [{"role": "system", "content": [{"type": "text", "text": system_text}]}] + messages


def _call_second_rollout_with_strategy(
    *,
    client: OpenAI,
    model: str,
    strategy: str,
    family: str,
    query: str,
    prompt_text: str,
    original_image,
    first_response: str,
    edited_image,
    exec_error: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,
    retries: int,
) -> tuple[str, str]:
    if strategy not in {"answer_guard", "combined_best", "manual_skill_only", "manual_skill_plus_teacher_examples"}:
        return _second_rollout(
            client,
            argparse.Namespace(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                timeout=timeout,
                retries=retries,
            ),
            prompt_text,
            original_image,
            first_response,
            edited_image,
            exec_error,
        )
    if edited_image is not None:
        assistant_response = (
            first_response[: first_response.rfind("```") + 3]
            + "\nOBSERVATION: Execution success. The output is as follows:"
            + "\n<the image outputs of the code is added as the second image>"
        )
        branch = "tool_success_second_rollout"
    else:
        assistant_response = first_response[: first_response.rfind("```") + 3] + "\nOBSERVATION: Execution failed. No output is available."
        branch = "tool_fail_second_rollout"
    messages = _second_rollout_messages(prompt_text, original_image, edited_image, assistant_response)
    if strategy in {"manual_skill_only", "manual_skill_plus_teacher_examples"}:
        system_text = (
            _strategy_system_prompt(strategy, family, query)
            + " Continue from the observation in the VTool style. "
            + "Use the focused image as the primary evidence. "
            + "Treat the answer stated in THOUGHT 0 / ANSWER as a candidate answer to verify, not something to replace casually. "
            + "If the focused image supports that candidate answer, keep it. Change it only when the focused image clearly contradicts it. "
            + "For count questions, list the qualifying visible entries before FINAL ANSWER. "
            + "For comparison or difference questions, name the compared entries and compute the value before FINAL ANSWER. "
            + "Do not restate unrelated table content."
        )
    else:
        system_text = _strategy_system_prompt(strategy, family, query) + " Verify the final answer carefully from the observation."
    response = _call_api(
        client,
        model,
        [{"role": "system", "content": [{"type": "text", "text": system_text}]}] + messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        timeout=timeout,
        retries=retries,
    )
    return response, branch


def _string_literals(code: str) -> list[str]:
    if not code:
        return []
    try:
        tree = ast.parse(code)
    except Exception:
        return []
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


def _illegal_labels(code: str, metadata: dict[str, Any], dataset_type: str) -> list[str]:
    if dataset_type != "table" or not code:
        return []
    valid = set()
    for key in metadata.get("columns_bbox", {}).keys():
        valid.add(str(key))
    for key in metadata.get("row_starters", {}).keys():
        valid.add(str(key))
    illegal: list[str] = []
    for value in _string_literals(code):
        if value not in valid:
            illegal.append(value)
    return illegal


def _failure_bucket(result: dict[str, Any]) -> str:
    error_lines = (result.get("code_error") or "").splitlines()
    error = error_lines[0] if error_lines else ""
    query = str(result.get("query", "")).lower()
    prediction = str(result.get("prediction", "")).strip()
    if result.get("correct"):
        return "correct"
    if error:
        if "KeyError" in error:
            return "tool_keyerror"
        if "display() did not receive a PIL image" in error:
            return "tool_no_image"
        return "other_tool_error"
    if not result.get("tool_exec_success"):
        return "tool_failed_no_error"
    if ("return 0 or 1 only" in query or "true or false" in query) and prediction not in {"0", "1"}:
        return "binary_format_or_reasoning"
    return "exec_success_but_wrong_answer"


def _family_breakdown(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    families = {}
    for family in sorted({row["question_family"] for row in results}):
        subset = [row for row in results if row["question_family"] == family]
        total = len(subset)
        families[family] = {
            "n": total,
            "exact_accuracy": sum(1 for row in subset if row["correct"]) / total if total else 0.0,
            "avg_score": sum(row["score"] for row in subset) / total if total else 0.0,
            "tool_exec_success_rate": sum(1 for row in subset if row["tool_exec_success"]) / total if total else 0.0,
        }
    return families


def _run_benchmark_variant(
    *,
    name: str,
    client: OpenAI,
    model: str,
    rows_df: pd.DataFrame,
    dataset_type: str,
    jinja_raw: str,
    example_pool: list[dict[str, Any]],
    fixed_teacher_examples: list[dict[str, Any]],
    fewshot_count: int,
    prompt_strategy: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,
    retries: int,
    verbose: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    total_rows = len(rows_df)
    if verbose:
        print(f"[benchmark] start variant={name} rows={total_rows}", flush=True)
    for row_index, (_, row) in enumerate(rows_df.iterrows(), start=1):
        row_dict = row.to_dict()
        metadata = _metadata_dict(row_dict)
        original_image = _bytes_to_pil(row_dict.get("images"))
        prompt_text = _build_prompt_text(row_dict, metadata, dataset_type, jinja_raw)
        family = _infer_question_family(str(row_dict.get("query", "")))
        if prompt_strategy == "manual_skill_plus_teacher_examples":
            examples = _fixed_teacher_examples_for_family(
                family=family,
                teacher_examples=fixed_teacher_examples,
                target_figure_id=str(row_dict.get("figure_id", "")),
            )
        elif prompt_strategy == "manual_skill_only":
            examples = []
        else:
            examples = _select_fewshot_examples(
                target_query=str(row_dict.get("query", "")),
                target_figure_id=str(row_dict.get("figure_id", "")),
                example_pool=example_pool,
                count=fewshot_count,
            )

        if not examples and prompt_strategy == "baseline_retrieval":
            first_response = _first_rollout(
                client,
                argparse.Namespace(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    timeout=timeout,
                    retries=retries,
                ),
                prompt_text,
                original_image,
            )
        else:
            first_response = _call_api(
                client,
                model,
                _build_messages_for_strategy(
                    prompt_text=prompt_text,
                    original_image=original_image,
                    examples=examples,
                    strategy=prompt_strategy,
                    family=family,
                    query=str(row_dict.get("query", "")),
                ),
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                timeout=timeout,
                retries=retries,
            )

        parsed = _parse_code(first_response)
        edited_image = None
        exec_error = parsed["error"]
        if parsed["status"] == "ok":
            edited_image, _, exec_error = _exec_code(parsed["code"], original_image, metadata, dataset_type)

        model_response = first_response
        second_rollout_used = False
        if edited_image is not None:
            second_rollout_used = True
            model_response, _ = _call_second_rollout_with_strategy(
                client=client,
                model=model,
                strategy=prompt_strategy,
                family=family,
                query=str(row_dict.get("query", "")),
                prompt_text=prompt_text,
                original_image=original_image,
                first_response=first_response,
                edited_image=edited_image,
                exec_error=exec_error,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                timeout=timeout,
                retries=retries,
            )

        prediction = _extract_final_answer_original_style(model_response)
        ground_truth = str(row_dict.get("answer", "")).strip()
        score = _score_answer(prediction, ground_truth)
        illegal_labels = _illegal_labels(parsed["code"], metadata, dataset_type)
        results.append(
            {
                "row_index": row_index,
                "figure_id": str(row_dict.get("figure_id", "")),
                "query": str(row_dict.get("query", "")),
                "ground_truth": ground_truth,
                "prediction": prediction,
                "score": score,
                "correct": score >= 1.0,
                "question_family": family,
                "parse_status": parsed["status"],
                "tool_exec_success": edited_image is not None,
                "second_rollout_used": second_rollout_used,
                "has_codeblock": "```python" in first_response,
                "has_action0": "ACTION 0" in first_response,
                "has_final_answer_marker": "FINAL ANSWER:" in model_response,
                "illegal_labels": illegal_labels,
                "illegal_label_count": len(illegal_labels),
                "code_error": exec_error,
            }
        )
        results[-1]["failure_bucket"] = _failure_bucket(results[-1])
        if verbose:
            print(
                f"[benchmark] variant={name} row={row_index}/{total_rows} "
                f"figure_id={results[-1]['figure_id']} parse={results[-1]['parse_status']} "
                f"exec={results[-1]['tool_exec_success']} correct={results[-1]['correct']}",
                flush=True,
            )

    total = len(results)
    return {
        "name": name,
        "summary": {
            "n": total,
            "codeblock_rate": sum(1 for row in results if row["has_codeblock"]) / total if total else 0.0,
            "action0_rate": sum(1 for row in results if row["has_action0"]) / total if total else 0.0,
            "parse_ok_rate": sum(1 for row in results if row["parse_status"] == "ok") / total if total else 0.0,
            "tool_exec_success_rate": sum(1 for row in results if row["tool_exec_success"]) / total if total else 0.0,
            "final_answer_marker_rate": sum(1 for row in results if row["has_final_answer_marker"]) / total if total else 0.0,
            "exact_accuracy": sum(1 for row in results if row["correct"]) / total if total else 0.0,
            "avg_score": sum(row["score"] for row in results) / total if total else 0.0,
            "illegal_label_rate": sum(1 for row in results if row["illegal_label_count"] > 0) / total if total else 0.0,
            "tool_keyerror_rate": sum(1 for row in results if row["failure_bucket"] == "tool_keyerror") / total if total else 0.0,
            "exec_success_but_wrong_answer_rate": sum(1 for row in results if row["failure_bucket"] == "exec_success_but_wrong_answer") / total if total else 0.0,
            "family_breakdown": _family_breakdown(results),
        },
        "rows": results,
    }


def _extract_python_block(text: str) -> str:
    marker = "```python"
    start = text.find(marker)
    if start == -1:
        return ""
    body = text[start + len(marker) :]
    end = body.find("```")
    if end == -1:
        return ""
    return body[:end].strip()


def _run_generic_coding_variant(
    *,
    name: str,
    client: OpenAI,
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    timeout: int,
    retries: int,
    verbose: bool,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    total_tasks = len(GENERIC_CODING_TASKS)
    if verbose:
        print(f"[generic] start variant={name} tasks={total_tasks}", flush=True)
    for task in GENERIC_CODING_TASKS:
        response = _call_api(
            client,
            model,
            [{"role": "user", "content": [{"type": "text", "text": task["prompt"]}]}],
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            timeout=timeout,
            retries=retries,
        )
        code = _extract_python_block(response)
        status = "no_code"
        error = ""
        if code:
            namespace: dict[str, Any] = {}
            try:
                with redirect_stdout(StringIO()):
                    exec(code, namespace, namespace)  # noqa: S102
                    exec(task["tests"], namespace, namespace)  # noqa: S102
                status = "pass"
            except Exception as exc:
                status = "fail"
                error = f"{type(exc).__name__}: {exc}"
        results.append({"name": task["name"], "status": status, "error": error})
        if verbose:
            print(f"[generic] variant={name} task={task['name']} status={status}", flush=True)

    total = len(results)
    return {
        "name": name,
        "summary": {
            "n": total,
            "pass_at_1": sum(1 for row in results if row["status"] == "pass") / total if total else 0.0,
            "no_code_rate": sum(1 for row in results if row["status"] == "no_code") / total if total else 0.0,
            "fail_rate": sum(1 for row in results if row["status"] == "fail") / total if total else 0.0,
        },
        "rows": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe VTool code-format skill vs generic coding skill.")
    parser.add_argument("--data-path", required=True, help="Benchmark parquet path, e.g. /root/VTool-R1/vtool-r1-datasets/table_test.parquet")
    parser.add_argument("--dataset-type", choices=["table", "chart"], default="table")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--base-url-base", default="http://33.3.175.26:8000/v1")
    parser.add_argument("--model-base", default="Qwen2.5-VL-7B-Instruct")
    parser.add_argument("--base-url-rl", default="http://33.3.175.26:8234/v1")
    parser.add_argument("--model-rl", default="VTool-Qwen2.5-7B")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--benchmark-limit", type=int, default=50)
    parser.add_argument("--fewshot-counts", nargs="*", type=int, default=[2, 4])
    parser.add_argument("--fewshot-source", default="", help="Path to per_case.jsonl from a successful RL run. Defaults to the aligned table run artifact.")
    parser.add_argument("--fewshot-source-data-path", default="", help="Optional parquet path used to map few-shot source figure_ids to rows. Defaults to --data-path.")
    parser.add_argument("--manual-teacher-bank", default=str(DEFAULT_MANUAL_TEACHER_BANK))
    parser.add_argument("--format-prompt", default=str(DEFAULT_JINJA))
    parser.add_argument(
        "--prompt-strategies",
        nargs="*",
        default=["baseline_retrieval"],
        help="Strategies: baseline_retrieval, label_guard, count_comparison_specialized, plan_then_action, answer_guard, combined_best, manual_skill_only, manual_skill_plus_teacher_examples",
    )
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--ignore-proxy-env", action="store_true", help="Unset proxy env vars inside this process before making requests.")
    parser.add_argument("--verbose", action="store_true", help="Print per-variant and per-row progress.")
    parser.add_argument(
        "--benchmark-variants",
        nargs="*",
        default=[],
        help="Benchmark variants to run. Supported: base_zero, base_fewshot_<k>, rl_zero.",
    )
    parser.add_argument(
        "--skip-generic-code",
        action="store_true",
        help="Skip the generic Python coding probe and only run benchmark variants.",
    )
    parser.add_argument("--rl-reference-summary", default="vision_agent_evolve/artifacts/vtool_protocol_eval/table_rl_7b_protocol_aligned_full/summary.json")
    args = parser.parse_args()

    if args.ignore_proxy_env:
        _clear_proxy_env()

    data_path = Path(args.data_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    format_prompt = Path(args.format_prompt)
    fewshot_source = Path(args.fewshot_source) if args.fewshot_source else (
        Path("/root/vision_agent_evolve_rl/vision_agent_evolve/artifacts/vtool_protocol_eval/table_rl_7b_protocol_aligned_full/per_case.jsonl")
    )
    manual_teacher_bank = Path(args.manual_teacher_bank)

    rows_df = _load_rows(data_path, args.benchmark_limit)
    fewshot_rows_df = _load_rows(Path(args.fewshot_source_data_path), limit=0) if args.fewshot_source_data_path else _load_rows(data_path, limit=0)
    jinja_raw = format_prompt.read_text(encoding="utf-8")

    base_client = _make_client(args.base_url_base, args.api_key)
    rl_client = _make_client(args.base_url_rl, args.api_key)

    example_pool = _build_example_pool(fewshot_rows_df, args.dataset_type, jinja_raw, fewshot_source)
    fixed_teacher_examples = _build_fixed_teacher_examples(
        rows_df=fewshot_rows_df,
        dataset_type=args.dataset_type,
        jinja_raw=jinja_raw,
        results_path=fewshot_source,
        teacher_bank_path=manual_teacher_bank,
    )

    benchmark_runs: list[dict[str, Any]] = []
    requested_variants = set(args.benchmark_variants)
    if not requested_variants:
        requested_variants = {"base_zero", "rl_zero"}
        for strategy in args.prompt_strategies:
            for count in args.fewshot_counts:
                requested_variants.add(f"base_{strategy}_{count}")
    if "base_zero" in requested_variants:
        benchmark_runs.append(
            _run_benchmark_variant(
                name="base_zero",
                client=base_client,
                model=args.model_base,
                rows_df=rows_df,
                dataset_type=args.dataset_type,
                jinja_raw=jinja_raw,
                example_pool=[],
                fixed_teacher_examples=[],
                fewshot_count=0,
                prompt_strategy="baseline_retrieval",
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                timeout=args.timeout,
                retries=args.retries,
                verbose=args.verbose,
            )
        )
    for strategy in args.prompt_strategies:
        for count in args.fewshot_counts:
            variant_name = f"base_{strategy}_{count}"
            legacy_variant_name = f"base_fewshot_{count}" if strategy == "baseline_retrieval" else ""
            if variant_name not in requested_variants and legacy_variant_name not in requested_variants:
                continue
            benchmark_runs.append(
                _run_benchmark_variant(
                    name=variant_name,
                    client=base_client,
                    model=args.model_base,
                    rows_df=rows_df,
                    dataset_type=args.dataset_type,
                    jinja_raw=jinja_raw,
                    example_pool=example_pool,
                    fixed_teacher_examples=fixed_teacher_examples,
                    fewshot_count=count,
                    prompt_strategy=strategy,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    timeout=args.timeout,
                    retries=args.retries,
                    verbose=args.verbose,
                )
            )
    if "rl_zero" in requested_variants:
        benchmark_runs.append(
            _run_benchmark_variant(
                name="rl_zero",
                client=rl_client,
                model=args.model_rl,
                rows_df=rows_df,
                dataset_type=args.dataset_type,
                jinja_raw=jinja_raw,
                example_pool=[],
                fixed_teacher_examples=[],
                fewshot_count=0,
                prompt_strategy="baseline_retrieval",
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                timeout=args.timeout,
                retries=args.retries,
                verbose=args.verbose,
            )
        )
    generic_runs: list[dict[str, Any]] = []
    if not args.skip_generic_code:
        generic_runs = [
            _run_generic_coding_variant(
                name="base_generic",
                client=base_client,
                model=args.model_base,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                timeout=args.timeout,
                retries=args.retries,
                verbose=args.verbose,
            ),
            _run_generic_coding_variant(
                name="rl_generic",
                client=rl_client,
                model=args.model_rl,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                timeout=args.timeout,
                retries=args.retries,
                verbose=args.verbose,
            ),
        ]

    payload = {
        "config": {
            "data_path": str(data_path.resolve()),
            "dataset_type": args.dataset_type,
            "benchmark_limit": len(rows_df),
            "fewshot_counts": list(args.fewshot_counts),
            "prompt_strategies": list(args.prompt_strategies),
            "fewshot_source": str(fewshot_source.resolve()),
            "manual_teacher_bank": str(manual_teacher_bank.resolve()),
            "format_prompt": str(format_prompt.resolve()),
            "base_url_base": args.base_url_base,
            "model_base": args.model_base,
            "base_url_rl": args.base_url_rl,
            "model_rl": args.model_rl,
            "ignore_proxy_env": bool(args.ignore_proxy_env),
        },
        "benchmark": {run["name"]: run for run in benchmark_runs},
        "generic_code": {run["name"]: run for run in generic_runs},
    }
    rl_ref_path = Path(args.rl_reference_summary)
    if rl_ref_path.exists():
        rl_summary = json.loads(rl_ref_path.read_text(encoding="utf-8"))
        payload["rl_reference"] = {
            "path": str(rl_ref_path.resolve()),
            "accuracy": rl_summary.get("accuracy"),
            "avg_score": rl_summary.get("avg_score"),
            "tool_exec_success_rate": rl_summary.get("tool_exec_success_rate"),
        }
        for run in payload["benchmark"].values():
            summary = run["summary"]
            if summary.get("exact_accuracy") is not None and payload["rl_reference"]["accuracy"] is not None:
                summary["rl_gap_exact"] = float(payload["rl_reference"]["accuracy"]) - float(summary["exact_accuracy"])
            if summary.get("avg_score") is not None and payload["rl_reference"]["avg_score"] is not None:
                summary["rl_gap_avg_score"] = float(payload["rl_reference"]["avg_score"]) - float(summary["avg_score"])
            if summary.get("tool_exec_success_rate") is not None and payload["rl_reference"]["tool_exec_success_rate"] is not None:
                summary["rl_gap_tool_exec_success"] = float(payload["rl_reference"]["tool_exec_success_rate"]) - float(summary["tool_exec_success_rate"])

    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
