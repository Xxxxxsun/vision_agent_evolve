from __future__ import annotations

import json
from pathlib import Path

from core.structured_data import load_visualtoolbench_cases, normalize_visualtoolbench_dataset
from core.visualtoolbench_runner import VisualCaseResult, VisualToolBenchRunner, VisualTurnResult
from tools.visualtoolbench_tools import execute_visualtoolbench_tool


def test_visualtoolbench_normalization_roundtrip(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    image_path = raw_root / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    rows = [
        {
            "id": "case_1",
            "turncase": "single-turn",
            "num_turns": 1,
            "prompt_category": "generalist",
            "eval_focus": "hybrid_tool_reasoning",
            "turn_prompts": ["What is 2+2?"],
            "turn_golden_answers": ["4"],
            "turn_tool_trajectories": ["[]"],
            "rubrics_by_turn": ['{"r1":{"description":"answer is 4","weight":5,"critical":"yes"}}'],
            "images_by_turn": [[{"path": "sample.png"}]],
            "num_images": 1,
        }
    ]
    (raw_root / "visualtoolbench.json").write_text(json.dumps(rows), encoding="utf-8")

    normalized_root = tmp_path / "normalized"
    manifest = normalize_visualtoolbench_dataset(raw_root, normalized_root)
    cases = load_visualtoolbench_cases(normalized_root)

    assert manifest["dataset"] == "visualtoolbench"
    assert len(cases) == 1
    assert cases[0].num_turns == 1
    assert Path(cases[0].turns[0].image_paths[0]).exists()


def test_visualtoolbench_calculator_tool() -> None:
    result = execute_visualtoolbench_tool(
        "calculator",
        {"expression": "2 + 3 * 4"},
        workspace_dir=Path("artifacts/test_visualtoolbench"),
        image_paths=[],
    )
    assert result.status == "ok"
    assert result.answer == "14"


def test_visualtoolbench_python_image_processing_tool(tmp_path: Path) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = execute_visualtoolbench_tool(
        "python_image_processing",
        {
            "code": (
                "img = Image.open(image_list[0]).convert('RGB')\n"
                "img.save(Path(processed_image_save_path) / 'transformed_image_0.png', 'PNG')\n"
                "print('saved')\n"
            )
        },
        workspace_dir=tmp_path / "workspace",
        image_paths=[str(image_path)],
    )
    assert result.status == "ok"
    assert result.answer == "saved"
    assert result.artifacts
    assert Path(result.artifacts[0]).exists()


def test_visualtoolbench_python_image_processing_supports_import_and_alias(tmp_path: Path) -> None:
    image_path = tmp_path / "input.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = execute_visualtoolbench_tool(
        "python_image_processing",
        {
            "code": (
                "from PIL import Image\n"
                "img = Image.open('image_1.png').convert('RGB')\n"
                "img.save('transformed_image_1.png', 'PNG')\n"
                "print('ok')\n"
            )
        },
        workspace_dir=tmp_path / "workspace_alias",
        image_paths=[str(image_path)],
    )
    assert result.status == "ok"
    assert result.answer == "ok"


def test_visualtoolbench_diagnostics_summary() -> None:
    runner = VisualToolBenchRunner(
        normalized_data_root=Path("datasets/structured_multibench"),
        output_dir=Path("artifacts/test_visualtoolbench_runner"),
        client=object(),  # diagnostics path does not need a real VLM client
    )
    diagnostics = runner._build_diagnostics(
        [
            VisualCaseResult(
                case_id="case_1",
                turncase="single-turn",
                prompt_category="generalist",
                eval_focus="hybrid_tool_reasoning",
                num_turns=1,
                passed=False,
                average_score=0.25,
                failure_label="vision_extraction_failure",
                turn_results=[
                    VisualTurnResult(
                        turn_index=1,
                        prompt="q",
                        final_answer="",
                        gold_answer="a",
                        weighted_score=0.25,
                        passed=False,
                        rubric_results={},
                        failure_label="vision_extraction_failure",
                        tool_calls=[],
                    )
                ],
            )
        ]
    )
    assert diagnostics["failure_counts"]["vision_extraction_failure"] == 1
    assert diagnostics["no_tool_case_ratio"] == 1.0
