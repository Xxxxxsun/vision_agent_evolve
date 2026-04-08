from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _find_chart_region(image: np.ndarray) -> tuple[int, int, int, int]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = (0, 0, w, h)
    best_area = 0
    image_area = float(h * w)
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = float(cw * ch)
        if area < image_area * 0.08:
            continue
        if area > best_area:
            best = (x, y, cw, ch)
            best_area = area
    return best


def _detect_bars(image: np.ndarray, chart_region: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    x, y, w, h = chart_region
    chart_crop = image[y:y+h, x:x+w]
    gray = cv2.cvtColor(chart_crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bars = []
    for contour in contours:
        cx, cy, cw, ch = cv2.boundingRect(contour)
        if cw < 10 or ch < 10:  # Filter out very small regions
            continue
        bars.append((cx + x, cy + y, cw, ch))
    return bars


def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        overlay = image.copy()
        x, y, w, h = _find_chart_region(image)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), 2)
        bars = _detect_bars(image, (x, y, w, h))
        for bx, by, bw, bh in bars:
            cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)
            # Add text label for manual extraction
            cv2.putText(overlay, "Bar", (bx, by - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        output_path = "artifacts/chart_value_overlay_output.png"
        save_image(overlay, output_path)
        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
        )
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        sys.exit(1)

    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()