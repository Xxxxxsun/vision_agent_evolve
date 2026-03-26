from __future__ import annotations

import cv2
import numpy as np

from core.types import ToolResult
from tools.implementations.shared import load_image, save_image


PANEL_W = 640
PANEL_H = 420
TEXT_COLOR = (30, 30, 30)
LABEL_BG = (245, 245, 245)


def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        h, w = image.shape[:2]

        center_crop = _crop_fraction(image, 0.2, 0.2, 0.6, 0.6)
        tl = _crop_fraction(image, 0.0, 0.0, 0.5, 0.5)
        tr = _crop_fraction(image, 0.5, 0.0, 0.5, 0.5)
        bl = _crop_fraction(image, 0.0, 0.5, 0.5, 0.5)
        br = _crop_fraction(image, 0.5, 0.5, 0.5, 0.5)
        sharpened = _sharpen(center_crop)

        panels = [
            ("original", image),
            ("center crop", center_crop),
            ("top left", tl),
            ("top right", tr),
            ("bottom left", bl),
            ("bottom right", br),
            ("center sharpened", sharpened),
        ]

        grid = _assemble_grid(panels)
        output_path = save_image(grid, "artifacts/hrbench_focus_grid.png")

        answer = (
            "Generated labeled focus grid with original, center crop, four quadrants, "
            "and a sharpened center view. Inspect the panel names to answer from the most relevant region."
        )
        debug = (
            f"original_size={w}x{h}\n"
            "panel_order=original,center crop,top left,top right,bottom left,bottom right,center sharpened"
        )
        return ToolResult(status="ok", answer=answer, artifacts=[str(output_path)], debug_info=debug)
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def _crop_fraction(img: np.ndarray, x_frac: float, y_frac: float, w_frac: float, h_frac: float) -> np.ndarray:
    h, w = img.shape[:2]
    x0 = max(0, min(w - 1, int(w * x_frac)))
    y0 = max(0, min(h - 1, int(h * y_frac)))
    x1 = max(x0 + 1, min(w, int(w * (x_frac + w_frac))))
    y1 = max(y0 + 1, min(h, int(h * (y_frac + h_frac))))
    return img[y0:y1, x0:x1].copy()


def _sharpen(img: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(img, (0, 0), 1.2)
    return cv2.addWeighted(img, 1.8, blurred, -0.8, 0)


def _assemble_grid(panels: list[tuple[str, np.ndarray]]) -> np.ndarray:
    rendered = [_render_panel(label, image) for label, image in panels]
    blank = np.full_like(rendered[0], 255)
    while len(rendered) % 2 != 0:
        rendered.append(blank.copy())

    rows = []
    for index in range(0, len(rendered), 2):
        rows.append(np.hstack([rendered[index], rendered[index + 1]]))
    return np.vstack(rows)


def _render_panel(label: str, image: np.ndarray) -> np.ndarray:
    resized = _fit_with_padding(image, PANEL_W, PANEL_H - 46)
    canvas = np.full((PANEL_H, PANEL_W, 3), 255, dtype=np.uint8)
    canvas[46:, :, :] = resized
    cv2.rectangle(canvas, (0, 0), (PANEL_W - 1, 45), LABEL_BG, thickness=-1)
    cv2.rectangle(canvas, (0, 0), (PANEL_W - 1, PANEL_H - 1), (180, 180, 180), thickness=2)
    cv2.putText(
        canvas,
        label,
        (16, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        TEXT_COLOR,
        2,
        cv2.LINE_AA,
    )
    return canvas


def _fit_with_padding(image: np.ndarray, width: int, height: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(width / max(w, 1), height / max(h, 1))
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    y0 = (height - new_h) // 2
    x0 = (width - new_w) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        raise SystemExit(1)

    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()
