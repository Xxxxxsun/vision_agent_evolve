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
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.25:
            continue
        if bw < max(8, w // 80) or bh < max(8, h // 80):
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _score_box(image: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x, y, w, h = box
    roi = image[y:y + h, x:x + w]
    if roi.size == 0:
        return -1.0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32)
    val = hsv[:, :, 2].astype(np.float32)
    colorfulness = float(np.mean(sat))
    contrast = float(np.std(val))
    area = float(w * h)
    return colorfulness * 0.6 + contrast * 0.3 + np.sqrt(area) * 0.1


def _expand_box(box: tuple[int, int, int, int], shape: tuple[int, int, int], scale: float = 0.2) -> tuple[int, int, int, int]:
    x, y, w, h = box
    ih, iw = shape[:2]
    pad_x = int(w * scale)
    pad_y = int(h * scale)
    x0 = max(0, x - pad_x)
    y0 = max(0, y - pad_y)
    x1 = min(iw, x + w + pad_x)
    y1 = min(ih, y + h + pad_y)
    return x0, y0, x1 - x0, y1 - y0


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        proposals = _proposal_regions(img)
        scored = [(_score_box(img, b), b) for b in proposals]
        scored.sort(key=lambda t: t[0], reverse=True)
        top_boxes = [_expand_box(b, img.shape, 0.2) for _, b in scored[:5]]

        overlay = img.copy()
        colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 255), (120, 180, 255)]
        for i, (x, y, bw, bh) in enumerate(top_boxes):
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), colors[i % len(colors)], 2)
            cv2.putText(overlay, f"R{i+1}", (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i % len(colors)], 2, cv2.LINE_AA)

        panel_h = max(h, 220)
        panel_w = w + min(len(top_boxes), 3) * max(180, w // 6)
        processed_img = np.full((panel_h, panel_w, 3), 245, dtype=np.uint8)
        processed_img[:h, :w] = overlay

        thumb_x = w
        thumb_w = max(180, w // 6)
        thumb_h = max(180, h // 3)
        for i, (x, y, bw, bh) in enumerate(top_boxes[:3]):
            roi = img[y:y + bh, x:x + bw]
            if roi.size == 0:
                continue
            roi_lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(roi_lab)
            l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
            roi_enh = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
            thumb = cv2.resize(roi_enh, (thumb_w, thumb_h), interpolation=cv2.INTER_CUBIC)
            y0 = i * thumb_h
            y1 = min(panel_h, y0 + thumb_h)
            processed_img[y0:y1, thumb_x:thumb_x + thumb_w] = thumb[:y1 - y0, :thumb_w]
            cv2.rectangle(processed_img, (thumb_x, y0), (thumb_x + thumb_w - 1, y1 - 1), colors[i % len(colors)], 3)
            cv2.putText(processed_img, f"Zoom R{i+1}", (thumb_x + 8, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, colors[i % len(colors)], 2, cv2.LINE_AA)
            thumb_x += thumb_w

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