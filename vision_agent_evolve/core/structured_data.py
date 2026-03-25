"""Dataset normalization and loading utilities for structured benchmarks."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from .types import TaskCase


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
) -> dict[str, Any]:
    """Normalize V* benchmark data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "vstar"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "vstar"
    source_files = _discover_data_files(raw_data_root, include_tokens=["test"])
    if not source_files:
        raise FileNotFoundError(f"Could not find VStar data files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
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
) -> dict[str, Any]:
    """Normalize HRBench 4K data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "hrbench"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "hrbench"
    source_files = _discover_data_files(raw_data_root, include_tokens=["4k", "hrbench"])
    if not source_files:
        raise FileNotFoundError(f"Could not find HRBench data files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
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
) -> dict[str, Any]:
    """Normalize MathVista testmini data into pseudo train/val JSONL files."""
    dataset_root = normalized_data_root / "mathvista"
    dataset_root.mkdir(parents=True, exist_ok=True)
    assets_root = normalized_data_root / "_assets" / "mathvista"
    source_files = _discover_data_files(raw_data_root, include_tokens=["testmini", "mathvista"])
    if not source_files:
        raise FileNotFoundError(f"Could not find MathVista testmini files under {raw_data_root}")

    rows = _load_rows_from_files(source_files)
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


def normalize_textvqa_dataset(
    raw_data_root: Path,
    normalized_data_root: Path,
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
        or item.get("qa_type")
        or _infer_question_type(question)
    )
    answer_type = str(
        item.get("answer_type")
        or item.get("label_type")
        or _infer_answer_type(answer)
    )

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
        raise KeyError(f"ChartQA record is missing an image reference: {item}")

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
            rows.extend(load_json_objects(path))
    return [row for row in rows if isinstance(row, dict)]


def _load_parquet_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - dependency is installed on benchmark servers
        raise RuntimeError("pyarrow is required to read parquet benchmark files.") from exc
    table = pq.read_table(path)
    return [dict(row) for row in table.to_pylist()]


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
        raise KeyError(f"Record is missing image data: {item}")

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
        resolved = _resolve_image_path(text_value, raw_data_root)
        if resolved is not None:
            return resolved
        if _looks_like_base64_image(text_value):
            return _save_image_bytes(text_value, assets_dir, source_id)

    raise FileNotFoundError(f"Could not materialize image for record {source_id}")


def _resolve_image_path(raw_value: str, raw_data_root: Path) -> Path | None:
    candidate = Path(str(raw_value))
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
        if path.exists():
            return path.resolve()
    if candidate.name:
        matches = sorted(path for path in raw_data_root.rglob(candidate.name) if path.is_file())
        if matches:
            return matches[0].resolve()
    return None


def _save_image_bytes(raw_value: Any, assets_dir: Path, source_id: str) -> Path:
    if isinstance(raw_value, str):
        payload = raw_value.split(",", 1)[-1]
        data = base64.b64decode(payload)
    else:
        data = bytes(raw_value)
    image = Image.open(io.BytesIO(data))
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_path = assets_dir / f"{_slugify(source_id)}.png"
    image.save(output_path)
    return output_path.resolve()


def _looks_like_base64_image(value: str) -> bool:
    text = str(value).strip()
    return text.startswith("data:image/") or len(text) > 100


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    return cleaned.strip("_") or "generic"


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
