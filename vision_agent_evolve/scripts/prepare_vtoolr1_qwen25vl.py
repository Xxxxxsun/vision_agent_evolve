"""Prepare VTool-R1 comparison data for Qwen2.5-VL API experiments."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image


CHART_SOURCE_DIR = Path("data/chartqa_vcot")
TABLE_SOURCE_FILE = "tablevqa_wbb.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize VTool-R1 ChartQA/TableVQA data into TaskCase JSONL.")
    parser.add_argument("--vtool-root", default="/root/VTool-R1", help="Local VTool-R1 repo/data root.")
    parser.add_argument(
        "--refocus-root",
        default="/root/vqa_datasets/datasets/refocus_hf",
        help="Local ReFOCUS HF export root containing test_data_with_bounding_box.",
    )
    parser.add_argument(
        "--normalized-data-root",
        default="./datasets/structured_vtoolr1_qwen25vl",
        help="Output root for normalized chartqa/refocus_tablevqa JSONL.",
    )
    parser.add_argument("--chart-split", action="append", default=[], help="ChartQA split to normalize.")
    parser.add_argument("--table-train-size", type=int, default=200)
    parser.add_argument("--table-test-size", type=int, default=0, help="0 means use all remaining rows.")
    parser.add_argument("--table-source-file", default=TABLE_SOURCE_FILE)
    args = parser.parse_args()

    vtool_root = Path(args.vtool_root).resolve()
    refocus_root = Path(args.refocus_root).resolve()
    normalized_root = Path(args.normalized_data_root).resolve()

    manifest = {
        "dataset_family": "vtoolr1_qwen25vl",
        "vtool_root": str(vtool_root),
        "refocus_root": str(refocus_root),
        "normalized_data_root": str(normalized_root),
        "chartqa": normalize_chartqa(
            vtool_root=vtool_root,
            normalized_root=normalized_root,
            splits=args.chart_split or ["train", "val", "test"],
        ),
        "refocus_tablevqa": normalize_tablevqa(
            vtool_root=vtool_root,
            refocus_root=refocus_root,
            normalized_root=normalized_root,
            source_file_name=args.table_source_file,
            train_size=args.table_train_size,
            test_size=args.table_test_size,
        ),
    }
    manifest_path = normalized_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def normalize_chartqa(vtool_root: Path, normalized_root: Path, splits: list[str]) -> dict[str, Any]:
    source_dir = vtool_root / CHART_SOURCE_DIR
    if not source_dir.exists():
        raise FileNotFoundError(f"VTool-R1 ChartQA source directory not found: {source_dir}")

    dataset_root = normalized_root / "chartqa"
    dataset_root.mkdir(parents=True, exist_ok=True)
    split_payload: dict[str, Any] = {}

    for split in splits:
        source_file = source_dir / f"{split}.jsonl"
        if not source_file.exists():
            continue
        records = [
            _normalize_chart_record(row, vtool_root, split, index)
            for index, row in enumerate(_load_jsonl(source_file), start=1)
        ]
        output_file = dataset_root / f"{split}.jsonl"
        _write_jsonl(output_file, records)
        split_payload[split] = {
            "count": len(records),
            "source_file": str(source_file),
            "output_file": str(output_file),
        }

    if "train" not in split_payload or "test" not in split_payload:
        raise FileNotFoundError(f"Expected train/test ChartQA JSONL files under {source_dir}")

    manifest = {
        "dataset": "chartqa",
        "source": "VTool-R1 chartqa_vcot",
        "raw_data_root": str(vtool_root),
        "normalized_data_root": str(dataset_root),
        "splits": split_payload,
    }
    (dataset_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def normalize_tablevqa(
    vtool_root: Path,
    refocus_root: Path,
    normalized_root: Path,
    source_file_name: str,
    train_size: int,
    test_size: int,
) -> dict[str, Any]:
    source_file = _find_refocus_bbox_dir(refocus_root) / source_file_name
    if not source_file.exists():
        raise FileNotFoundError(f"ReFOCUS/TableVQA source file not found: {source_file}")

    dataset_root = normalized_root / "refocus_tablevqa"
    dataset_root.mkdir(parents=True, exist_ok=True)
    raw_rows = _load_mapping_json(source_file)
    all_records = [
        _normalize_table_record(row, vtool_root, index)
        for index, row in enumerate(raw_rows, start=1)
    ]
    all_records = sorted(all_records, key=lambda row: str(row["id"]))

    train_records = _with_split(all_records[: min(train_size, len(all_records))], "train")
    remaining = all_records[len(train_records) :]
    test_records = _with_split(remaining[:test_size] if test_size else remaining, "test")

    train_file = dataset_root / "train.jsonl"
    test_file = dataset_root / "test.jsonl"
    _write_jsonl(train_file, train_records)
    _write_jsonl(test_file, test_records)

    manifest = {
        "dataset": "refocus_tablevqa",
        "source": source_file_name,
        "raw_data_root": str(refocus_root),
        "image_root": str(vtool_root),
        "normalized_data_root": str(dataset_root),
        "splits": {
            "train": {"count": len(train_records), "source_file": str(source_file), "output_file": str(train_file)},
            "test": {"count": len(test_records), "source_file": str(source_file), "output_file": str(test_file)},
        },
        "split_note": "TableVQA source is a held-out VTool-R1/Refocus table file; train/test are deterministic pseudo-splits for training-free evolution experiments.",
    }
    (dataset_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _normalize_chart_record(row: dict[str, Any], vtool_root: Path, split: str, index: int) -> dict[str, Any]:
    source_id = str(row.get("id") or f"chartqa_{split}_{index}").strip()
    question = str(row.get("question") or row.get("query") or row.get("prompt") or "").strip()
    answer = str(row.get("answer") or row.get("label") or "").strip()
    image_path = _resolve_required_path(vtool_root, str(row.get("image") or row.get("image_path") or ""))
    width, height = _image_size(image_path)

    x_values = [str(value) for value in row.get("x_values", []) if str(value).strip()]
    y_values = [str(value) for value in row.get("y_values", []) if str(value).strip()]
    x_values_bbox = _bbox_mapping(x_values, row.get("x_values_bbox"), width, height)
    y_values_bbox = _bbox_mapping(y_values, row.get("y_values_bbox"), width, height)

    return {
        "id": f"{split}_{source_id}",
        "problem_id": "chartqa",
        "prompt": question,
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "chartqa",
            "split": split,
            "source_id": source_id,
            "capability_family": "chartqa",
            "source": str(row.get("source") or ""),
            "question_type": _infer_question_type(question),
            "answer_type": _infer_answer_type(answer),
            "image_width": width,
            "image_height": height,
            "figure_bbox": _coerce_bbox(row.get("figure_bbox"), width, height),
            "x_values": x_values,
            "y_values": y_values,
            "x_values_bbox": x_values_bbox,
            "y_values_bbox": y_values_bbox,
        },
    }


def _normalize_table_record(row: dict[str, Any], vtool_root: Path, index: int) -> dict[str, Any]:
    source_id = str(row.get("figure_id") or row.get("id") or f"tablevqa_{index}").strip()
    question = str(row.get("query") or row.get("question") or row.get("prompt") or "").strip()
    answer = str(row.get("answer") or row.get("label") or "").strip()
    image_path = _resolve_required_path(vtool_root, str(row.get("figure_path") or row.get("image") or ""))
    width, height = _image_size(image_path)

    column_headers = [str(value) for value in row.get("column_headers", []) if str(value).strip()]
    row_starters = [str(value) for value in row.get("row_starters", []) if str(value).strip()]
    columns_bbox = _bbox_mapping(column_headers, row.get("columns_bbox"), width, height)
    rows_bbox = _bbox_mapping(row_starters, row.get("rows_bbox"), width, height)

    table_title = str(row.get("title") or row.get("caption") or "").strip()
    prompt = question
    if table_title and table_title.lower() not in prompt.lower():
        prompt = f"{prompt}\n\nTable title: {table_title}".strip()

    return {
        "id": f"table_{source_id}",
        "problem_id": "refocus_tablevqa",
        "prompt": prompt,
        "answer": answer,
        "image_path": str(image_path),
        "metadata": {
            "dataset_name": "refocus_tablevqa",
            "split": str(row.get("split") or "test"),
            "source_id": source_id,
            "capability_family": "refocus_tablevqa_table",
            "source": "tablevqa_wbb",
            "question_type": _infer_question_type(question),
            "answer_type": _infer_answer_type(answer),
            "image_width": width,
            "image_height": height,
            "figure_bbox": _coerce_bbox(row.get("table_bbox"), width, height),
            "columns": column_headers,
            "row_starters": rows_bbox,
            "row_labels": row_starters,
            "columns_bbox": columns_bbox,
        },
    }


def _bbox_mapping(labels: list[str], raw_bbox: Any, width: int, height: int) -> dict[str, dict[str, int]]:
    boxes = _bbox_list(raw_bbox)
    result: dict[str, dict[str, int]] = {}
    used = Counter()
    for label, box in zip(labels, boxes):
        normalized_label = label.strip()
        if not normalized_label:
            continue
        used[normalized_label] += 1
        key = normalized_label if used[normalized_label] == 1 else f"{normalized_label}#{used[normalized_label]}"
        coerced = _coerce_bbox(box, width, height)
        if coerced:
            result[key] = coerced
    return result


def _bbox_list(raw_bbox: Any) -> list[Any]:
    if isinstance(raw_bbox, list):
        return raw_bbox
    if isinstance(raw_bbox, dict):
        if all(key in raw_bbox for key in ("x1", "y1", "x2", "y2")) and all(
            isinstance(raw_bbox.get(key), list) for key in ("x1", "y1", "x2", "y2")
        ):
            return [
                {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
                for x1, y1, x2, y2 in zip(raw_bbox["x1"], raw_bbox["y1"], raw_bbox["x2"], raw_bbox["y2"])
            ]
        return list(raw_bbox.values())
    return []


def _coerce_bbox(raw_bbox: Any, width: int, height: int) -> dict[str, int]:
    if not isinstance(raw_bbox, dict):
        return {}
    try:
        x1 = float(raw_bbox["x1"])
        y1 = float(raw_bbox["y1"])
        x2 = float(raw_bbox["x2"])
        y2 = float(raw_bbox["y2"])
    except (KeyError, TypeError, ValueError):
        return {}

    if max(abs(x1), abs(y1), abs(x2), abs(y2)) <= 1.5:
        x1, x2 = x1 * width, x2 * width
        y1, y2 = y1 * height, y2 * height

    return {
        "x1": int(round(max(0, min(width, x1)))),
        "y1": int(round(max(0, min(height, y1)))),
        "x2": int(round(max(0, min(width, x2)))),
        "y2": int(round(max(0, min(height, y2)))),
    }


def _find_refocus_bbox_dir(refocus_root: Path) -> Path:
    candidates = sorted(path for path in refocus_root.glob("test_data_with_bounding_box*") if path.is_dir())
    if not candidates:
        raise FileNotFoundError(f"Could not find test_data_with_bounding_box directory under {refocus_root}")
    return candidates[0]


def _resolve_required_path(root: Path, raw_value: str) -> Path:
    raw_value = raw_value.strip()
    if not raw_value:
        raise FileNotFoundError("Missing image path in source record.")
    path = Path(raw_value)
    candidates = [path] if path.is_absolute() else [root / path, root / path.name]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Could not resolve image path {raw_value!r} under {root}")


def _image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _load_mapping_json(path: Path) -> list[dict[str, Any]]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        rows: list[dict[str, Any]] = []
        for key, value in parsed.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("id", str(key))
                row.setdefault("figure_id", str(key))
                rows.append(row)
        return rows
    return []


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _with_split(records: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for record in records:
        cloned = dict(record)
        metadata = dict(cloned.get("metadata") or {})
        metadata["split"] = split
        cloned["metadata"] = metadata
        updated.append(cloned)
    return updated


def _infer_question_type(question: str) -> str:
    lowered = question.lower()
    if any(token in lowered for token in ["how many", "number of", "count"]):
        return "count_or_total"
    if any(token in lowered for token in ["difference", "more than", "less than", "average", "sum"]):
        return "computed_numeric"
    if any(token in lowered for token in ["true", "false", "yes", "no"]):
        return "boolean"
    return "generic"


def _infer_answer_type(answer: str) -> str:
    text = answer.strip().replace(",", "")
    if not text:
        return "empty"
    try:
        float(text)
        return "numeric"
    except ValueError:
        pass
    if text.lower() in {"yes", "no", "true", "false", "0", "1"}:
        return "boolean"
    return "string"


if __name__ == "__main__":
    main()
