from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from core.types import ToolResult


def _resolve_output_path(name: str) -> Path:
    work_dir = Path(os.environ.get("VISION_AGENT_WORK_DIR", "artifacts"))
    return work_dir / name


def _thumbnail(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (245, 245, 245))
    canvas.paste(copy, ((size[0] - copy.width) // 2, (size[1] - copy.height) // 2))
    return canvas


def run(image_path: str) -> ToolResult:
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        return ToolResult(status="error", answer="", error=f"Failed to load image: {exc}")

    width, height = image.size
    preview_width = min(900, max(360, width))
    scale = preview_width / max(width, 1)
    preview_height = max(1, int(height * scale))
    preview = image.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
    preview = ImageEnhance.Sharpness(preview).enhance(1.25)
    draw = ImageDraw.Draw(preview)

    mid_x = preview.width // 2
    mid_y = preview.height // 2
    third_x1 = preview.width // 3
    third_x2 = 2 * preview.width // 3
    third_y1 = preview.height // 3
    third_y2 = 2 * preview.height // 3
    draw.line((mid_x, 0, mid_x, preview.height), fill=(255, 255, 255), width=3)
    draw.line((0, mid_y, preview.width, mid_y), fill=(255, 255, 255), width=3)
    for x in (third_x1, third_x2):
        draw.line((x, 0, x, preview.height), fill=(255, 210, 0), width=2)
    for y in (third_y1, third_y2):
        draw.line((0, y, preview.width, y), fill=(255, 210, 0), width=2)
    draw.text((8, 8), "left | center | right / top | middle | bottom guide", fill=(255, 255, 255))

    patch_w = max(140, preview.width // 3)
    patch_h = max(120, preview.height // 3)
    source_boxes = [
        ("left", (0, 0, width // 2, height)),
        ("right", (width // 2, 0, width, height)),
        ("top", (0, 0, width, height // 2)),
        ("bottom", (0, height // 2, width, height)),
        ("center", (width // 4, height // 4, 3 * width // 4, 3 * height // 4)),
        ("full", (0, 0, width, height)),
    ]
    panel = Image.new("RGB", (3 * patch_w, 2 * patch_h), (248, 248, 248))
    panel_draw = ImageDraw.Draw(panel)
    colors = [(255, 210, 0), (0, 190, 255), (0, 220, 120), (255, 120, 220), (255, 120, 80), (180, 140, 255)]

    for idx, (label, box) in enumerate(source_boxes):
        crop = image.crop(box)
        thumb = _thumbnail(crop, (patch_w - 12, patch_h - 12))
        x = (idx % 3) * patch_w + 6
        y = (idx // 3) * patch_h + 6
        panel.paste(thumb, (x, y))
        color = colors[idx % len(colors)]
        panel_draw.rectangle((x, y, x + thumb.width - 1, y + thumb.height - 1), outline=color, width=3)
        panel_draw.text((x + 6, y + 6), label, fill=color)

    out = Image.new("RGB", (max(preview.width, panel.width), preview.height + panel.height), (255, 255, 255))
    out.paste(preview, ((out.width - preview.width) // 2, 0))
    out.paste(panel, ((out.width - panel.width) // 2, preview.height))

    output_path = _resolve_output_path("generic_visual_focus_output.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)
    return ToolResult(
        status="ok",
        answer="",
        artifacts=[str(output_path)],
        debug_info="PIL spatial guide: overview grid plus left/right/top/bottom/center/full crops.",
    )


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        raise SystemExit(1)
    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()
