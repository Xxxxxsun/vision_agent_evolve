"""Merge our structured-run summary with VTool-R1 results into one comparison payload."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_our_score(summary: dict[str, Any], setting: str) -> float | None:
    settings = summary.get("settings", {})
    row = settings.get(setting, {})
    value = row.get("accuracy")
    if value is None:
        value = row.get("primary_score")
    return None if value is None else float(value)


def _read_vtool_score(payload: dict[str, Any]) -> float | None:
    for key in ["accuracy", "score", "primary_score", "relaxed_accuracy"]:
        value = payload.get(key)
        if value is not None:
            return float(value)
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        for key in ["accuracy", "score", "primary_score", "relaxed_accuracy"]:
            value = metrics.get(key)
            if value is not None:
                return float(value)
    return None


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "api_model"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare our results against a VTool-R1 result JSON.")
    parser.add_argument("--dataset", required=True, help="Dataset label, e.g. chartqa or refocus_tablevqa.")
    parser.add_argument("--our-summary", required=True, help="Path to artifacts/.../summary.json produced by this repo.")
    parser.add_argument("--vtool-result", required=True, help="Path to a JSON file containing VTool-R1 metrics for the same dataset.")
    parser.add_argument("--our-setting", default="skill_only_frozen_inference", help="Setting key inside our summary.json.")
    parser.add_argument(
        "--reference-label",
        default="vtool_r1_reported",
        help="Row label for the reference result, e.g. vtool_r1_reported.",
    )
    parser.add_argument(
        "--api-label",
        default="",
        help="Optional row label prefix for the API model. Defaults to the model name from our summary config.",
    )
    parser.add_argument("--output", default="", help="Optional output JSON path.")
    args = parser.parse_args()

    our_summary = _load_json(Path(args.our_summary))
    vtool_payload = _load_json(Path(args.vtool_result))

    our_score = _read_our_score(our_summary, args.our_setting)
    vtool_score = _read_vtool_score(vtool_payload)
    direct_score = _read_our_score(our_summary, "direct_vlm")
    prompt_score = _read_our_score(our_summary, "toolpool_prompt_baseline")
    config = our_summary.get("config", {})
    api_model = args.api_label or str(config.get("vlm_model", "") or "api_model")
    api_row_prefix = _slugify(api_model)

    payload = {
        "dataset": args.dataset,
        "our_setting": args.our_setting,
        "api_model": api_model,
        "rows": {
            f"{api_row_prefix}_direct": direct_score,
            f"{api_row_prefix}_same_tool_prompt": prompt_score,
            "ours_same_tool_evolve": our_score,
            args.reference_label: vtool_score,
        },
        "deltas": {
            "ours_minus_direct": None if our_score is None or direct_score is None else our_score - direct_score,
            "ours_minus_prompt": None if our_score is None or prompt_score is None else our_score - prompt_score,
            "ours_minus_vtool_r1": None if our_score is None or vtool_score is None else our_score - vtool_score,
        },
        "sources": {
            "our_summary": str(Path(args.our_summary).resolve()),
            "vtool_result": str(Path(args.vtool_result).resolve()),
        },
        "reference": {
            "label": args.reference_label,
            "score_source": "reported_reference",
        },
        "runtime": {
            "vlm_model": config.get("vlm_model", ""),
            "vlm_base_url": config.get("vlm_base_url", ""),
            "vlm_api_style": config.get("vlm_api_style", ""),
            "uses_alibaba_chat_api": bool(config.get("uses_alibaba_chat_api")),
            "disable_generated_tools": bool(config.get("disable_generated_tools")),
            "fixed_tool_names": list(config.get("fixed_tool_names", [])),
        },
    }

    if args.output:
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
