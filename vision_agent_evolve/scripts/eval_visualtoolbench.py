"""Run the dedicated VisualToolBench evaluator."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.structured_data import load_visualtoolbench_cases
from core.vlm_client import VLMClient
from core.visualtoolbench_runner import VisualToolBenchRunner
from tools.visualtoolbench_tools import execute_visualtoolbench_tool


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate VisualToolBench with tool-enabled prompting.")
    parser.add_argument("--normalized-data-root", required=True, help="Root containing normalized VisualToolBench JSONL files.")
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--output-dir", default="artifacts/visualtoolbench")
    parser.add_argument("--max-tool-calls-per-turn", type=int, default=20)
    parser.add_argument("--preflight-limit", type=int, default=3, help="Run a small preflight sample before the main evaluation.")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--judge-model", default="", help="Optional separate judge model. Defaults to current VLM_MODEL.")
    args = parser.parse_args()

    normalized_root = Path(args.normalized_data_root)
    _ensure_model_env()
    cases = load_visualtoolbench_cases(normalized_root, split=args.split, limit=max(args.preflight_limit, args.limit, 1))

    if not args.skip_preflight:
        preflight = _run_preflight(cases[: max(1, args.preflight_limit)])
        print(json.dumps({"preflight": preflight}, ensure_ascii=False, indent=2))

    solver_client = VLMClient()
    judge_model = args.judge_model.strip()
    judge_client = VLMClient(model=judge_model) if judge_model else solver_client

    runner = VisualToolBenchRunner(
        normalized_data_root=normalized_root,
        output_dir=PROJECT_ROOT / args.output_dir,
        client=solver_client,
        judge_client=judge_client,
        max_tool_calls_per_turn=args.max_tool_calls_per_turn,
    )
    summary = runner.run(split=args.split, limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _ensure_model_env() -> None:
    missing = []
    for key in ("VLM_BASE_URL", "VLM_API_KEY", "VLM_MODEL"):
        if not os.getenv(key, "").strip():
            missing.append(key)
    if missing:
        raise SystemExit(
            "Missing required model environment variables for VisualToolBench eval: " + ", ".join(missing)
        )


def _run_preflight(cases: list) -> dict[str, object]:
    if not cases:
        return {"ok": False, "error": "No VisualToolBench cases available for preflight."}

    with tempfile.TemporaryDirectory(prefix="vtb_preflight_") as tmp_dir:
        workspace = Path(tmp_dir)
        calc = execute_visualtoolbench_tool(
            "calculator",
            {"expression": "2 + 3 * 4"},
            workspace_dir=workspace / "calculator",
            image_paths=[],
        )
        interp = execute_visualtoolbench_tool(
            "python_interpreter",
            {"code": "print(6 * 7)"},
            workspace_dir=workspace / "python_interpreter",
            image_paths=[],
        )
        first_images = cases[0].turns[0].image_paths if cases[0].turns else []
        image_proc = execute_visualtoolbench_tool(
            "python_image_processing",
            {
                "code": (
                    "from pathlib import Path\n"
                    "img = Image.open(image_list[0]).convert('RGB')\n"
                    "img.save(Path(processed_image_save_path) / 'transformed_image_0.png', 'PNG')\n"
                    "print('saved')\n"
                )
            },
            workspace_dir=workspace / "python_image_processing",
            image_paths=first_images,
        ) if first_images else None

        image_paths_exist = sum(
            1
            for case in cases
            for turn in case.turns
            for image_path in turn.image_paths
            if Path(image_path).exists()
        )
        return {
            "ok": calc.status == "ok" and interp.status == "ok" and (image_proc is None or image_proc.status == "ok"),
            "sample_cases": len(cases),
            "image_paths_checked": image_paths_exist,
            "calculator_status": calc.status,
            "python_interpreter_status": interp.status,
            "python_image_processing_status": None if image_proc is None else image_proc.status,
            "python_image_processing_artifacts": [] if image_proc is None else image_proc.artifacts,
        }


if __name__ == "__main__":
    main()
