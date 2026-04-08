from core.types import ToolResult
from tools.implementations.shared import load_image, save_image

import cv2
import numpy as np


def _proposal_regions(image: np.ndarray):
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag_u8 = cv2.convertScaleAbs(mag)
    _, edge = cv2.threshold(mag_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(edge, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.25:
            continue
        if bw < max(8, w // 100) or bh < max(8, h // 100):
            continue
        roi = image[y:y + bh, x:x + bw]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[:, :, 1]))
        val_std = float(np.std(hsv[:, :, 2]))
        score = (area / image_area) * 2.0 + sat / 255.0 + val_std / 128.0
        boxes.append((score, x, y, bw, bh))

    boxes.sort(key=lambda t: t[0], reverse=True)
    selected = []
    for _, x, y, bw, bh in boxes:
        keep = True
        for sx, sy, sw, sh in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.35:
                keep = False
                break
        if keep:
            selected.append((x, y, bw, bh))
        if len(selected) >= 6:
            break
    return selected


def _enhance_roi(roi: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    merged = cv2.merge([l2, a, b])
    enhanced = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    return cv2.convertScaleAbs(enhanced, alpha=1.1, beta=4)


def _make_output(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    overlay = image.copy()
    boxes = _proposal_regions(image)

    for i, (x, y, bw, bh) in enumerate(boxes):
        color = (255, 200 - 20 * min(i, 5), 0 + 30 * min(i, 5))
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, 2)
        cv2.putText(overlay, str(i + 1), (x, max(18, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

    top_h = int(h * 0.68)
    bottom_h = max(120, h - top_h)
    canvas = np.full((top_h + bottom_h, w, 3), 255, dtype=np.uint8)
    canvas[:top_h] = cv2.resize(overlay, (w, top_h))

    if not boxes:
        return canvas

    tile_h = bottom_h - 20
    gap = 10
    tile_w = max(1, (w - gap * (len(boxes) + 1)) // len(boxes))
    x_cursor = gap
    for i, (x, y, bw, bh) in enumerate(boxes):
        pad = max(2, int(0.12 * max(bw, bh)))
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        roi = image[y1:y2, x1:x2]
        roi = _enhance_roi(roi)
        rh, rw = roi.shape[:2]
        scale = min(tile_w / max(1, rw), tile_h / max(1, rh))
        new_w, new_h = max(1, int(rw * scale)), max(1, int(rh * scale))
        tile = cv2.resize(roi, (new_w, new_h))
        y_off = top_h + 10 + (tile_h - new_h) // 2
        canvas[y_off:y_off + new_h, x_cursor:x_cursor + new_w] = tile
        cv2.rectangle(canvas, (x_cursor, top_h + 10), (x_cursor + tile_w, top_h + 10 + tile_h), (180, 180, 180), 1)
        cv2.putText(canvas, str(i + 1), (x_cursor + 4, top_h + 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 255), 2, cv2.LINE_AA)
        x_cursor += tile_w + gap

    return canvas


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        processed_img = _make_output(img)

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
