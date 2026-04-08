"""Run TIR-Bench in direct or tool-enabled mode."""

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

from core.structured_data import load_tirbench_cases
from core.tirbench_runner import TirBenchRunner
from core.vlm_client import VLMClient
from tools.visualtoolbench_tools import execute_visualtoolbench_tool


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate TIR-Bench with direct or tool-enabled prompting.")
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--mode", choices=["direct", "tool"], default="direct")
    parser.add_argument("--output-dir", default="artifacts/tirbench")
    parser.add_argument("--solver-model", default="", help="Optional solver model override. Defaults to VLM_MODEL.")
    parser.add_argument("--extractor-model", default="", help="Optional answer extractor model. Defaults to solver model.")
    parser.add_argument("--max-tool-calls", type=int, default=20)
    parser.add_argument("--preflight-limit", type=int, default=3)
    parser.add_argument("--skip-preflight", action="store_true")
    args = parser.parse_args()

    _ensure_model_env()
    normalized_root = Path(args.normalized_data_root)
    cases = load_tirbench_cases(normalized_root, split=args.split, limit=max(args.limit, args.preflight_limit, 1))

    if not args.skip_preflight:
        preflight = _run_preflight(cases[: max(1, args.preflight_limit)], mode=args.mode)
        print(json.dumps({"preflight": preflight}, ensure_ascii=False, indent=2))

    solver_client = VLMClient(model=args.solver_model.strip() or None)
    extractor_model = args.extractor_model.strip()
    extractor_client = VLMClient(model=extractor_model) if extractor_model else solver_client

    runner = TirBenchRunner(
        normalized_data_root=normalized_root,
        output_dir=PROJECT_ROOT / args.output_dir,
        client=solver_client,
        extractor_client=extractor_client,
        mode=args.mode,
        max_tool_calls=args.max_tool_calls,
    )
    summary = runner.run(split=args.split, limit=args.limit)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _ensure_model_env() -> None:
    missing = [key for key in ("VLM_BASE_URL", "VLM_API_KEY", "VLM_MODEL") if not os.getenv(key, "").strip()]
    if missing:
        raise SystemExit("Missing required model environment variables for TIR-Bench eval: " + ", ".join(missing))


def _run_preflight(cases: list, mode: str) -> dict[str, object]:
    if not cases:
        return {"ok": False, "error": "No TIR-Bench cases available for preflight."}
    missing_images = [
        image_path
        for case in cases
        for image_path in case.image_paths
        if not Path(image_path).exists()
    ]
    result: dict[str, object] = {
        "ok": not missing_images,
        "sample_cases": len(cases),
        "missing_images": missing_images[:5],
        "mode": mode,
    }
    if mode == "tool":
        with tempfile.TemporaryDirectory(prefix="tir_preflight_") as tmp_dir:
            workspace = Path(tmp_dir)
            calc = execute_visualtoolbench_tool(
                "calculator",
                {"expression": "2 + 3 * 4"},
                workspace_dir=workspace / "calculator",
                image_paths=[],
            )
            first_images = cases[0].image_paths
            image_proc = execute_visualtoolbench_tool(
                "python_image_processing",
                {
                    "code": (
                        "from pathlib import Path\n"
                        "img = Image.open(image_list[0]).convert('RGB')\n"
                        "img.save(Path(processed_image_save_path) / 'transformed_image_0.png')\n"
                        "print('saved')\n"
                    )
                },
                workspace_dir=workspace / "python_image_processing",
                image_paths=first_images,
            ) if first_images else None
            result.update(
                {
                    "ok": bool(result["ok"]) and calc.status == "ok" and (image_proc is None or image_proc.status == "ok"),
                    "calculator_status": calc.status,
                    "python_image_processing_status": None if image_proc is None else image_proc.status,
                    "python_image_processing_artifacts": [] if image_proc is None else image_proc.artifacts,
                }
            )
    return result


if __name__ == "__main__":
    main()
