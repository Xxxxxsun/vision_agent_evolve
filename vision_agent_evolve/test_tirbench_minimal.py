from __future__ import annotations

import json
from pathlib import Path

from core.structured_data import load_tirbench_cases, normalize_tirbench_dataset
from core.tirbench_runner import score_tirbench_answer


def test_tirbench_normalization_roundtrip(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    image_dir = raw_root / "data" / "math"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "sample.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    rows = [
        {
            "id": 1,
            "task": "math",
            "answer": "C",
            "prompt": "Which option is correct?",
            "image_1": "data/math/sample.png",
            "image_2": None,
            "meta_data": {"difficulty": None},
        }
    ]
    (raw_root / "TIR-Bench.json").write_text(json.dumps(rows), encoding="utf-8")

    normalized_root = tmp_path / "normalized"
    manifest = normalize_tirbench_dataset(raw_root, normalized_root)
    cases = load_tirbench_cases(normalized_root)

    assert manifest["dataset"] == "tirbench"
    assert len(cases) == 1
    assert cases[0].task == "math"
    assert cases[0].gold_answer == "C"
    assert Path(cases[0].image_paths[0]).exists()


def test_tirbench_scores_choice_int_float() -> None:
    assert score_tirbench_answer("math", "", "C", "C") == 1.0
    assert score_tirbench_answer("instrument", "", "72", "72") == 1.0
    assert score_tirbench_answer("instrument", "", "72.5", "72.5") == 1.0


def test_tirbench_scores_jigsaw_partial_credit() -> None:
    score = score_tirbench_answer(
        "jigsaw",
        "",
        "1, 2, 3, 4",
        "[1, 4, 3, 2]",
        {"metadata": {"difficulty": 2}},
    )
    assert score == 0.5


def test_tirbench_scores_spot_difference_iou() -> None:
    score = score_tirbench_answer("spot_difference", "", "1, 2, 3", "2, 3, 4")
    assert score == 0.5


def test_tirbench_scores_ocr_response_contains_answer() -> None:
    assert score_tirbench_answer("ocr", "the visible word is mobi", "", "wrong", {"image_1": "60.jpg"}) == 1.0
