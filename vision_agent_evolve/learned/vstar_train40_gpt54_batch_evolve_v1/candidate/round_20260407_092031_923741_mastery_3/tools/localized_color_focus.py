from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.convertScaleAbs(cv2.magnitude(grad_x, grad_y))
    _, mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    k = max(3, int(round(min(h, w) * 0.01)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.35:
            continue
        if bw < 8 or bh < 8:
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _box_score(image: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x, y, w, h = box
    roi = image[y:y + h, x:x + w]
    if roi.size == 0:
        return -1.0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    val = hsv[:, :, 2].astype(np.float32) / 255.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edge = cv2.Canny(gray, 60, 160).astype(np.float32) / 255.0
    edge_density = float(edge.mean())
    colorfulness = float((sat * (0.5 + 0.5 * val)).mean())
    aspect_penalty = abs((w / max(h, 1.0)) - 1.0)
    area_ratio = (w * h) / float(image.shape[0] * image.shape[1])
    size_term = 1.0 - min(abs(area_ratio - 0.03) / 0.03, 1.0)
    return 1.2 * edge_density + colorfulness + 0.5 * size_term - 0.15 * aspect_penalty


def _expand(box: tuple[int, int, int, int], shape: tuple[int, int, int], pad_frac: float = 0.25) -> tuple[int, int, int, int]:
    x, y, w, h = box
    ih, iw = shape[:2]
    px = int(round(w * pad_frac))
    py = int(round(h * pad_frac))
    x0 = max(0, x - px)
    y0 = max(0, y - py)
    x1 = min(iw, x + w + px)
    y1 = min(ih, y + h + py)
    return x0, y0, x1 - x0, y1 - y0


def _make_panel(image: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    h, w = image.shape[:2]
    overlay = image.copy()
    colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 255)]
    top = boxes[:4]
    for i, box in enumerate(top):
        x, y, bw, bh = _expand(box, image.shape)
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), colors[i % len(colors)], max(2, min(h, w) // 300))
        cv2.putText(overlay, str(i + 1), (x, max(18, y + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colors[i % len(colors)], 2, cv2.LINE_AA)

    panel_w = max(w, 900)
    header_h = max(36, h // 18)
    tile_h = max(140, h // 3)
    panel = np.full((h + header_h + tile_h, panel_w, 3), 245, dtype=np.uint8)
    panel[:h, :w] = overlay
    cv2.putText(panel, "Localized color focus: inspect numbered candidate regions", (10, h + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 40), 2, cv2.LINE_AA)

    if not top:
        return panel

    tile_w = panel_w // len(top)
    y0 = h + header_h
    for i, box in enumerate(top):
        x, y, bw, bh = _expand(box, image.shape, 0.35)
        crop = image[y:y + bh, x:x + bw]
        if crop.size == 0:
            continue
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
        scale = min((tile_w - 12) / max(enhanced.shape[1], 1), (tile_h - 28) / max(enhanced.shape[0], 1))
        new_w = max(1, int(enhanced.shape[1] * scale))
        new_h = max(1, int(enhanced.shape[0] * scale))
        resized = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        x1 = i * tile_w + (tile_w - new_w) // 2
        y1 = y0 + 20 + (tile_h - 20 - new_h) // 2
        panel[y1:y1 + new_h, x1:x1 + new_w] = resized
        cv2.putText(panel, f"#{i + 1}", (i * tile_w + 8, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2, cv2.LINE_AA)
    return panel


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        boxes = _proposal_regions(img)
        boxes = sorted(boxes, key=lambda b: _box_score(img, b), reverse=True)[:8]
        processed_img = _make_panel(img, boxes)

        output_path = "artifacts/localized_color_focus_output.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))


def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        sys.exit(1)

    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()