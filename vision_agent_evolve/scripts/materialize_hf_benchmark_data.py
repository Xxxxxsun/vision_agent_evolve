"""Download and materialize benchmark datasets from Hugging Face to stable local paths."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _save_image(image_obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image_to_save = image_obj
    if path.suffix.lower() in {".jpg", ".jpeg"} and getattr(image_obj, "mode", "") != "RGB":
        image_to_save = image_obj.convert("RGB")
    image_to_save.save(path)


def _write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def materialize_chartqa(output_root: Path, splits: tuple[str, ...] = ("train", "val", "test")) -> dict:
    from datasets import load_dataset

    summary: dict[str, dict] = {}
    for split in splits:
        dataset = load_dataset("HuggingFaceM4/ChartQA", split=split)
        rows: list[dict] = []
        for index, item in enumerate(dataset):
            source_id = f"{split}_{index:06d}"
            image_rel = f"{split}/png/{source_id}.png"
            image_path = output_root / image_rel
            if not image_path.exists():
                _save_image(item["image"], image_path)
            label = item.get("label")
            if isinstance(label, list):
                answer = str(label[0]).strip() if label else ""
            else:
                answer = str(label or "").strip()
            rows.append(
                {
                    "id": source_id,
                    "question": str(item.get("query", "")).strip(),
                    "answer": answer,
                    "image_path": image_rel,
                    "metadata": {
                        "human_or_machine": item.get("human_or_machine"),
                    },
                }
            )
        _write_json(output_root / f"{split}.json", rows)
        summary[split] = {"count": len(rows), "output_file": str((output_root / f"{split}.json").resolve())}
    manifest = {
        "dataset": "chartqa_hf",
        "source": "HuggingFaceM4/ChartQA",
        "output_root": str(output_root.resolve()),
        "splits": summary,
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def materialize_hrbench(output_root: Path) -> dict:
    from datasets import load_dataset

    summary: dict[str, dict] = {}
    variants = {
        "hrbench_4k": ("DreamMr/HR-Bench", "hrbench_version_split", "hrbench_4k"),
        "hrbench_8k": ("DreamMr/HR-Bench", "hrbench_version_split", "hrbench_8k"),
    }
    for filename, (dataset_name, config_name, split_name) in variants.items():
        dataset = load_dataset(dataset_name, config_name, split=split_name)
        rows = [dict(item) for item in dataset]
        path = output_root / f"{filename}.jsonl"
        _write_jsonl(path, rows)
        summary[split_name] = {"count": len(rows), "output_file": str(path.resolve())}
    manifest = {
        "dataset": "hrbench_hf",
        "source": "DreamMr/HR-Bench",
        "output_root": str(output_root.resolve()),
        "splits": summary,
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def materialize_mathvista(output_root: Path, splits: tuple[str, ...] = ("testmini", "test")) -> dict:
    from datasets import load_dataset

    images_root = output_root / "images"
    summary: dict[str, dict] = {}
    for split in splits:
        dataset = load_dataset("AI4Math/MathVista", split=split)
        rows: list[dict] = []
        for item in dataset:
            pid = str(item.get("pid") or item.get("id") or "")
            image_rel = str(item.get("image") or "").strip()
            if not image_rel:
                image_rel = f"images/{pid or len(rows) + 1}.png"
            image_path = output_root / image_rel
            if not image_path.exists():
                decoded = item.get("decoded_image")
                if decoded is None:
                    raise RuntimeError(f"MathVista row {pid} is missing decoded_image")
                _save_image(decoded, image_path)
            row = dict(item)
            row.pop("decoded_image", None)
            row["image"] = image_rel
            rows.append(row)
        path = output_root / f"mathvista_{split}.jsonl"
        _write_jsonl(path, rows)
        summary[split] = {"count": len(rows), "output_file": str(path.resolve())}
    manifest = {
        "dataset": "mathvista_hf",
        "source": "AI4Math/MathVista",
        "output_root": str(output_root.resolve()),
        "images_root": str(images_root.resolve()),
        "splits": summary,
    }
    _write_json(output_root / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize benchmark datasets from Hugging Face to stable local raw dirs.")
    parser.add_argument("--dataset", choices=["chartqa", "hrbench", "mathvista", "all"], required=True)
    parser.add_argument("--chartqa-root", default="/root/vqa_datasets/datasets/chartqa_hf")
    parser.add_argument("--hrbench-root", default="/root/vqa_datasets/datasets/hr_bench")
    parser.add_argument("--mathvista-root", default="/root/vqa_datasets/datasets/mathvista")
    parser.add_argument("--chartqa-splits", nargs="+", default=["train", "val", "test"])
    parser.add_argument("--mathvista-splits", nargs="+", default=["testmini", "test"])
    args = parser.parse_args()

    outputs: dict[str, dict] = {}
    if args.dataset in {"chartqa", "all"}:
        outputs["chartqa"] = materialize_chartqa(Path(args.chartqa_root), tuple(args.chartqa_splits))
    if args.dataset in {"hrbench", "all"}:
        outputs["hrbench"] = materialize_hrbench(Path(args.hrbench_root))
    if args.dataset in {"mathvista", "all"}:
        outputs["mathvista"] = materialize_mathvista(Path(args.mathvista_root), tuple(args.mathvista_splits))
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
