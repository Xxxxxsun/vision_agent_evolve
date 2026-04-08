from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag_u8 = cv2.convertScaleAbs(mag)
    _, edge_mask = cv2.threshold(mag_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    a = lab[:, :, 1].astype(np.float32)
    b = lab[:, :, 2].astype(np.float32)
    colorfulness = cv2.magnitude(a - 128.0, b - 128.0)
    color_u8 = cv2.normalize(colorfulness, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, color_mask = cv2.threshold(color_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    mask = cv2.bitwise_or(edge_mask, color_mask)
    k = max(3, int(round(min(h, w) * 0.01)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    proposals = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.001 or area > image_area * 0.25:
            continue
        if bw < max(8, w // 100) or bh < max(8, h // 100):
            continue

        roi_mask = mask[y:y + bh, x:x + bw]
        roi_mag = mag[y:y + bh, x:x + bw]
        roi_color = colorfulness[y:y + bh, x:x + bw]
        fill_ratio = float(np.count_nonzero(roi_mask)) / max(1.0, area)
        edge_score = float(np.mean(roi_mag))
        color_score = float(np.mean(roi_color))
        center_x = x + bw / 2.0
        center_y = y + bh / 2.0
        center_bias = 1.0 - (((center_x - w / 2.0) / (w / 2.0)) ** 2 + ((center_y - h / 2.0) / (h / 2.0)) ** 2) * 0.25
        score = (0.45 * fill_ratio) + (0.25 * (edge_score / (np.mean(mag) + 1e-6))) + (0.25 * (color_score / (np.mean(colorfulness) + 1e-6))) + (0.05 * center_bias)
        proposals.append((x, y, bw, bh, score))

    proposals.sort(key=lambda t: t[4], reverse=True)

    selected = []
    for box in proposals:
        x, y, bw, bh, score = box
        keep = True
        for sx, sy, sw, sh, _ in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.35:
                keep = False
                break
        if keep:
            selected.append(box)
        if len(selected) >= 6:
            break
    return selected


def _expand_box(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> tuple[int, int, int, int]:
    pad_x = max(2, int(w * 0.2))
    pad_y = max(2, int(h * 0.2))
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(img_w, x + w + pad_x)
    y2 = min(img_h, y + h + pad_y)
    return x1, y1, x2, y2


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        processed_img = img.copy()

        proposals = _proposal_regions(img)
        if not proposals:
            output_path = "artifacts/localized_color_focus_output.png"
            save_image(processed_img, output_path)
            return ToolResult(status="ok", answer="no_proposals", artifacts=[output_path])

        overlay = processed_img.copy()
        colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 0), (180, 80, 255), (255, 0, 180)]
        crops = []
        crop_h = max(80, h // 5)
        crop_w = max(80, w // 6)

        for i, (x, y, bw, bh, _) in enumerate(proposals):
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), colors[i % len(colors)], 2)
            cv2.putText(overlay, str(i + 1), (x, max(18, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[i % len(colors)], 2, cv2.LINE_AA)
            x1, y1, x2, y2 = _expand_box(x, y, bw, bh, w, h)
            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            crop = cv2.resize(crop, (crop_w, crop_h), interpolation=cv2.INTER_CUBIC)
            crop = cv2.convertScaleAbs(crop, alpha=1.2, beta=8)
            cv2.rectangle(crop, (0, 0), (crop.shape[1] - 1, crop.shape[0] - 1), colors[i % len(colors)], 3)
            cv2.putText(crop, str(i + 1), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, colors[i % len(colors)], 2, cv2.LINE_AA)
            crops.append(crop)

        processed_img = cv2.addWeighted(overlay, 0.75, img, 0.25, 0)
        if crops:
            strip = np.full((crop_h, crop_w * len(crops), 3), 255, dtype=np.uint8)
            for i, crop in enumerate(crops):
                strip[:, i * crop_w:(i + 1) * crop_w] = crop
            gap = np.full((max(8, h // 80), max(w, strip.shape[1]), 3), 255, dtype=np.uint8)
            canvas_w = max(w, strip.shape[1])
            top = np.full((h, canvas_w, 3), 255, dtype=np.uint8)
            top[:h, :w] = processed_img
            bottom = np.full((crop_h, canvas_w, 3), 255, dtype=np.uint8)
            bottom[:crop_h, :strip.shape[1]] = strip
            processed_img = np.vstack([top, gap, bottom])

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