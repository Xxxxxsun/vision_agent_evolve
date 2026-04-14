"""Dataset normalization and loading utilities for structured benchmarks."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import random
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from .types import MultiTurnTaskCase, MultiTurnTaskTurn, TaskCase


def load_json_objects(path: Path) -> list[dict[str, Any]]:
    """Load one or more JSON objects from a file."""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    items: list[dict[str, Any]] = []
    index = 0
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw):
            break
        obj, next_index = decoder.raw_decode(raw, index)
        if isinstance(obj, dict):
            items.append(obj)
        index = next_index
    return items


def normalize_chartqa_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    splits: Iterable[str] = ("train", "val"),
) -> dict[str, Any]:
    """Normalize locally provided ChartQA annotations into the TaskCase schema."""
    dataset_root = normalized_data_root / "chartqa"
    dataset_root.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "dataset": "chartqa",
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "splits": {},
    }

    for split in splits:
        annotation_files = _discover_chartqa_annotation_files(raw_data_root, split)
        if not annotation_files:
            raise FileNotFoundError(
                f"Could not find ChartQA annotation files for split '{split}' under {raw_data_root}"
            )

        records: list[dict[str, Any]] = []
        for annotation_file in annotation_files:
            for index, item in enumerate(load_json_objects(annotation_file), start=1):
                records.append(
                    _normalize_chartqa_record(
                        item=item,
                        split=split,
                        raw_data_root=raw_data_root,
                        annotation_file=annotation_file,
                        fallback_index=index,
                    )
                )

        output_file = dataset_root / f"{split}.jsonl"
        with output_file.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        manifest["splits"][split] = {
            "count": len(records),
            "annotation_files": [str(path) for path in annotation_files],
            "output_file": str(output_file),
        }

    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_normalized_cases(
    normalized_data_root: Path,
    dataset: str,
    split: str,
    limit: int = 0,
) -> list[TaskCase]:
    """Load normalized TaskCase objects from JSONL."""
    dataset_root = normalized_data_root / dataset
    split_file = dataset_root / f"{split}.jsonl"
    if not split_file.exists():
        raise FileNotFoundError(f"Normalized split not found: {split_file}")

    cases: list[TaskCase] = []
    for index, item in enumerate(load_json_objects(split_file), start=1):
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("dataset_name", dataset)
        metadata.setdefault("split", split)
        metadata.setdefault("source_id", str(item.get("id", f"{dataset}_{split}_{index}")))
        metadata.setdefault("capability_family", str(item.get("problem_id", dataset)))
        case = TaskCase(
            case_id=str(item.get("id", f"{dataset}_{split}_{index}")),
            problem_id=str(item.get("problem_id", dataset)),
            prompt=str(item.get("prompt", item.get("question", ""))),
            gold_answer=str(item.get("answer", item.get("gold_answer", ""))),
            image_path=str(item.get("image_path", "")),
            metadata=metadata,
        )
        cases.append(case)
        if limit and len(cases) >= limit:
            break
    return cases


def normalize_vstar_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_size: int = 40,
    val_size: int = 151,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize V* benchmark data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "vstar"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "vstar"
    source_files = _discover_data_files(raw_data_root, include_tokens=["test"])
    if not source_files:
        raise FileNotFoundError(f"Could not find VStar data files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
    if limit:
        rows = rows[:limit]
    records = [
        _normalize_vstar_record(item, raw_data_root, assets_root, index)
        for index, item in enumerate(rows, start=1)
    ]
    return _write_pseudo_split_dataset(
        dataset_name="vstar",
        raw_data_root=raw_data_root,
        dataset_root=dataset_root,
        records=records,
        source_files=source_files,
        train_size=train_size,
        val_size=val_size,
        source_split="test",
    )


def normalize_hrbench_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_size: int = 100,
    val_size: int = 700,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize HRBench 4K data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "hrbench"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "hrbench"
    source_files = _discover_data_files(raw_data_root, include_tokens=["4k", "hrbench"])
    if not source_files:
        raise FileNotFoundError(f"Could not find HRBench data files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
    if limit:
        rows = rows[:limit]
    records = [
        _normalize_hrbench_record(item, raw_data_root, assets_root, index)
        for index, item in enumerate(rows, start=1)
    ]
    return _write_pseudo_split_dataset(
        dataset_name="hrbench",
        raw_data_root=raw_data_root,
        dataset_root=dataset_root,
        records=records,
        source_files=source_files,
        train_size=train_size,
        val_size=val_size,
        source_split="hrbench_4k",
    )


def normalize_mathvista_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_size: int = 100,
    val_size: int = 900,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize MathVista testmini data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "mathvista"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "mathvista"
    source_files = _discover_data_files(raw_data_root, include_tokens=["testmini", "mathvista"])
    if not source_files:
        raise FileNotFoundError(f"Could not find MathVista testmini files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
    if limit:
        rows = rows[:limit]
    rows = _extract_semantic_records(rows)
    records = [
        _normalize_mathvista_record(item, raw_data_root, assets_root, index)
        for index, item in enumerate(rows, start=1)
    ]
    return _write_pseudo_split_dataset(
        dataset_name="mathvista",
        raw_data_root=raw_data_root,
        dataset_root=dataset_root,
        records=records,
        source_files=source_files,
        train_size=train_size,
        val_size=val_size,
        source_split="testmini",
    )


def normalize_refocus_tablevqa_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_size: int = 200,
    val_size: int = 500,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize ReFOCUS-style TableVQA data into shared JSONL files."""
    dataset_root = normalized_data_root / "refocus_tablevqa"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "refocus_tablevqa"
    source_files = _discover_data_files(
        raw_data_root,
        include_tokens=["tablevqa", "table_vqa", "refocus", "table", "wtq", "fintabnet", "tabfact"],
    )
    if not source_files:
        raise FileNotFoundError(f"Could not find ReFOCUS/TableVQA files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
    if limit:
        rows = rows[:limit]
    rows = _extract_semantic_records(rows)
    records = [
        _normalize_refocus_tablevqa_record(item, raw_data_root, assets_root, index)
        for index, item in enumerate(rows, start=1)
    ]
    return _write_pseudo_split_dataset(
        dataset_name="refocus_tablevqa",
        raw_data_root=raw_data_root,
        dataset_root=dataset_root,
        records=records,
        source_files=source_files,
        train_size=train_size,
        val_size=val_size,
        source_split="refocus_tablevqa",
    )


def normalize_refocus_chart_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_split: str = "train",
    eval_split: str = "test",
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize ReFOCUS-Chart data into shared JSONL files."""
    dataset_root = normalized_data_root / "refocus_chart"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "refocus_chart"

    split_to_files = {
        train_split: _discover_data_files(raw_data_root, include_tokens=["train", "refocus", "chart"]),
        eval_split: _discover_data_files(raw_data_root, include_tokens=["test", "refocus", "chart"]),
    }
    if not split_to_files[train_split]:
        raise FileNotFoundError(f"Could not find ReFOCUS-Chart train files under {raw_data_root}")
    if not split_to_files[eval_split]:
        raise FileNotFoundError(f"Could not find ReFOCUS-Chart test files under {raw_data_root}")

    manifest: dict[str, Any] = {
        "dataset": "refocus_chart",
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "splits": {},
    }

    for split, files in split_to_files.items():
        rows = _load_rows_from_files(files)
        if limit:
            rows = rows[:limit]
        records = [
            _normalize_refocus_chart_record(item, raw_data_root, assets_root / split, index)
            for index, item in enumerate(rows, start=1)
        ]
        output_file = dataset_root / f"{split}.jsonl"
        _write_jsonl(output_file, records)
        manifest["splits"][split] = {
            "count": len(records),
            "source_files": [str(path) for path in files],
            "output_file": str(output_file),
        }

    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def normalize_textvqa_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize TextVQA train/validation data into shared JSONL files."""
    dataset_root = normalized_data_root / "textvqa"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "textvqa"

    split_to_files = {
        "train": _discover_data_files(raw_data_root, include_tokens=["train", "textvqa"]),
        "val": _discover_data_files(raw_data_root, include_tokens=["validation", "val", "textvqa"]),
    }
    if not split_to_files["train"]:
        raise FileNotFoundError(f"Could not find TextVQA train files under {raw_data_root}")
    if not split_to_files["val"]:
        raise FileNotFoundError(f"Could not find TextVQA validation files under {raw_data_root}")

    manifest: dict[str, Any] = {
        "dataset": "textvqa",
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "splits": {},
    }
    for split, files in split_to_files.items():
        rows = _load_rows_from_files(files)
        if limit:
            rows = rows[:limit]
        records = [
            _normalize_textvqa_record(item, raw_data_root, assets_root, split, index)
            for index, item in enumerate(rows, start=1)
        ]
        output_file = dataset_root / f"{split}.jsonl"
        _write_jsonl(output_file, records)
        manifest["splits"][split] = {
            "count": len(records),
            "source_split": "validation" if split == "val" else "train",
            "source_files": [str(path) for path in files],
            "output_file": str(output_file),
        }

    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def normalize_gta_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    train_ratio: float = 0.3,
    seed: int = 42,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize GTA benchmark data into shared JSONL files."""
    dataset_root = normalized_data_root / "gta"
    dataset_root.mkdir(parents=True, exist_ok=True)

    dataset_file = raw_data_root / "dataset.json"
    toolmeta_file = raw_data_root / "toolmeta.json"
    image_dir = raw_data_root / "image"
    if not dataset_file.exists():
        raise FileNotFoundError(f"Could not find GTA dataset file under {raw_data_root}")
    if not toolmeta_file.exists():
        raise FileNotFoundError(f"Could not find GTA tool metadata file under {raw_data_root}")
    if not image_dir.exists():
        raise FileNotFoundError(f"Could not find GTA image directory under {raw_data_root}")

    raw_data = json.loads(dataset_file.read_text(encoding="utf-8"))
    toolmeta = json.loads(toolmeta_file.read_text(encoding="utf-8"))

    records: list[dict[str, Any]] = []
    for index, (qid, item) in enumerate(sorted(raw_data.items(), key=lambda pair: int(pair[0]))):
        if limit and index >= limit:
            break
        record = _normalize_gta_record(str(qid), item, raw_data_root, toolmeta)
        if record is not None:
            records.append(record)

    rng = random.Random(seed)
    indices = list(range(len(records)))
    rng.shuffle(indices)
    train_size = max(1, int(len(records) * train_ratio)) if records else 0
    train_indices = sorted(indices[:train_size])
    val_indices = sorted(indices[train_size:])

    split_map = {"train": train_indices, "val": val_indices}
    manifest: dict[str, Any] = {
        "dataset": "gta",
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "total_cases": len(records),
        "train_ratio": train_ratio,
        "seed": seed,
        "splits": {},
        "unique_tools": sorted({tool for row in records for tool in row["metadata"].get("gt_tools", [])}),
        "tool_categories": sorted({str(row["metadata"].get("tool_category", "unknown")) for row in records}),
    }

    for split, split_indices in split_map.items():
        split_file = dataset_root / f"{split}.jsonl"
        with split_file.open("w", encoding="utf-8") as handle:
            for idx in split_indices:
                handle.write(json.dumps(records[idx], ensure_ascii=False) + "\n")
        manifest["splits"][split] = {
            "count": len(split_indices),
            "output_file": str(split_file),
        }

    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def normalize_visualtoolbench_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
    limit: int = 0,
) -> dict[str, Any]:
    """Normalize local VisualToolBench exports into JSONL files.

    Expected input is a JSON/JSONL export that preserves the benchmark schema and
    stores local image paths or image descriptors with a local ``path``/``src``.
    """
    dataset_root = normalized_data_root / "visualtoolbench"
    dataset_root.mkdir(parents=True, exist_ok=True)

    source_file = _discover_visualtoolbench_source(raw_data_root)
    if source_file is None:
        raise FileNotFoundError(
            f"Could not find a VisualToolBench JSON/JSONL export under {raw_data_root}"
        )

    rows = _load_visualtoolbench_rows(source_file)
    if limit:
        rows = rows[:limit]

    records = [
        _normalize_visualtoolbench_record(item, raw_data_root, normalized_data_root, index)
        for index, item in enumerate(rows, start=1)
    ]
    records = [record for record in records if record is not None]

    output_file = dataset_root / "test.jsonl"
    _write_jsonl(output_file, records)
    manifest = {
        "dataset": "visualtoolbench",
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "splits": {
            "test": {
                "count": len(records),
                "source_file": str(source_file),
                "output_file": str(output_file),
            }
        },
    }
    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_visualtoolbench_cases(
    normalized_data_root: Path,
    split: str = "test",
    limit: int = 0,
) -> list[MultiTurnTaskCase]:
    """Load normalized VisualToolBench cases from JSONL."""
    dataset_root = normalized_data_root / "visualtoolbench"
    split_file = dataset_root / f"{split}.jsonl"
    if not split_file.exists():
        raise FileNotFoundError(f"Normalized split not found: {split_file}")

    cases: list[MultiTurnTaskCase] = []
    for index, item in enumerate(load_json_objects(split_file), start=1):
        turns_raw = item.get("turns", [])
        turns: list[MultiTurnTaskTurn] = []
        for turn in turns_raw:
            if not isinstance(turn, dict):
                continue
            turns.append(
                MultiTurnTaskTurn(
                    prompt=str(turn.get("prompt", "")),
                    gold_answer=str(turn.get("gold_answer", "")),
                    image_paths=[str(path) for path in turn.get("image_paths", []) if str(path).strip()],
                    rubric_payload=str(turn.get("rubric_payload", "")),
                    reference_tool_trajectory=str(turn.get("reference_tool_trajectory", "")),
                    metadata=dict(turn.get("metadata") or {}),
                )
            )

        if not turns:
            continue

        cases.append(
            MultiTurnTaskCase(
                case_id=str(item.get("id", f"visualtoolbench_{index}")),
                turncase=str(item.get("turncase", "single-turn")),
                prompt_category=str(item.get("prompt_category", "")),
                eval_focus=str(item.get("eval_focus", "")),
                turns=turns,
                metadata=dict(item.get("metadata") or {}),
            )
        )
        if limit and len(cases) >= limit:
            break

    return cases


def check_chartqa_answer(actual: str, expected: str, prompt: str = "") -> bool:
    """Dataset-specific answer checker for ChartQA-style short answers."""
    actual_text = _normalize_answer_text(actual)
    expected_text = _normalize_answer_text(expected)
    if not actual_text or not expected_text:
        return False

    if actual_text == expected_text:
        return True

    if _contains_expected_text(actual_text, expected_text):
        return True

    actual_number = _parse_number(actual_text)
    expected_number = _parse_number(expected_text)
    if actual_number is not None and expected_number is not None:
        question_hint = prompt.lower()
        candidates = _numeric_candidates_by_intent(actual, expected, question_hint)
        if any(abs(candidate - expected_number) <= 1e-6 for candidate in candidates):
            return True
        return abs(actual_number - expected_number) <= 1e-6

    return False


def check_chartqa_case_answer(actual: str, case: TaskCase) -> bool:
    """TaskCase wrapper for EvolutionLoop answer checking."""
    return check_chartqa_answer(actual, case.gold_answer, prompt=case.prompt)


def score_multiple_choice_answer(actual: str, expected: str, choices: dict[str, str] | None = None) -> float:
    choice_map = choices or {}
    actual_letter = normalize_choice_answer(actual, choice_map)
    expected_letter = normalize_choice_answer(expected, choice_map) or _choice_letter(expected)
    return 1.0 if actual_letter and expected_letter and actual_letter == expected_letter else 0.0


def check_multiple_choice_answer(actual: str, expected: str, choices: dict[str, str] | None = None) -> bool:
    return score_multiple_choice_answer(actual, expected, choices) >= 1.0


def score_mathvista_answer(
    actual: str,
    expected: str,
    prompt: str = "",
    choices: dict[str, str] | None = None,
    answer_type: str = "",
    precision: int | None = None,
    unit: str = "",
) -> float:
    if choices:
        return score_multiple_choice_answer(actual, expected, choices)

    actual_text = _strip_unit(_normalize_answer_text(actual), unit)
    expected_text = _strip_unit(_normalize_answer_text(expected), unit)
    if not actual_text or not expected_text:
        return 0.0

    if actual_text == expected_text or _contains_expected_text(actual_text, expected_text):
        return 1.0

    actual_number = _parse_number(actual_text)
    expected_number = _parse_number(expected_text)
    if actual_number is not None and expected_number is not None:
        if precision is not None:
            try:
                digits = int(precision)
            except (TypeError, ValueError):
                digits = None
            if digits is not None:
                if round(actual_number, digits) == round(expected_number, digits):
                    return 1.0
        question_hint = prompt.lower()
        candidates = _numeric_candidates_by_intent(actual, expected, question_hint)
        if any(abs(candidate - expected_number) <= 1e-6 for candidate in candidates):
            return 1.0
    return 0.0


def check_mathvista_answer(
    actual: str,
    expected: str,
    prompt: str = "",
    choices: dict[str, str] | None = None,
    answer_type: str = "",
    precision: int | None = None,
    unit: str = "",
) -> bool:
    return (
        score_mathvista_answer(
            actual,
            expected,
            prompt=prompt,
            choices=choices,
            answer_type=answer_type,
            precision=precision,
            unit=unit,
        )
        >= 1.0
    )


def score_textvqa_answer(actual: str, answers: list[str]) -> float:
    normalized_actual = _normalize_answer_text(actual)
    if not normalized_actual or not answers:
        return 0.0
    matches = sum(1 for answer in answers if _normalize_answer_text(answer) == normalized_actual)
    return min(1.0, matches / 3.0)


def check_textvqa_case_answer(actual: str, case: TaskCase) -> bool:
    answers = [str(value) for value in case.metadata.get("answers", [])]
    return score_textvqa_answer(actual, answers) >= 1.0


def _discover_chartqa_annotation_files(raw_data_root: Path, split: str) -> list[Path]:
    preferred = [
        raw_data_root / f"{split}.json",
        raw_data_root / f"{split}.jsonl",
        raw_data_root / split / f"{split}.json",
        raw_data_root / split / f"{split}.jsonl",
    ]
    discovered: list[Path] = [path for path in preferred if path.exists()]
    if discovered:
        return discovered

    wildcard_matches = sorted(
        {
            path
            for pattern in [f"**/*{split}*.json", f"**/*{split}*.jsonl"]
            for path in raw_data_root.glob(pattern)
            if path.is_file()
        }
    )
    return wildcard_matches


def _normalize_chartqa_record(
    item: dict[str, Any],
    split: str,
    raw_data_root: Path,
    annotation_file: Path,
    fallback_index: int,
) -> dict[str, Any]:
    raw_metadata = _coerce_record_metadata(item.get("metadata"))
    question = str(
        item.get("question")
        or item.get("query")
        or item.get("prompt")
        or item.get("text")
        or ""
    ).strip()
    answer = str(
        item.get("answer")
        or item.get("label")
        or item.get("gold_answer")
        or item.get("target")
        or ""
    ).strip()
    source_id = str(
        item.get("id")
        or item.get("question_id")
        or item.get("sample_id")
        or item.get("uid")
        or f"{annotation_file.stem}_{fallback_index}"
    )
    image_path = _resolve_chartqa_image_path(item, raw_data_root, annotation_file, split)
    with Image.open(image_path) as image:
        width, height = image.size

    question_type = str(
        item.get("question_type")
        or raw_metadata.get("question_type")
        or item.get("qa_type")
        or _infer_question_type(question)
    )
    answer_type = str(
        item.get("answer_type")
        or raw_metadata.get("answer_type")
        or item.get("label_type")
        or _infer_answer_type(answer)
    )
    chart_type = str(item.get("source") or item.get("type") or raw_metadata.get("type") or "").strip()
    x_values_bbox = item.get("x_values_bbox", raw_metadata.get("x_values_bbox"))
    y_values_bbox = item.get("y_values_bbox", raw_metadata.get("y_values_bbox"))
    figure_bbox = item.get("figure_bbox", raw_metadata.get("figure_bbox"))

    return {
        "id": source_id,
        "problem_id": "chartqa",
        "prompt": question,
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "chartqa",
            "split": split,
            "source_id": source_id,
            "capability_family": "chartqa",
            "question_type": question_type,
            "answer_type": answer_type,
            "image_width": width,
            "image_height": height,
            "chart_type": chart_type,
            "figure_bbox": figure_bbox,
            "x_values_bbox": x_values_bbox if isinstance(x_values_bbox, dict) else {},
            "y_values_bbox": y_values_bbox if isinstance(y_values_bbox, dict) else {},
        },
    }


def _resolve_chartqa_image_path(
    item: dict[str, Any],
    raw_data_root: Path,
    annotation_file: Path,
    split: str,
) -> Path:
    raw_image = str(
        item.get("image_path")
        or item.get("image")
        or item.get("imgname")
        or item.get("img_name")
        or item.get("img")
        or item.get("image_id")
        or ""
    ).strip()
    if not raw_image:
        raise KeyError(f"ChartQA record is missing an image reference: {_summarize_record(item)}")

    candidate = Path(raw_image)
    possibilities: list[Path] = []
    if candidate.is_absolute():
        possibilities.append(candidate)
    else:
        possibilities.extend(
            [
                raw_data_root / candidate,
                annotation_file.parent / candidate,
                raw_data_root / split / candidate,
                raw_data_root / "images" / candidate,
                raw_data_root / split / "images" / candidate,
                raw_data_root / "png" / candidate,
                raw_data_root / split / "png" / candidate,
                raw_data_root / "charts" / candidate,
                raw_data_root / split / "charts" / candidate,
            ]
        )

    if not candidate.suffix:
        expanded: list[Path] = []
        for path in list(possibilities):
            expanded.extend(path.with_suffix(suffix) for suffix in [".png", ".jpg", ".jpeg", ".webp"])
        possibilities.extend(expanded)

    for path in possibilities:
        if path.exists():
            return path.resolve()

    recursive_match = _find_chartqa_image_recursive(raw_data_root, split, candidate)
    if recursive_match is not None:
        return recursive_match

    raise FileNotFoundError(f"Could not resolve ChartQA image '{raw_image}' from {annotation_file}")


def _find_chartqa_image_recursive(raw_data_root: Path, split: str, candidate: Path) -> Path | None:
    """Fallback for official ChartQA layouts where annotations store only the filename."""
    search_name = candidate.name or str(candidate)
    split_root = raw_data_root / split

    search_roots = [split_root, raw_data_root]
    for root in search_roots:
        if not root.exists():
            continue
        matches = sorted(
            path for path in root.rglob(search_name)
            if path.is_file()
        )
        if matches:
            return matches[0].resolve()

        if not candidate.suffix:
            expanded_matches: list[Path] = []
            for suffix in [".png", ".jpg", ".jpeg", ".webp"]:
                expanded_matches.extend(
                    path for path in root.rglob(f"{search_name}{suffix}")
                    if path.is_file()
                )
            if expanded_matches:
                return sorted(expanded_matches)[0].resolve()

    return None


def _normalize_gta_record(
    qid: str,
    item: dict[str, Any],
    raw_data_root: Path,
    toolmeta: dict[str, Any],
) -> dict[str, Any] | None:
    user_query = ""
    dialogs = item.get("dialogs", [])
    for dialog in dialogs:
        if dialog.get("role") == "user":
            user_query = str(dialog.get("content", "")).strip()
            break

    image_paths: list[str] = []
    for file_info in item.get("files", []):
        raw_path = str(file_info.get("path", "")).strip()
        if not raw_path:
            continue
        resolved = (raw_data_root / raw_path).resolve()
        image_paths.append(str(resolved))

    whitelist, blacklist, answer_str = _parse_gta_gold_answer(item.get("gt_answer"))
    if not answer_str.strip():
        return None

    gt_tools = [str(tool.get("name", "")).strip() for tool in item.get("tools", []) if str(tool.get("name", "")).strip()]
    gt_chain = _extract_gta_tool_chain(dialogs)
    tool_category = _classify_gta_tool_category(gt_tools)
    tool_catalog = _build_gta_tool_description(
        [toolmeta[name] for name in gt_tools if name in toolmeta]
        or item.get("tools", [])
    )
    image_refs = "\n".join(f"[Image {i + 1}]: {path}" for i, path in enumerate(image_paths))
    prompt_parts = [user_query]
    if tool_catalog:
        prompt_parts.append(f"You have access to the following tools:\n{tool_catalog}")
    if image_refs:
        prompt_parts.append(f"Images provided:\n{image_refs}")
    prompt = "\n\n".join(part for part in prompt_parts if part)

    return {
        "id": f"gta_{qid}",
        "problem_id": f"gta_{tool_category}",
        "prompt": prompt,
        "answer": answer_str,
        "image_path": image_paths[0] if image_paths else "",
        "metadata": {
            "dataset_name": "gta",
            "source_id": qid,
            "question_type": tool_category,
            "answer_type": "free_form",
            "gt_tools": gt_tools,
            "gt_tool_chain": gt_chain,
            "gt_answer_whitelist": whitelist,
            "gt_answer_blacklist": blacklist,
            "all_image_paths": image_paths,
            "num_tools": len(gt_tools),
            "num_steps": len(gt_chain),
            "tool_category": tool_category,
            "capability_family": f"gta_{tool_category}",
        },
    }


def _parse_gta_gold_answer(gt_answer: Any) -> tuple[list[list[str]], list[list[str]] | None, str]:
    whitelist: list[list[str]]
    blacklist: list[list[str]] | None
    answer_str = ""
    if isinstance(gt_answer, dict):
        raw_whitelist = gt_answer.get("whitelist", [[]])
        whitelist = [[str(item) for item in group] for group in raw_whitelist if isinstance(group, list)]
        blacklist_raw = gt_answer.get("blacklist")
        if isinstance(blacklist_raw, list):
            blacklist = [[str(item) for item in group] for group in blacklist_raw if isinstance(group, list)]
        else:
            blacklist = None
        if whitelist and whitelist[0]:
            answer_str = str(whitelist[0][0])
    elif isinstance(gt_answer, list) and gt_answer:
        whitelist = [[str(gt_answer[0])]]
        blacklist = None
        answer_str = str(gt_answer[0])
    else:
        whitelist = [[]]
        blacklist = None
    return whitelist, blacklist, answer_str


def _build_gta_tool_description(tools: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for tool in tools:
        name = str(tool.get("name", "")).strip()
        if not name:
            continue
        inputs = ", ".join(
            f"{inp.get('name', 'arg')}:{inp.get('type', 'any')}"
            for inp in tool.get("inputs", [])
            if isinstance(inp, dict)
        )
        outputs = ", ".join(
            str(output.get("type", "any"))
            for output in tool.get("outputs", [])
            if isinstance(output, dict)
        )
        description = str(tool.get("description", "")).strip()
        lines.append(f"- {name}({inputs}) -> {outputs or 'any'}: {description}")
    return "\n".join(lines)


def _extract_gta_tool_chain(dialogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for turn in dialogs:
        if turn.get("role") != "assistant":
            continue
        for tool_call in turn.get("tool_calls", []):
            function = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
            chain.append(
                {
                    "tool": str(function.get("name", "")),
                    "arguments": function.get("arguments", {}),
                    "thought": str(turn.get("thought", "")),
                }
            )
    return chain


def _classify_gta_tool_category(tools: list[str]) -> str:
    perception = {"OCR", "ImageDescription", "RegionAttributeDescription", "CountGivenObject", "TextToBbox", "MathOCR"}
    operation = {"DrawBox", "AddText", "GoogleSearch"}
    logic = {"Calculator", "Plot", "Solver"}
    creativity = {"TextToImage", "ImageStylization"}

    tool_set = set(tools)
    categories: list[str] = []
    if tool_set & perception:
        categories.append("perception")
    if tool_set & operation:
        categories.append("operation")
    if tool_set & logic:
        categories.append("logic")
    if tool_set & creativity:
        categories.append("creativity")
    return "+".join(categories) if categories else "unknown"


def _discover_data_files(raw_data_root: Path, include_tokens: list[str]) -> list[Path]:
    include_tokens = [token.lower() for token in include_tokens if token]
    allowed_suffixes = {".json", ".jsonl", ".parquet"}
    matches: list[Path] = []
    for path in raw_data_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        haystack = str(path.relative_to(raw_data_root)).lower()
        if any(token in haystack for token in include_tokens):
            matches.append(path)
    return sorted(dict.fromkeys(matches))


def _load_rows_from_files(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.suffix.lower() == ".parquet":
            rows.extend(_load_parquet_rows(path))
        else:
            loaded = load_json_objects(path)
            rows.extend(_expand_mapping_rows(loaded))
    return [row for row in rows if isinstance(row, dict)]


def _load_parquet_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency is installed on benchmark servers
        raise RuntimeError("pyarrow is required to read parquet benchmark files.") from exc
    table = pq.read_table(path)
    return [dict(row) for row in table.to_pylist()]


def _expand_mapping_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for row in rows:
        if _looks_like_record_mapping(row):
            for key, value in row.items():
                if not isinstance(value, dict):
                    continue
                item = dict(value)
                item.setdefault("id", str(key))
                item.setdefault("pid", str(key))
                item.setdefault("question_id", str(key))
                expanded.append(item)
        else:
            expanded.append(row)
    return expanded


def _extract_semantic_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    for row in rows:
        extracted.extend(_extract_semantic_records_from_value(row))
    return extracted


def _extract_semantic_records_from_value(value: Any, inherited_id: str | None = None) -> list[dict[str, Any]]:
    if isinstance(value, list):
        results: list[dict[str, Any]] = []
        for item in value:
            results.extend(_extract_semantic_records_from_value(item, inherited_id=inherited_id))
        return results

    if not isinstance(value, dict):
        return []

    if _looks_like_semantic_record(value):
        item = dict(value)
        if inherited_id:
            item.setdefault("id", inherited_id)
            item.setdefault("pid", inherited_id)
            item.setdefault("question_id", inherited_id)
        return [item]

    results: list[dict[str, Any]] = []
    for key, nested in value.items():
        key_text = str(key)
        nested_id = inherited_id
        if key_text.isdigit():
            nested_id = key_text
        results.extend(_extract_semantic_records_from_value(nested, inherited_id=nested_id))
    return results


def _looks_like_semantic_record(row: dict[str, Any]) -> bool:
    keys = {str(key) for key in row.keys()}
    prompt_markers = {"question", "prompt", "query", "text"}
    image_markers = {"image", "decoded_image", "image_path", "img", "imgname", "img_name", "image_id", "image_file"}
    answer_markers = {"answer", "label", "gold_answer", "target"}
    return bool(keys & prompt_markers) and bool(keys & answer_markers) and bool(keys & image_markers)


def _looks_like_record_mapping(row: dict[str, Any]) -> bool:
    if not row:
        return False
    values = list(row.values())
    if not values or not all(isinstance(value, dict) for value in values):
        return False
    sample_keys = set()
    for value in values[:5]:
        sample_keys.update(str(key) for key in value.keys())
    semantic_markers = {
        "question",
        "prompt",
        "answer",
        "image",
        "image_path",
        "decoded_image",
        "choices",
        "options",
        "query",
    }
    return bool(sample_keys & semantic_markers)


def _discover_visualtoolbench_source(raw_data_root: Path) -> Path | None:
    preferred_names = [
        "test.parquet",
        "visualtoolbench.jsonl",
        "visualtoolbench.json",
        "test.jsonl",
        "test.json",
    ]
    for name in preferred_names:
        candidate = raw_data_root / name
        if candidate.exists():
            return candidate
    matches = _discover_data_files(raw_data_root, include_tokens=["visualtoolbench", "test"])
    return matches[0] if matches else None


def _normalize_visualtoolbench_record(
    item: dict[str, Any],
    raw_data_root: Path,
    normalized_data_root: Path,
    fallback_index: int,
) -> dict[str, Any] | None:
    turn_prompts = [str(value) for value in item.get("turn_prompts", [])]
    turn_answers = [str(value) for value in item.get("turn_golden_answers", [])]
    rubrics_by_turn = [str(value) for value in item.get("rubrics_by_turn", [])]
    tool_trajectories = [str(value) for value in item.get("turn_tool_trajectories", [])]
    images_by_turn = item.get("images_by_turn", [])

    if not turn_prompts:
        prompt = str(item.get("prompt", item.get("question", ""))).strip()
        if prompt:
            turn_prompts = [prompt]
    if not turn_prompts:
        return None

    num_turns = max(
        len(turn_prompts),
        len(turn_answers),
        len(rubrics_by_turn),
        len(tool_trajectories),
        len(images_by_turn) if isinstance(images_by_turn, list) else 0,
        int(item.get("num_turns", 0) or 0),
    )
    turns: list[dict[str, Any]] = []
    for index in range(num_turns):
        prompt = turn_prompts[index] if index < len(turn_prompts) else ""
        if not prompt.strip():
            continue
        turns.append(
            {
                "prompt": prompt,
                "gold_answer": turn_answers[index] if index < len(turn_answers) else "",
                "rubric_payload": rubrics_by_turn[index] if index < len(rubrics_by_turn) else "",
                "reference_tool_trajectory": tool_trajectories[index] if index < len(tool_trajectories) else "",
                "image_paths": _resolve_visualtoolbench_turn_images(
                    images_by_turn[index] if index < len(images_by_turn) else [],
                    raw_data_root,
                    normalized_data_root,
                    item_id=str(item.get("id", f"visualtoolbench_{fallback_index}")),
                    turn_index=index,
                ),
                "metadata": {
                    "turn_index": index,
                },
            }
        )

    if not turns:
        return None

    return {
        "id": str(item.get("id", f"visualtoolbench_{fallback_index}")),
        "turncase": str(item.get("turncase", "single-turn")),
        "prompt_category": str(item.get("prompt_category", "")),
        "eval_focus": str(item.get("eval_focus", "")),
        "turns": turns,
        "metadata": {
            "dataset_name": "visualtoolbench",
            "num_turns": len(turns),
            "num_images": int(item.get("num_images", 0) or 0),
        },
    }


def _load_visualtoolbench_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".parquet":
        return _load_parquet_rows(path)
    return load_json_objects(path)


def _resolve_visualtoolbench_turn_images(
    value: Any,
    raw_data_root: Path,
    normalized_data_root: Path,
    item_id: str,
    turn_index: int,
) -> list[str]:
    if not isinstance(value, list):
        return []

    resolved: list[str] = []
    assets_root = normalized_data_root / "_assets" / "visualtoolbench" / item_id / f"turn_{turn_index + 1}"
    assets_root.mkdir(parents=True, exist_ok=True)

    for image_index, item in enumerate(value, start=1):
        if isinstance(item, dict):
            image_bytes = item.get("bytes")
            if isinstance(image_bytes, (bytes, bytearray)) and image_bytes:
                suffix = _guess_image_suffix(image_bytes)
                output_path = assets_root / f"image_{image_index}{suffix}"
                if not output_path.exists():
                    output_path.write_bytes(bytes(image_bytes))
                resolved.append(str(output_path.resolve()))
                continue

            path_value = ""
            for key in ("path", "src", "file_name", "filename"):
                candidate = str(item.get(key, "")).strip()
                if candidate:
                    path_value = candidate
                    break
        else:
            path_value = str(item).strip() if isinstance(item, str) else ""

        if not path_value:
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = (raw_data_root / path).resolve()
        if path.exists():
            resolved.append(str(path))
    return resolved


def _guess_image_suffix(image_bytes: bytes | bytearray) -> str:
    header = bytes(image_bytes[:12])
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return ".gif"
    if header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_pseudo_split_dataset(
    dataset_name: str,
    raw_data_root: Path,
    dataset_root: Path,
    records: list[dict[str, Any]],
    source_files: list[Path],
    train_size: int,
    val_size: int,
    source_split: str,
) -> dict[str, Any]:
    ordered = sorted(records, key=lambda row: _stable_hash_key(str(row["id"])))
    train_records = _with_split(ordered[: min(train_size, len(ordered))], "train")
    val_start = len(train_records)
    val_records = _with_split(ordered[val_start: val_start + val_size], "val")

    train_file = dataset_root / "train.jsonl"
    val_file = dataset_root / "val.jsonl"
    _write_jsonl(train_file, train_records)
    _write_jsonl(val_file, val_records)

    manifest = {
        "dataset": dataset_name,
        "raw_data_root": str(raw_data_root),
        "normalized_data_root": str(dataset_root),
        "splits": {
            "train": {
                "count": len(train_records),
                "source_split": source_split,
                "source_files": [str(path) for path in source_files],
                "output_file": str(train_file),
            },
            "val": {
                "count": len(val_records),
                "source_split": source_split,
                "source_files": [str(path) for path in source_files],
                "output_file": str(val_file),
            },
        },
    }
    manifest_path = dataset_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _with_split(records: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for row in records:
        cloned = dict(row)
        metadata = dict(cloned.get("metadata") or {})
        metadata["split"] = split
        cloned["metadata"] = metadata
        updated.append(cloned)
    return updated


def _stable_hash_key(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def _normalize_vstar_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    fallback_index: int,
) -> dict[str, Any]:
    source_id = _string_field(item, ["id", "question_id", "sample_id", "uid"], f"vstar_{fallback_index}")
    prompt = _string_field(item, ["question", "prompt", "query", "text"], "")
    category = _slugify(_string_field(item, ["category", "task", "type"], "generic"))
    choices = _extract_choices(item)
    answer = _normalize_choice_gold(item.get("answer", item.get("label", "")), choices)
    image_path = _materialize_image(item, raw_data_root, assets_root / "train_val", source_id)

    return {
        "id": source_id,
        "problem_id": "vstar",
        "prompt": _append_choices_to_prompt(prompt, choices),
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "vstar",
            "source_id": source_id,
            "capability_family": f"vstar_{category}",
            "category": category,
            "choices": choices,
            "answer_type": "multiple_choice",
        },
    }


def _normalize_hrbench_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    fallback_index: int,
) -> dict[str, Any]:
    source_id = _string_field(item, ["id", "question_id", "sample_id", "uid"], f"hrbench_{fallback_index}")
    prompt = _string_field(item, ["question", "prompt", "query", "text"], "")
    category = _slugify(_string_field(item, ["category", "task", "type"], "generic"))
    cycle_category = _slugify(_string_field(item, ["cycle_category", "cycle", "cycle_type"], "generic"))
    choices = _extract_choices(item)
    answer = _normalize_choice_gold(item.get("answer", item.get("label", "")), choices)
    image_path = _materialize_image(item, raw_data_root, assets_root / "train_val", source_id)

    return {
        "id": source_id,
        "problem_id": "hrbench",
        "prompt": _append_choices_to_prompt(prompt, choices),
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "hrbench",
            "source_id": source_id,
            "capability_family": f"hrbench_{category}",
            "category": category,
            "cycle_category": cycle_category,
            "choices": choices,
            "answer_type": "multiple_choice",
        },
    }


def _normalize_mathvista_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    fallback_index: int,
) -> dict[str, Any]:
    source_id = _string_field(item, ["id", "pid", "question_id", "sample_id", "uid"], f"mathvista_{fallback_index}")
    prompt = _string_field(item, ["question", "prompt", "query", "text"], "")
    source = _slugify(_string_field(item, ["source", "domain", "subject"], "generic"))
    question_type = _slugify(_string_field(item, ["question_type", "task_type"], "generic"))
    answer_type = _slugify(_string_field(item, ["answer_type", "response_type"], _infer_answer_type(str(item.get("answer", "")))))
    precision = item.get("precision")
    unit = _string_field(item, ["unit"], "")
    choices = _extract_choices(item)
    answer = (
        _normalize_choice_gold(item.get("answer", item.get("label", "")), choices)
        if choices else str(item.get("answer", item.get("label", ""))).strip()
    )
    image_path = _materialize_image(item, raw_data_root, assets_root / "train_val", source_id)

    return {
        "id": source_id,
        "problem_id": "mathvista",
        "prompt": _append_choices_to_prompt(prompt, choices),
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "mathvista",
            "source_id": source_id,
            "capability_family": f"mathvista_{source}_{question_type}",
            "source": source,
            "question_type": question_type,
            "answer_type": answer_type,
            "precision": precision,
            "unit": unit,
            "choices": choices,
        },
    }


def _normalize_refocus_tablevqa_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    fallback_index: int,
) -> dict[str, Any]:
    raw_metadata = _coerce_record_metadata(item.get("metadata"))
    source_id = _string_field(item, ["id", "qid", "question_id", "sample_id", "uid"], f"refocus_tablevqa_{fallback_index}")
    prompt = _string_field(item, ["question", "prompt", "query", "text"], "")
    source = _slugify(_string_field(item, ["source", "dataset", "domain", "task"], "tablevqa"))
    question_type = _slugify(_string_field(item, ["question_type", "task_type", "type"], _infer_question_type(prompt)))
    answer = str(item.get("answer", item.get("label", item.get("gold_answer", item.get("target", ""))))).strip()
    answer_type = _slugify(_string_field(item, ["answer_type", "response_type"], _infer_answer_type(answer)))
    image_path = _materialize_image(item, raw_data_root, assets_root / "train_val", source_id)
    columns_bbox = item.get("columns_bbox", raw_metadata.get("columns_bbox"))
    row_starters_bbox = (
        item.get("rows_bbox")
        or item.get("row_starters")
        or raw_metadata.get("rows_bbox")
        or raw_metadata.get("row_starters")
    )
    figure_bbox = item.get("figure_bbox", raw_metadata.get("figure_bbox"))

    table_title = _string_field(item, ["title", "table_title", "caption"], "")
    if table_title and table_title.lower() not in prompt.lower():
        prompt = f"{prompt}\n\nTable title: {table_title}".strip()

    return {
        "id": source_id,
        "problem_id": "refocus_tablevqa",
        "prompt": prompt,
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "refocus_tablevqa",
            "source_id": source_id,
            "capability_family": f"refocus_tablevqa_{source}_{question_type}",
            "source": source,
            "question_type": question_type,
            "answer_type": answer_type,
            "metric_type": "accuracy",
            "figure_bbox": figure_bbox,
            "columns_bbox": columns_bbox if isinstance(columns_bbox, dict) else {},
            "row_starters": row_starters_bbox if isinstance(row_starters_bbox, dict) else {},
        },
    }


def _normalize_refocus_chart_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    fallback_index: int,
) -> dict[str, Any]:
    raw_metadata = _coerce_record_metadata(item.get("metadata"))
    source_id = _string_field(
        item,
        ["id", "qid", "question_id", "sample_id", "uid"],
        f"refocus_chart_{fallback_index}",
    )

    extra_info = item.get("extra_info") if isinstance(item.get("extra_info"), dict) else {}
    reward_model = item.get("reward_model") if isinstance(item.get("reward_model"), dict) else {}
    prompt = _string_field(extra_info, ["question"], "")
    if not prompt:
        raw_prompt = item.get("prompt")
        if isinstance(raw_prompt, list):
            for message in raw_prompt:
                if not isinstance(message, dict):
                    continue
                if str(message.get("role", "")).strip().lower() == "user":
                    content = str(message.get("content", "")).strip()
                    if content:
                        marker = "USER REQUEST:"
                        if marker in content:
                            content = content.split(marker, 1)[-1].strip()
                        prompt = content
                        break
        if not prompt:
            prompt = _string_field(item, ["question", "query", "text"], "")
    answer = _string_field(
        reward_model,
        ["ground_truth", "answer"],
        _string_field(item, ["answer", "label", "gold_answer", "target"], _string_field(extra_info, ["answer"], "")),
    )

    image_item = dict(item)
    if image_item.get("images") and isinstance(image_item["images"], list):
        first_image = image_item["images"][0]
        if first_image is not None:
            image_item["image"] = first_image
    elif image_item.get("edited_image") is not None:
        image_item["image"] = image_item["edited_image"]
    image_path = _materialize_image(image_item, raw_data_root, assets_root, source_id)

    source = _slugify(_string_field(item, ["source", "dataset", "domain", "task"], "refocus_chart"))
    question_type = _slugify(_string_field(item, ["question_type", "task_type", "type"], _infer_question_type(prompt)))
    answer_type = _slugify(_string_field(item, ["answer_type", "response_type"], _infer_answer_type(answer)))

    tool_metadata: dict[str, Any] = {}
    tools_kwargs = extra_info.get("tools_kwargs") if isinstance(extra_info, dict) else None
    if isinstance(tools_kwargs, dict):
        raw_tool_metadata = tools_kwargs.get("metadata")
        if isinstance(raw_tool_metadata, str):
            try:
                parsed = json.loads(raw_tool_metadata)
                if isinstance(parsed, dict):
                    tool_metadata = parsed
            except json.JSONDecodeError:
                tool_metadata = {}
        elif isinstance(raw_tool_metadata, dict):
            tool_metadata = raw_tool_metadata

    x_values_bbox = tool_metadata.get("x_values_bbox", item.get("x_values_bbox", raw_metadata.get("x_values_bbox")))
    y_values_bbox = tool_metadata.get("y_values_bbox", item.get("y_values_bbox", raw_metadata.get("y_values_bbox")))
    figure_bbox = tool_metadata.get("figure_bbox", item.get("figure_bbox", raw_metadata.get("figure_bbox")))

    return {
        "id": source_id,
        "problem_id": "refocus_chart",
        "prompt": prompt,
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "refocus_chart",
            "split": _string_field(item, ["split"], _string_field(extra_info, ["split"], "")),
            "source_id": source_id,
            "capability_family": f"refocus_chart_{source}_{question_type}",
            "source": source,
            "question_type": question_type,
            "answer_type": answer_type,
            "metric_type": "accuracy",
            "reward_style": _string_field(reward_model, ["style"], ""),
            "figure_bbox": figure_bbox,
            "x_values": [str(value) for value in item.get("x_values", []) if str(value).strip()],
            "y_values": [str(value) for value in item.get("y_values", []) if str(value).strip()],
            "x_values_bbox": x_values_bbox if isinstance(x_values_bbox, dict) else {},
            "y_values_bbox": y_values_bbox if isinstance(y_values_bbox, dict) else {},
        },
    }


def _normalize_textvqa_record(
    item: dict[str, Any],
    raw_data_root: Path,
    assets_root: Path,
    split: str,
    fallback_index: int,
) -> dict[str, Any]:
    source_id = _string_field(item, ["id", "question_id", "sample_id", "uid"], f"textvqa_{split}_{fallback_index}")
    prompt = _string_field(item, ["question", "prompt", "query", "text"], "")
    answers = _extract_answers(item)
    ocr_tokens = _extract_ocr_tokens(item)
    image_path = _materialize_image(item, raw_data_root, assets_root / split, source_id)
    majority_answer = _majority_answer(answers)

    return {
        "id": source_id,
        "problem_id": "textvqa",
        "prompt": prompt,
        "answer": majority_answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "textvqa",
            "split": split,
            "source_id": source_id,
            "capability_family": "textvqa_ocr",
            "answers": answers,
            "ocr_tokens": ocr_tokens,
            "answer_type": "vqa_accuracy",
        },
    }


def _string_field(item: dict[str, Any], keys: list[str], default: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _extract_choices(item: dict[str, Any]) -> dict[str, str]:
    letter_columns = {
        label: str(item.get(label, "")).strip()
        for label in ("A", "B", "C", "D")
        if str(item.get(label, "")).strip()
    }
    if letter_columns:
        return dict(sorted(letter_columns.items()))

    raw = item.get("choices", item.get("options", item.get("candidates", item.get("answers"))))
    if raw is None or isinstance(raw, str):
        return {}
    if isinstance(raw, dict):
        result: dict[str, str] = {}
        for key, value in raw.items():
            label = _choice_letter(str(key))
            if label and str(value).strip():
                result[label] = str(value).strip()
        return dict(sorted(result.items()))
    if isinstance(raw, list):
        result = {}
        for index, value in enumerate(raw):
            label = chr(ord("A") + index)
            if isinstance(value, dict):
                text = _string_field(value, ["text", "label", "answer", "content"], "")
            else:
                text = str(value).strip()
            if text:
                result[label] = text
        return result
    return {}


def _coerce_record_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _extract_answers(item: dict[str, Any]) -> list[str]:
    raw = item.get("answers", item.get("answer_list", item.get("gt_answers", [])))
    if isinstance(raw, list):
        answers = [str(value).strip() for value in raw if str(value).strip()]
        if answers:
            return answers
    answer = str(item.get("answer", item.get("label", ""))).strip()
    return [answer] if answer else []


def _extract_ocr_tokens(item: dict[str, Any]) -> list[str]:
    raw = item.get("ocr_tokens", item.get("ocr", item.get("tokens", [])))
    if isinstance(raw, list):
        tokens = []
        for value in raw:
            if isinstance(value, dict):
                text = _string_field(value, ["text", "token", "word"], "")
            else:
                text = str(value).strip()
            if text:
                tokens.append(text)
        return tokens
    return []


def _majority_answer(answers: list[str]) -> str:
    if not answers:
        return ""
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    for answer in answers:
        normalized = _normalize_answer_text(answer)
        counts[normalized] = counts.get(normalized, 0) + 1
        originals.setdefault(normalized, answer)
    best_key = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return originals[best_key]


def _append_choices_to_prompt(prompt: str, choices: dict[str, str]) -> str:
    if not choices:
        return prompt
    lines = [prompt.strip(), "", "Choices:"]
    lines.extend(f"{label}. {text}" for label, text in sorted(choices.items()))
    return "\n".join(lines).strip()


def _normalize_choice_gold(value: Any, choices: dict[str, str]) -> str:
    answer = str(value).strip()
    if not answer:
        return answer
    resolved = normalize_choice_answer(answer, choices)
    return resolved or answer


def normalize_choice_answer(value: str, choices: dict[str, str]) -> str:
    text = str(value).strip()
    if not text:
        return ""

    letter = _choice_letter(text)
    if letter and (not choices or letter in choices):
        return letter

    normalized = _normalize_answer_text(text)
    for label, choice_text in choices.items():
        if normalized == _normalize_answer_text(choice_text):
            return label
        if _contains_expected_text(normalized, _normalize_answer_text(choice_text)):
            return label
    return ""


def _choice_letter(text: str) -> str:
    match = re.search(r"\b([A-D])\b", str(text).strip().upper())
    if match:
        return match.group(1)
    compact = re.sub(r"[^A-Z]", "", str(text).upper())
    return compact if compact in {"A", "B", "C", "D"} else ""


def _materialize_image(item: dict[str, Any], raw_data_root: Path, assets_dir: Path, source_id: str) -> Path:
    image_value = (
        item.get("image")
        or item.get("decoded_image")
        or item.get("image_path")
        or item.get("img")
        or item.get("imgname")
        or item.get("img_name")
        or item.get("image_id")
        or item.get("image_file")
    )
    if image_value is None:
        raise KeyError(f"Record is missing image data: {_summarize_record(item)}")

    if isinstance(image_value, dict):
        raw_path = image_value.get("path")
        raw_bytes = image_value.get("bytes")
        if raw_path:
            resolved = _resolve_image_path(raw_path, raw_data_root)
            if resolved is not None:
                return resolved
        if raw_bytes:
            return _save_image_bytes(raw_bytes, assets_dir, source_id)

    if isinstance(image_value, (bytes, bytearray)):
        return _save_image_bytes(bytes(image_value), assets_dir, source_id)

    text_value = str(image_value).strip()
    if text_value:
        if _looks_like_base64_image(text_value):
            return _save_image_bytes(text_value, assets_dir, source_id)
        resolved = _resolve_image_path(text_value, raw_data_root)
        if resolved is not None:
            return resolved

    raise FileNotFoundError(
        f"Could not materialize image for record {source_id}. "
        f"image_field={_safe_repr(image_value)}"
    )


def _resolve_image_path(raw_value: str, raw_data_root: Path) -> Path | None:
    raw_text = str(raw_value).strip()
    if not raw_text or _looks_like_base64_image(raw_text) or len(raw_text) > 512:
        return None

    candidate = Path(raw_text)
    possibilities: list[Path] = []
    if candidate.is_absolute():
        possibilities.append(candidate)
    else:
        possibilities.extend(
            [
                raw_data_root / candidate,
                raw_data_root / "images" / candidate,
                raw_data_root / "imgs" / candidate,
                raw_data_root / "images" / candidate.name,
                raw_data_root / "imgs" / candidate.name,
            ]
        )
    for path in possibilities:
        try:
            if path.exists():
                return path.resolve()
        except OSError:
            continue
    if candidate.name:
        matches = sorted(path for path in raw_data_root.rglob(candidate.name) if path.is_file())
        if matches:
            return matches[0].resolve()
    if str(candidate):
        relative_parts = [part for part in candidate.parts if part not in {"", ".", ".."}]
        if relative_parts:
            target_suffix = "/".join(relative_parts)
            suffix_matches = sorted(
                path for path in raw_data_root.rglob("*")
                if path.is_file() and str(path.relative_to(raw_data_root)).endswith(target_suffix)
            )
            if suffix_matches:
                return suffix_matches[0].resolve()
    return None


def _save_image_bytes(raw_value: Any, assets_dir: Path, source_id: str) -> Path:
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_path = assets_dir / f"{_slugify(source_id)}.png"
    if output_path.exists():
        return output_path.resolve()

    if isinstance(raw_value, str):
        payload = raw_value.split(",", 1)[-1]
        data = base64.b64decode(payload)
    else:
        data = bytes(raw_value)
    image = Image.open(io.BytesIO(data))
    if image.mode not in {"RGB", "RGBA", "L"}:
        image = image.convert("RGB")
    image.save(output_path)
    return output_path.resolve()


def _looks_like_base64_image(value: str) -> bool:
    text = str(value).strip()
    return text.startswith("data:image/") or len(text) > 100


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return cleaned.strip("_") or "generic"


def _summarize_record(item: dict[str, Any]) -> str:
    summary_keys = ["id", "question_id", "sample_id", "uid", "question", "prompt", "image_path", "imgname", "img_name"]
    summary: dict[str, str] = {}
    for key in summary_keys:
        if key not in item:
            continue
        summary[key] = _safe_repr(item.get(key))
    if not summary:
        summary["keys"] = ",".join(sorted(item.keys())[:20])
    return json.dumps(summary, ensure_ascii=False)


def _safe_repr(value: Any, max_len: int = 120) -> str:
    if value is None:
        return "None"
    if isinstance(value, (bytes, bytearray)):
        return f"<bytes len={len(value)}>"
    if isinstance(value, dict):
        return f"<dict keys={sorted(value.keys())[:10]}>"
    if isinstance(value, list):
        return f"<list len={len(value)}>"
    text = str(value).strip().replace("\n", " ")
    if len(text) > max_len:
        return f"{text[:max_len]}...<len={len(text)}>"
    return text


def _infer_question_type(question: str) -> str:
    text = question.lower()
    if any(token in text for token in ["highest", "lowest", "maximum", "minimum"]):
        return "extrema"
    if any(token in text for token in ["how many", "total", "sum"]):
        return "count_or_total"
    if any(token in text for token in ["compare", "difference", "more than", "less than"]):
        return "comparison"
    return "generic"


def _infer_answer_type(answer: str) -> str:
    if _parse_number(answer) is not None:
        return "numeric"
    if answer.strip().lower() in {"yes", "no", "true", "false"}:
        return "boolean"
    return "string"


def _normalize_answer_text(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.replace(",", "")
    return text.strip(" .")


def _strip_unit(text: str, unit: str) -> str:
    normalized_unit = _normalize_answer_text(unit)
    if not normalized_unit:
        return text
    if text.endswith(normalized_unit):
        text = text[: -len(normalized_unit)].strip()
    return text.strip()


def _contains_expected_text(actual_text: str, expected_text: str) -> bool:
    """Check whether the normalized expected answer appears as a standalone span."""
    if not expected_text:
        return False

    if " " in expected_text:
        return expected_text in actual_text

    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(expected_text)}(?![a-z0-9])")
    return bool(pattern.search(actual_text))


def _numeric_candidates_by_intent(actual: str, expected: str, question_hint: str) -> list[float]:
    """Extract candidate numeric answers, biased by the question intent."""
    candidates = _extract_numeric_tokens(actual)
    if not candidates:
        return []

    expected_number = _parse_number(_normalize_answer_text(expected))
    expected_is_year = _looks_like_year(expected_number)
    asks_for_year = _question_asks_for_year(question_hint) or expected_is_year
    asks_for_ratio = _question_asks_for_ratio(question_hint)

    year_values = [value for value, raw in candidates if _looks_like_year_token(raw)]
    non_year_values = [value for value, raw in candidates if not _looks_like_year_token(raw)]

    if asks_for_year:
        return year_values or [value for value, _ in candidates]

    if asks_for_ratio:
        return non_year_values or [value for value, _ in candidates]

    if expected_number is not None and not expected_is_year and non_year_values:
        return non_year_values + year_values

    return [value for value, _ in candidates]


def _extract_numeric_tokens(text: str) -> list[tuple[float, str]]:
    """Extract numeric spans in order of appearance."""
    matches = re.findall(r"[-+]?\d+(?:\.\d+)?", str(text).replace(",", ""))
    tokens: list[tuple[float, str]] = []
    for raw in matches:
        try:
            tokens.append((float(raw), raw))
        except ValueError:
            continue
    return tokens


def _looks_like_year(value: float | None) -> bool:
    if value is None:
        return False
    return float(int(value)) == value and 1500 <= value <= 2100


def _looks_like_year_token(raw: str) -> bool:
    if not re.fullmatch(r"\d{4}", raw):
        return False
    value = int(raw)
    return 1500 <= value <= 2100


def _question_asks_for_year(question_hint: str) -> bool:
    return any(
        phrase in question_hint
        for phrase in [
            "what year",
            "in what year",
            "which year",
            "year did",
            "year was",
        ]
    )


def _question_asks_for_ratio(question_hint: str) -> bool:
    return any(
        phrase in question_hint
        for phrase in [
            "what percentage",
            "what percent",
            "percentage of",
            "percent of",
            "how much",
            "how many",
            "what was the value",
            "what is the value",
        ]
    )


def _parse_number(value: str) -> float | None:
    cleaned = value.strip().lower().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        pass

    match = re.search(r"[-+]?\d*\.?\d+", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
