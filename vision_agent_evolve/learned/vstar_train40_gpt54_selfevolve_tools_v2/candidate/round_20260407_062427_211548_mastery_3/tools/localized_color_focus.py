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
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.35:
            continue
        if bw < max(10, w // 80) or bh < max(10, h // 80):
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _dominant_bgr(crop: np.ndarray) -> tuple[int, int, int]:
    pixels = crop.reshape(-1, 3).astype(np.float32)
    if len(pixels) == 0:
        return (0, 0, 0)
    sample_n = min(len(pixels), 4000)
    idx = np.linspace(0, len(pixels) - 1, sample_n).astype(np.int32)
    sample = pixels[idx]
    k = max(1, min(3, sample_n))
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _ret, labels, centers = cv2.kmeans(sample, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    color = centers[np.argmax(counts)].astype(np.uint8)
    return int(color[0]), int(color[1]), int(color[2])


def _score_boxes(image: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> list[tuple[float, tuple[int, int, int, int]]]:
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    scored = []
    for box in boxes:
        x, y, bw, bh = box
        crop_hsv = hsv[y:y + bh, x:x + bw]
        crop_gray = cv2.cvtColor(image[y:y + bh, x:x + bw], cv2.COLOR_BGR2GRAY)
        sat = float(np.mean(crop_hsv[:, :, 1]))
        var = float(np.std(crop_gray))
        area_frac = (bw * bh) / float(h * w)
        center_bias = 1.0 - abs((x + bw / 2) / w - 0.5) * 0.6 - abs((y + bh / 2) / h - 0.5) * 0.3
        score = sat * 0.5 + var * 0.4 + area_frac * 300 + center_bias * 20
        scored.append((score, box))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        boxes = _proposal_regions(img)
        scored = _score_boxes(img, boxes)[:4]
        overlay = img.copy()
        pad = max(4, min(h, w) // 100)
        panel_h = max(h // 4, 120)
        panel = np.full((panel_h, w, 3), 245, dtype=np.uint8)
        slot_w = max(1, w // max(1, len(scored))) if scored else w

        for i, (_score, (x, y, bw, bh)) in enumerate(scored):
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (255, 200, 0), 2)
            cv2.putText(overlay, f"R{i+1}", (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(w, x + bw + pad)
            y1 = min(h, y + bh + pad)
            crop = img[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            dom = _dominant_bgr(crop)
            zoom_h = panel_h - 50
            zoom_w = max(40, slot_w - 20)
            scale = min(zoom_w / crop.shape[1], zoom_h / crop.shape[0])
            new_size = (max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale)))
            zoom = cv2.resize(crop, new_size, interpolation=cv2.INTER_CUBIC)
            sx = i * slot_w + (slot_w - new_size[0]) // 2
            sy = 8 + (zoom_h - new_size[1]) // 2
            panel[sy:sy + new_size[1], sx:sx + new_size[0]] = zoom
            sw0, sw1 = sx, min(sx + 40, w)
            sh0, sh1 = panel_h - 36, panel_h - 8
            panel[sh0:sh1, sw0:sw1] = np.array(dom, dtype=np.uint8)
            cv2.rectangle(panel, (sw0, sh0), (sw1, sh1), (0, 0, 0), 1)
            cv2.putText(panel, f"R{i+1}", (sx, panel_h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2, cv2.LINE_AA)

        if not scored:
            cv2.putText(panel, "No strong local regions found", (10, panel_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2, cv2.LINE_AA)

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
