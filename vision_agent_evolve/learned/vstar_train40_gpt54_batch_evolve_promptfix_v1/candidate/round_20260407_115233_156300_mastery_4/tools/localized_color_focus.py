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
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.0015 or area > image_area * 0.18:
            continue
        ar = bw / max(bh, 1)
        if ar < 0.25 or ar > 4.0:
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _expand_box(x: int, y: int, w: int, h: int, W: int, H: int, scale: float = 1.35) -> tuple[int, int, int, int]:
    cx, cy = x + w / 2.0, y + h / 2.0
    nw, nh = w * scale, h * scale
    x0 = max(0, int(cx - nw / 2.0))
    y0 = max(0, int(cy - nh / 2.0))
    x1 = min(W, int(cx + nw / 2.0))
    y1 = min(H, int(cy + nh / 2.0))
    return x0, y0, x1 - x0, y1 - y0


def _score_box(image: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x, y, w, h = box
    roi = image[y:y + h, x:x + w]
    if roi.size == 0:
        return -1.0
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32) / 255.0
    val = hsv[:, :, 2].astype(np.float32) / 255.0
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 160)
    edge_density = float(edges.mean()) / 255.0
    colorfulness = float(np.mean(sat * (0.3 + 0.7 * val)))
    compactness = 1.0 / (1.0 + abs((w / max(h, 1)) - 1.0))
    return 0.5 * colorfulness + 0.35 * edge_density + 0.15 * compactness


def _enhance_crop(roi: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    return cv2.resize(enhanced, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_CUBIC)


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        H, W = img.shape[:2]
        boxes = _proposal_regions(img)
        expanded = [_expand_box(x, y, w, h, W, H) for x, y, w, h in boxes]
        scored = sorted((( _score_box(img, b), b) for b in expanded), key=lambda t: t[0], reverse=True)
        top = [b for s, b in scored[:6] if s >= 0]

        overlay = img.copy()
        for i, (x, y, w, h) in enumerate(top):
            color = (0, int(180 + 12 * min(i, 5)), 255)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

        if not top:
            processed_img = overlay
        else:
            thumb_h = max(80, H // 4)
            thumbs = []
            for box in top[:4]:
                x, y, w, h = box
                roi = img[y:y + h, x:x + w]
                zoom = _enhance_crop(roi)
                scale = thumb_h / max(zoom.shape[0], 1)
                thumb = cv2.resize(zoom, (max(1, int(zoom.shape[1] * scale)), thumb_h), interpolation=cv2.INTER_AREA)
                thumbs.append(thumb)
            strip_w = sum(t.shape[1] for t in thumbs) + 10 * (len(thumbs) + 1)
            canvas_w = max(W, strip_w)
            canvas = np.full((H + thumb_h + 20, canvas_w, 3), 245, dtype=np.uint8)
            canvas[:H, :W] = overlay
            xoff = 10
            yoff = H + 10
            for thumb in thumbs:
                th, tw = thumb.shape[:2]
                canvas[yoff:yoff + th, xoff:xoff + tw] = thumb
                cv2.rectangle(canvas, (xoff, yoff), (xoff + tw, yoff + th), (80, 80, 80), 1)
                xoff += tw + 10
            processed_img = canvas

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