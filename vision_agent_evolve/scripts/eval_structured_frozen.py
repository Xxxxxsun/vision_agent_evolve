"""Evaluate a frozen structured-benchmark subset or snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evolution.structured_runner import StructuredBenchmarkRunner, StructuredExperimentConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen structured benchmark capabilities.")
    parser.add_argument("--dataset", choices=["chartqa"], required=True)
    parser.add_argument("--raw-data-root", required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--subset-id", default="chartqa_refocus_v1")
    parser.add_argument("--held-out-split", default="val")
    parser.add_argument("--snapshot-name", default="")
    parser.add_argument("--enable-readability-judge", action="store_true")
    args = parser.parse_args()

    config = StructuredExperimentConfig(
        dataset=args.dataset,
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        subset_id=args.subset_id,
        held_out_split=args.held_out_split,
        readability_judge_enabled=args.enable_readability_judge,
    )
    runner = StructuredBenchmarkRunner(config=config, project_root=PROJECT_ROOT)
    records = runner.run_frozen_transfer(
        snapshot_name=args.snapshot_name or None,
        subset_id=None if args.snapshot_name else args.subset_id,
    )
    payload = {
        "dataset": args.dataset,
        "subset_id": args.subset_id,
        "snapshot_name": args.snapshot_name or None,
        "held_out_split": args.held_out_split,
        "total": len(records),
        "correct": sum(1 for row in records if row.correct),
        "records": [row.__dict__ for row in records],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
