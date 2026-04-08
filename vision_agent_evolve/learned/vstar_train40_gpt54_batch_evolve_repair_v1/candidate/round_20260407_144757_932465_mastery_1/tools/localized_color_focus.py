from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag8 = cv2.convertScaleAbs(mag)
    _, edge_mask = cv2.threshold(mag8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    merged = cv2.morphologyEx(edge_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    merged = cv2.dilate(merged, kernel, iterations=1)

    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.35:
            continue
        aspect = bw / float(max(bh, 1))
        if aspect > 8 or aspect < 0.125:
            continue
        roi = gray[y:y + bh, x:x + bw]
        if roi.size == 0:
            continue
        texture = float(np.std(roi))
        if texture < 8:
            continue
        boxes.append((x, y, bw, bh))

    scored = []
    for x, y, bw, bh in boxes:
        roi = image[y:y + bh, x:x + bw]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[:, :, 1]))
        val_std = float(np.std(hsv[:, :, 2]))
        score = sat * 0.6 + val_std * 0.4 + min(bw * bh / image_area, 0.03) * 1000
        scored.append((score, (x, y, bw, bh)))

    scored.sort(key=lambda t: t[0], reverse=True)
    selected = []
    for _, box in scored:
        x, y, bw, bh = box
        keep = True
        for sx, sy, sw, sh in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.4:
                keep = False
                break
        if keep:
            selected.append(box)
        if len(selected) >= 6:
            break
    return selected


def _enhance_crop(crop: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    return enhanced


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        boxes = _proposal_regions(img)

        overlay = img.copy()
        colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 120), (180, 120, 255), (255, 255, 0)]
        for i, (x, y, bw, bh) in enumerate(boxes):
            pad = int(0.08 * max(bw, bh)) + 2
            x1, y1 = max(0, x - pad), max(0, y - pad)
            x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
            cv2.rectangle(overlay, (x1, y1), (x2, y2), colors[i % len(colors)], 2)
            cv2.putText(overlay, str(i + 1), (x1, max(18, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i % len(colors)], 2, cv2.LINE_AA)

        top_h = max(h, 240)
        panel = np.full((top_h, w, 3), 245, dtype=np.uint8)
        if boxes:
            tile_w = max(1, w // min(len(boxes), 3))
            tile_h = max(1, top_h // (1 if len(boxes) <= 3 else 2))
            for i, (x, y, bw, bh) in enumerate(boxes):
                r = 0 if i < 3 else 1
                c = i if i < 3 else i - 3
                if c >= 3:
                    break
                pad = int(0.18 * max(bw, bh)) + 2
                x1, y1 = max(0, x - pad), max(0, y - pad)
                x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
                crop = img[y1:y2, x1:x2]
                if crop.size == 0:
                    continue
                crop = _enhance_crop(crop)
                scale = min((tile_w - 10) / max(crop.shape[1], 1), (tile_h - 30) / max(crop.shape[0], 1))
                new_size = (max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale)))
                resized = cv2.resize(crop, new_size, interpolation=cv2.INTER_CUBIC)
                oy = r * tile_h + 25 + (tile_h - 30 - resized.shape[0]) // 2
                ox = c * tile_w + 5 + (tile_w - 10 - resized.shape[1]) // 2
                panel[oy:oy + resized.shape[0], ox:ox + resized.shape[1]] = resized
                cv2.putText(panel, f"Region {i+1}", (c * tile_w + 8, r * tile_h + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (40, 40, 40), 2, cv2.LINE_AA)

        processed_img = np.vstack([panel, overlay]) if boxes else overlay
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