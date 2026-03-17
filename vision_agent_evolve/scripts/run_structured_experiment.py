"""Run the ChartQA structured benchmark experiment."""

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
    parser = argparse.ArgumentParser(description="Run structured benchmark experiments.")
    parser.add_argument("--dataset", choices=["chartqa"], required=True)
    parser.add_argument("--raw-data-root", required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--subset-id", default="chartqa_refocus_v1")
    parser.add_argument("--evolve-split", default="train")
    parser.add_argument("--held-out-split", default="val")
    parser.add_argument("--k", type=int, default=200)
    parser.add_argument("--max-attempts", type=int, default=10)
    parser.add_argument("--enable-readability-judge", action="store_true")
    args = parser.parse_args()

    config = StructuredExperimentConfig(
        dataset=args.dataset,
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        subset_id=args.subset_id,
        evolve_split=args.evolve_split,
        held_out_split=args.held_out_split,
        k=args.k,
        max_attempts=args.max_attempts,
        readability_judge_enabled=args.enable_readability_judge,
    )
    runner = StructuredBenchmarkRunner(config=config, project_root=PROJECT_ROOT)
    summary = runner.run_experiment()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
