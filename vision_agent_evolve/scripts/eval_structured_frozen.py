"""Evaluate a frozen structured-benchmark subset or snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evolution.benchmark_adapters import available_benchmark_datasets
from evolution.structured_runner import StructuredBenchmarkRunner, StructuredExperimentConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen structured benchmark capabilities.")
    parser.add_argument("--dataset", choices=available_benchmark_datasets(), required=True)
    parser.add_argument("--datasets", nargs="+", default=None, help="Optional multi-dataset evaluation list.")
    parser.add_argument("--raw-data-root", required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--subset-id", default="chartqa_refocus_v1")
    parser.add_argument("--held-out-split", default="val")
    parser.add_argument("--held-out-limit", type=int, default=0)
    parser.add_argument("--snapshot-name", default="")
    parser.add_argument(
        "--capability-mode",
        choices=["persistent_tools", "scratch_code_skill"],
        default="persistent_tools",
        help="Which frozen capability mode to evaluate.",
    )
    parser.add_argument(
        "--force-skill",
        action="store_true",
        help="Require the task skill to be executed before completion. In scratch mode, this also requires a new image artifact.",
    )
    parser.add_argument(
        "--disable-skill",
        action="store_true",
        help="Evaluate with built-in/persistent tools available but without loading evolved family skills.",
    )
    parser.add_argument("--enable-readability-judge", action="store_true")
    args = parser.parse_args()

    config = StructuredExperimentConfig(
        dataset=args.dataset,
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        subset_id=args.subset_id,
        datasets=args.datasets,
        held_out_split=args.held_out_split,
        held_out_limit=args.held_out_limit,
        readability_judge_enabled=args.enable_readability_judge,
    )
    runner = StructuredBenchmarkRunner(config=config, project_root=PROJECT_ROOT)
    records = runner.run_frozen_inference(
        snapshot_name=args.snapshot_name or None,
        subset_id=None if args.snapshot_name else args.subset_id,
        force_skill=args.force_skill,
        capability_mode=args.capability_mode,
        use_skill=not args.disable_skill,
    )
    summary = runner.rebuild_summary(snapshot_name=args.snapshot_name or None)
    payload = {
        "dataset": args.dataset,
        "subset_id": args.subset_id,
        "snapshot_name": args.snapshot_name or None,
        "held_out_split": args.held_out_split,
        "capability_mode": args.capability_mode,
        "force_skill": args.force_skill,
        "use_skill": not args.disable_skill,
        "total": len(records),
        "correct": sum(1 for row in records if row.correct),
        "summary_path": str(runner.summary_path),
        "frozen_accuracy": summary.get("settings", {}).get(runner._frozen_setting_name(args.capability_mode, args.force_skill, not args.disable_skill), {}).get("accuracy", 0.0),
        "records": [row.__dict__ for row in records],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
