"""Dataset normalization and loading utilities for structured benchmarks."""

from __future__ import annotations

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
