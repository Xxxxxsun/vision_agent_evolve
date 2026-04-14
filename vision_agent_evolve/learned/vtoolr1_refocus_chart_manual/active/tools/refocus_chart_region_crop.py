from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageOps

from core.types import ToolResult


def _load_bbox_mapping(raw_json: str) -> dict[str, dict[str, int]]:
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("bbox mapping must decode to a JSON object")
    cleaned: dict[str, dict[str, int]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        try:
            cleaned[str(key)] = {
                "x1": int(value["x1"]),
                "y1": int(value["y1"]),
                "x2": int(value["x2"]),
                "y2": int(value["y2"]),
            }
        except Exception:
            continue
    if not cleaned:
        raise ValueError("bbox mapping did not contain any usable labeled boxes")
    return cleaned


def _normalize_labels(raw_json: str, bbox_mapping: dict[str, dict[str, int]]) -> list[str]:
    if not raw_json.strip():
        return []
    parsed = json.loads(raw_json)
    if not isinstance(parsed, list):
        raise ValueError("labels_json must decode to a JSON list")
    labels = [str(value).strip() for value in parsed if str(value).strip()]
    missing = [label for label in labels if label not in bbox_mapping]
    if missing:
        raise ValueError(f"labels not found in bbox mapping: {missing}")
    return labels


def _artifact_dir() -> Path:
    work_dir = os.environ.get("VISION_AGENT_WORK_DIR", "").strip()
    if work_dir:
        target = Path(work_dir) / "artifacts"
    else:
        target = Path("artifacts")
    target.mkdir(parents=True, exist_ok=True)
    return target


def run(image_path: str, labels_json: str, bbox_mapping_json: str, padding: str = "16") -> ToolResult:
    try:
        bbox_mapping = _load_bbox_mapping(bbox_mapping_json)
        labels = _normalize_labels(labels_json, bbox_mapping)
        if not labels:
            raise ValueError("labels_json must include at least one label")
        pad = max(0, int(float(padding)))

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            width, height = image.size
            x1 = min(bbox_mapping[label]["x1"] for label in labels)
            y1 = min(bbox_mapping[label]["y1"] for label in labels)
            x2 = max(bbox_mapping[label]["x2"] for label in labels)
            y2 = max(bbox_mapping[label]["y2"] for label in labels)
            crop_box = (
                max(0, x1 - pad),
                max(0, y1 - pad),
                min(width, x2 + pad),
                min(height, y2 + pad),
            )
            cropped = image.crop(crop_box)
            # Add a thin border so the cropped focus region is visually obvious.
            cropped = ImageOps.expand(cropped, border=4, fill=(220, 30, 30))

        slug = "_".join(label.lower().replace(" ", "_")[:24] for label in labels[:3]) or "focus"
        output_path = _artifact_dir() / f"refocus_chart_region_crop_{slug}.png"
        cropped.save(output_path)
        answer = (
            f"Cropped focus region for labels {labels}. "
            f"crop_box={list(crop_box)}\n"
            f"ARTIFACTS: {output_path}"
        )
        return ToolResult(status="ok", answer=answer, artifacts=[str(output_path)])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def main() -> None:
    import sys

    if len(sys.argv) < 4:
        print(
            "Usage: python -m tools refocus_chart_region_crop <image_path> "
            "'[\"Label\"]' '<bbox_mapping_json>' [padding]"
        )
        raise SystemExit(1)

    image_path = sys.argv[1]
    labels_json = sys.argv[2]
    bbox_mapping_json = sys.argv[3]
    padding = sys.argv[4] if len(sys.argv) > 4 else "16"
    result = run(image_path, labels_json, bbox_mapping_json, padding)
    if result.status != "ok":
        print(f"ERROR: {result.error}")
        raise SystemExit(1)
    print(result.answer)


if __name__ == "__main__":
    main()
