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
    _, edge_mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    _, sat_mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    mask = cv2.bitwise_or(edge_mask, sat_mask)
    k = max(3, int(round(min(h, w) * 0.01)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.35:
            continue
        aspect = bw / max(bh, 1)
        if aspect > 6.0 or aspect < 0.15:
            continue
        roi_sat = sat[y:y + bh, x:x + bw]
        roi_mag = mag[y:y + bh, x:x + bw]
        score = float(np.mean(roi_sat)) + 0.6 * float(np.mean(roi_mag))
        boxes.append((x, y, bw, bh, score))

    boxes.sort(key=lambda b: b[4], reverse=True)
    selected = []
    for x, y, bw, bh, _ in boxes:
        keep = True
        for sx, sy, sw, sh in selected:
            inter_x1 = max(x, sx)
            inter_y1 = max(y, sy)
            inter_x2 = min(x + bw, sx + sw)
            inter_y2 = min(y + bh, sy + sh)
            inter = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.35:
                keep = False
                break
        if keep:
            selected.append((x, y, bw, bh))
        if len(selected) >= 6:
            break
    return selected


def _enhance_patch(patch: np.ndarray, out_size: int) -> np.ndarray:
    if patch.size == 0:
        return np.zeros((out_size, out_size, 3), dtype=np.uint8)
    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    ph, pw = enhanced.shape[:2]
    scale = min(out_size / max(ph, 1), out_size / max(pw, 1))
    nw, nh = max(1, int(pw * scale)), max(1, int(ph * scale))
    resized = cv2.resize(enhanced, (nw, nh), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((out_size, out_size, 3), 245, dtype=np.uint8)
    oy = (out_size - nh) // 2
    ox = (out_size - nw) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return canvas


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        boxes = _proposal_regions(img)

        overlay = img.copy()
        colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 255), (120, 180, 255), (255, 180, 120)]
        for i, (x, y, bw, bh) in enumerate(boxes):
            color = colors[i % len(colors)]
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, max(2, min(h, w) // 300))
            cv2.putText(overlay, str(i + 1), (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        panel_h = max(120, h // 4)
        patch_size = int(panel_h * 0.8)
        strip = np.full((panel_h, w, 3), 250, dtype=np.uint8)
        margin = max(8, w // 100)
        x_cursor = margin
        for i, (x, y, bw, bh) in enumerate(boxes):
            if x_cursor + patch_size > w - margin:
                break
            pad = int(0.12 * max(bw, bh))
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + bw + pad)
            y2 = min(h, y + bh + pad)
            patch = _enhance_patch(img[y1:y2, x1:x2], patch_size)
            y_off = (panel_h - patch_size) // 2
            strip[y_off:y_off + patch_size, x_cursor:x_cursor + patch_size] = patch
            cv2.rectangle(strip, (x_cursor, y_off), (x_cursor + patch_size, y_off + patch_size), colors[i % len(colors)], 2)
            cv2.putText(strip, str(i + 1), (x_cursor + 6, y_off + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i % len(colors)], 2, cv2.LINE_AA)
            x_cursor += patch_size + margin

        processed_img = np.vstack([overlay, strip])
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