"""Probe Refocus_Chart per-case outputs and summarize likely failure modes."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _categorize(row: dict[str, Any], kind: str) -> str:
    answer = str(row.get("answer", "") or "").strip()
    expected = str(row.get("expected", "") or "").strip()
    question_type = str((row.get("metadata") or {}).get("question_type", "")).strip()
    if row.get("correct"):
        return "correct"
    if not answer:
        return "empty_answer"

    lower = answer.lower()
    if answer.endswith((":","(","/",",")):
        return "truncated_output"
    if (
        ("to answer this question" in lower or "let's" in lower or "step by step" in lower)
        and len(answer) > 200
        and "final answer:" not in lower
    ):
        return "overlong_reasoning_or_truncation"
    if expected and expected.lower() in lower and lower != expected.lower():
        return "contains_expected_but_extra_text"
    if ":" in answer and any(ch.isdigit() for ch in answer):
        return "ratio_or_time_format_confusion"
    if (question_type == "boolean" or expected in {"Yes", "No"}) and ("yes" in lower or "no" in lower):
        if expected.lower() not in lower:
            return "boolean_polarity_error"
    if kind == "manual" and int(row.get("tool_count", 0) or 0) > 0:
        return "tool_guided_wrong_answer"
    return "other_wrong"


def _summarize(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    by_category = Counter()
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        category = _categorize(row, kind)
        family = str((row.get("metadata") or {}).get("capability_family", "unknown"))
        by_category[category] += 1
        by_family[family][category] += 1
        if category != "correct" and len(samples[category]) < 12:
            samples[category].append(
                {
                    "case_id": row.get("case_id"),
                    "family": family,
                    "question_type": (row.get("metadata") or {}).get("question_type"),
                    "expected": row.get("expected"),
                    "answer": row.get("answer"),
                    "tool_names": row.get("tool_names", []),
                }
            )
    return {
        "counts": dict(by_category),
        "per_family": {family: dict(counter) for family, counter in sorted(by_family.items())},
        "samples": dict(samples),
    }


def _join_direct_and_manual(
    direct_rows: list[dict[str, Any]],
    manual_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    direct_map = {str(row["case_id"]): row for row in direct_rows}
    manual_map = {str(row["case_id"]): row for row in manual_rows}
    quadrants = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case_id in sorted(direct_map.keys()):
        direct = direct_map[case_id]
        manual = manual_map[case_id]
        key = f"direct_{'correct' if direct.get('correct') else 'wrong'}__manual_{'correct' if manual.get('correct') else 'wrong'}"
        quadrants[key] += 1
        if len(examples[key]) < 12:
            examples[key].append(
                {
                    "case_id": case_id,
                    "family": (direct.get("metadata") or {}).get("capability_family"),
                    "expected": direct.get("expected"),
                    "direct_answer": direct.get("answer"),
                    "manual_answer": manual.get("answer"),
                    "manual_tools": manual.get("tool_names", []),
                }
            )
    return {
        "quadrants": dict(quadrants),
        "examples": dict(examples),
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Refocus_Chart Probe Report")
    lines.append("")
    lines.append("## Direct VLM Failure Modes")
    lines.append("")
    for key, value in payload["direct"]["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Manual Skill + Tool Failure Modes")
    lines.append("")
    for key, value in payload["manual"]["counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Direct vs Manual Quadrants")
    lines.append("")
    for key, value in payload["comparison"]["quadrants"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("## Probe Reading")
    lines.append("")
    lines.append("- `direct_vlm` is hurt mainly by overlong reasoning, truncation, and ratio/format confusion rather than pure visual blindness.")
    lines.append("- `manual skill + tool` is hurt mainly by `empty_answer` and `tool_guided_wrong_answer`, which suggests the current handwritten SOP/tool orchestration is the main failure point.")
    lines.append("- The dominant manual failure mode is not lack of tool access; it is using tools but failing to convert the resulting evidence into a correct short final answer.")
    lines.append("")
    lines.append("## Sample Quadrant Cases")
    lines.append("")
    for key, rows in payload["comparison"]["examples"].items():
        lines.append(f"### `{key}`")
        lines.append("")
        for row in rows[:5]:
            lines.append(
                f"- `{row['case_id']}` `{row['family']}` expected=`{row['expected']}` "
                f"direct=`{str(row['direct_answer'])[:120]}` manual=`{str(row['manual_answer'])[:120]}`"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Refocus_Chart failure modes from per-case JSONL outputs.")
    parser.add_argument("--direct-per-case", required=True)
    parser.add_argument("--manual-per-case", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    direct_rows = _load_rows(Path(args.direct_per_case))
    manual_rows = _load_rows(Path(args.manual_per_case))
    payload = {
        "direct": _summarize(direct_rows, "direct"),
        "manual": _summarize(manual_rows, "manual"),
        "comparison": _join_direct_and_manual(direct_rows, manual_rows),
    }
    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(_to_markdown(payload), encoding="utf-8")
    print(json.dumps({"output_json": str(output_json), "output_md": str(output_md)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
