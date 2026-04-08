from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from core.types import ToolResult


def _resolve_output_path(name: str) -> Path:
    work_dir = Path(os.environ.get("VISION_AGENT_WORK_DIR", "artifacts"))
    return work_dir / name


def _fit_patch(image: Image.Image, size: int) -> Image.Image:
    patch = image.copy()
    patch.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), (245, 245, 245))
    x = (size - patch.width) // 2
    y = (size - patch.height) // 2
    canvas.paste(patch, (x, y))
    return canvas


def _candidate_boxes(width: int, height: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Return generic location crops for small-object attribute inspection."""
    boxes: list[tuple[str, tuple[int, int, int, int]]] = []
    specs = [
        ("C", 0.50, 0.50, 0.44, 0.44),
        ("L", 0.30, 0.50, 0.36, 0.46),
        ("R", 0.70, 0.50, 0.36, 0.46),
        ("T", 0.50, 0.30, 0.46, 0.36),
        ("B", 0.50, 0.70, 0.46, 0.36),
        ("W", 0.50, 0.50, 0.78, 0.78),
    ]
    for label, cx_frac, cy_frac, bw_frac, bh_frac in specs:
        bw = max(8, int(width * bw_frac))
        bh = max(8, int(height * bh_frac))
        cx = int(width * cx_frac)
        cy = int(height * cy_frac)
        x1 = max(0, min(width - bw, cx - bw // 2))
        y1 = max(0, min(height - bh, cy - bh // 2))
        boxes.append((label, (x1, y1, x1 + bw, y1 + bh)))
    return boxes


def run(image_path: str) -> ToolResult:
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return ToolResult(status="error", answer="", error=f"Failed to load image: {exc}")

    width, height = image.size
    boxes = _candidate_boxes(width, height)

    preview_width = min(900, max(360, width))
    scale = preview_width / max(width, 1)
    preview_height = max(1, int(height * scale))
    preview = image.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(preview)
    palette = [(255, 170, 0), (0, 180, 255), (0, 210, 120), (255, 100, 220), (150, 120, 255), (255, 80, 80)]

    panel_size = max(130, min(220, preview_width // 3))
    panel_cols = 3
    panel_rows = 2
    panel = Image.new("RGB", (panel_cols * panel_size, panel_rows * panel_size), (248, 248, 248))
    panel_draw = ImageDraw.Draw(panel)

    for idx, (label, box) in enumerate(boxes):
        color = palette[idx % len(palette)]
        x1, y1, x2, y2 = box
        scaled_box = tuple(int(v * scale) for v in box)
        draw.rectangle(scaled_box, outline=color, width=4)
        draw.text((scaled_box[0] + 4, max(2, scaled_box[1] - 18)), label, fill=color)

        crop = image.crop((x1, y1, x2, y2))
        crop = ImageEnhance.Sharpness(crop).enhance(1.6)
        patch = _fit_patch(crop, panel_size - 12)
        px = (idx % panel_cols) * panel_size + 6
        py = (idx // panel_cols) * panel_size + 6
        panel.paste(patch, (px, py))
        panel_draw.rectangle((px, py, px + patch.width - 1, py + patch.height - 1), outline=color, width=3)
        panel_draw.text((px + 6, py + 6), label, fill=color)

    out = Image.new("RGB", (max(preview.width, panel.width), preview.height + panel.height), (255, 255, 255))
    out.paste(preview, ((out.width - preview.width) // 2, 0))
    out.paste(panel, ((out.width - panel.width) // 2, preview.height))

    output_path = _resolve_output_path("localized_color_focus_output.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)
    return ToolResult(
        status="ok",
        answer="",
        artifacts=[str(output_path)],
        debug_info="PIL crop panel: overview plus labeled center/left/right/top/bottom/wide crops.",
    )


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        raise SystemExit(1)
    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()
