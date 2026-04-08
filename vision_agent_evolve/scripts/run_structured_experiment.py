"""Run the ChartQA structured benchmark experiment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evolution.benchmark_adapters import available_benchmark_datasets
from evolution.benchmark_adapters import get_benchmark_adapter
from evolution.structured_runner import StructuredBenchmarkRunner, StructuredExperimentConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run structured benchmark experiments.")
    parser.add_argument("--dataset", choices=available_benchmark_datasets(), required=True)
    parser.add_argument("--datasets", nargs="+", default=None, help="Optional multi-dataset training/eval list.")
    parser.add_argument("--raw-data-root", required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--subset-id", default="chartqa_refocus_v1")
    parser.add_argument("--evolve-split", default="train")
    parser.add_argument("--held-out-split", default="val")
    parser.add_argument("--k", type=int, default=200)
    parser.add_argument("--train-subset-size", type=int, default=0)
    parser.add_argument("--held-out-limit", type=int, default=0)
    parser.add_argument("--max-attempts", type=int, default=10)
    parser.add_argument("--max-planning-rounds", type=int, default=5)
    parser.add_argument("--families-per-round-limit", type=int, default=3)
    parser.add_argument("--representatives-per-cluster", type=int, default=3)
    parser.add_argument(
        "--tool-preference",
        choices=["balanced", "prefer_tools", "require_tools"],
        default="balanced",
        help="Bias the subset planner toward tool generation.",
    )
    parser.add_argument("--enable-readability-judge", action="store_true")
    parser.add_argument("--save-first-n-evolves", type=int, default=10)
    parser.add_argument("--forced-skill-name", default=None)
    parser.add_argument(
        "--fixed-tool-names",
        nargs="+",
        default=[],
        help="Optional allowlist of preset builtin tool names for same-tool comparisons.",
    )
    parser.add_argument(
        "--disable-generated-tools",
        action="store_true",
        help="Forbid new learned tool generation and use only the fixed preset tool pool.",
    )
    parser.add_argument(
        "--settings",
        nargs="+",
        default=["direct_vlm", "pure_react", "agent_train_adaptive", "preset_tools_only", "frozen_inference"],
        help="Subset of settings to run. Choices: direct_vlm pure_react toolpool_prompt_baseline agent_train_adaptive agent_train_batch_evolve skill_only_train_adaptive preset_tools_only same_tool_preset_tools_only frozen_inference skill_only_frozen_inference frozen_inference_forced_skill scratch_skill_train_adaptive scratch_skill_frozen_inference scratch_skill_frozen_forced self_evolve online_evolve frozen_transfer all",
    )
    args = parser.parse_args()

    settings = _normalize_settings(args.settings)

    config = StructuredExperimentConfig(
        dataset=args.dataset,
        raw_data_root=Path(args.raw_data_root),
        normalized_data_root=Path(args.normalized_data_root),
        subset_id=args.subset_id,
        datasets=args.datasets,
        evolve_split=args.evolve_split,
        held_out_split=args.held_out_split,
        k=args.k,
        train_subset_size=args.train_subset_size,
        held_out_limit=args.held_out_limit,
        max_attempts=args.max_attempts,
        max_planning_rounds=args.max_planning_rounds,
        families_per_round_limit=args.families_per_round_limit,
        representatives_per_cluster=args.representatives_per_cluster,
        tool_preference=args.tool_preference,
        readability_judge_enabled=args.enable_readability_judge,
        settings=settings,
        save_first_n_evolves=args.save_first_n_evolves,
        forced_skill_name=args.forced_skill_name,
        fixed_tool_names=args.fixed_tool_names,
        disable_generated_tools=args.disable_generated_tools,
    )
    _validate_dataset_assets(config)
    runner = StructuredBenchmarkRunner(config=config, project_root=PROJECT_ROOT)
    summary = runner.run_experiment()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _normalize_settings(raw_settings: list[str]) -> list[str]:
    expanded: list[str] = []
    for setting in raw_settings:
        normalized = setting.strip().lower()
        if normalized == "all":
            expanded.extend(["direct_vlm", "pure_react", "toolpool_prompt_baseline", "agent_train_adaptive", "preset_tools_only", "frozen_inference"])
            continue
        aliases = {
            "self_evolve": "agent_train_adaptive",
            "online_evolve": "agent_train_adaptive",
            "frozen_transfer": "frozen_inference",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in {
            "direct_vlm",
            "pure_react",
            "toolpool_prompt_baseline",
            "agent_train_adaptive",
            "agent_train_batch_evolve",
            "skill_only_train_adaptive",
            "preset_tools_only",
            "same_tool_preset_tools_only",
            "frozen_inference",
            "skill_only_frozen_inference",
            "frozen_inference_forced_skill",
            "scratch_skill_train_adaptive",
            "scratch_skill_frozen_inference",
            "scratch_skill_frozen_forced",
        }:
            raise SystemExit(f"Unknown setting: {setting}")
        if normalized not in expanded:
            expanded.append(normalized)
    return expanded


def _validate_dataset_assets(config: StructuredExperimentConfig) -> None:
    dataset_names = config.datasets or [config.dataset]
    missing_by_dataset: dict[str, list[str]] = {}
    for dataset_name in dataset_names:
        adapter = get_benchmark_adapter(dataset_name)
        split_names = {config.evolve_split}
        if config.held_out_split:
            split_names.add(config.held_out_split)
        for split in split_names:
            cases = adapter.load_cases(config.normalized_data_root, split, limit=0)
            missing = [
                f"{case.case_id}: {case.image_path}"
                for case in cases
                if case.image_path and not Path(case.image_path).exists()
            ]
            if missing:
                missing_by_dataset.setdefault(dataset_name, []).extend(missing)

    if not missing_by_dataset:
        return

    lines = ["Dataset asset validation failed. Missing image files detected before experiment start:"]
    for dataset_name, missing in sorted(missing_by_dataset.items()):
        lines.append(f"- {dataset_name}: {len(missing)} missing")
        lines.extend(f"  {entry}" for entry in missing[:5])
    raise SystemExit("\n".join(lines))


if __name__ == "__main__":
    main()
