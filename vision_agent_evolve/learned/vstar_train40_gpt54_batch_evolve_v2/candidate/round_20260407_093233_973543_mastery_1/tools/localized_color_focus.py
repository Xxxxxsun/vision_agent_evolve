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
    blur = cv2.GaussianBlur(mag, (5, 5), 0)
    _, mask = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.35:
            continue
        if bw < max(8, w // 80) or bh < max(8, h // 80):
            continue
        roi = image[y:y + bh, x:x + bw]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[:, :, 1]))
        edge = float(np.mean(blur[y:y + bh, x:x + bw]))
        center_x = x + bw / 2.0
        center_y = y + bh / 2.0
        cx = abs(center_x - w / 2.0) / (w / 2.0)
        cy = abs(center_y - h / 2.0) / (h / 2.0)
        center_bias = 1.0 - 0.5 * (cx + cy)
        score = edge * 0.55 + sat * 0.3 + 255.0 * max(0.0, center_bias) * 0.15
        boxes.append((score, x, y, bw, bh))
    boxes.sort(reverse=True)
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
    if not selected:
        selected = [(w // 4, h // 4, w // 2, h // 2)]
    return selected


def _enhance_crop(crop: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = cv2.normalize(hsv[:, :, 1], None, 40, 255, cv2.NORM_MINMAX)
    hsv[:, :, 2] = cv2.normalize(hsv[:, :, 2], None, 30, 255, cv2.NORM_MINMAX)
    enhanced = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    scale = min(out_w / max(1, crop.shape[1]), out_h / max(1, crop.shape[0]))
    new_w = max(1, int(crop.shape[1] * scale))
    new_h = max(1, int(crop.shape[0] * scale))
    resized = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((out_h, out_w, 3), 245, dtype=np.uint8)
    y0 = (out_h - new_h) // 2
    x0 = (out_w - new_w) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        boxes = _proposal_regions(img)
        overlay = img.copy()
        colors = [(255, 200, 0), (0, 220, 255), (80, 255, 120), (255, 120, 180), (180, 120, 255), (0, 255, 0)]
        for i, (x, y, bw, bh) in enumerate(boxes):
            pad = int(0.08 * max(bw, bh))
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), colors[i % len(colors)], 2)
            cv2.putText(overlay, str(i + 1), (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i % len(colors)], 2, cv2.LINE_AA)
        panel_h = max(h // 3, 180)
        panel = np.full((panel_h, w, 3), 250, dtype=np.uint8)
        n = len(boxes)
        tile_w = max(1, w // n)
        for i, (x, y, bw, bh) in enumerate(boxes):
            pad = int(0.12 * max(bw, bh))
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
            crop = img[y1:y2, x1:x2]
            tile = _enhance_crop(crop, panel_h - 26, tile_w - 8)
            x0 = i * tile_w + 4
            panel[22:22 + tile.shape[0], x0:x0 + tile.shape[1]] = tile
            cv2.putText(panel, str(i + 1), (x0 + 4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA)
        processed_img = np.vstack([overlay, panel])
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