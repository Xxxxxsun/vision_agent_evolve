from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _proposal_regions(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag = cv2.convertScaleAbs(mag)
    _, mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    k = max(3, (min(h, w) // 120) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = float(bw * bh)
        if area < image_area * 0.002 or area > image_area * 0.20:
            continue
        if bh == 0 or bw == 0:
            continue
        aspect = bw / float(bh)
        if aspect > 4.5 or aspect < 0.2:
            continue
        boxes.append((x, y, bw, bh, area))

    boxes.sort(key=lambda b: b[4], reverse=True)
    kept = []
    for x, y, bw, bh, _ in boxes:
        keep = True
        for kx, ky, kw, kh in kept:
            ix1, iy1 = max(x, kx), max(y, ky)
            ix2, iy2 = min(x + bw, kx + kw), min(y + bh, ky + kh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = bw * bh + kw * kh - inter
            if union > 0 and inter / union > 0.4:
                keep = False
                break
        if keep:
            kept.append((x, y, bw, bh))
        if len(kept) >= 8:
            break
    return kept


def _enhance_crop(crop: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    return enhanced


def _make_contact_sheet(img: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    h, w = img.shape[:2]
    overlay = img.copy()
    for i, (x, y, bw, bh) in enumerate(boxes):
        pad = max(4, int(0.08 * max(bw, bh)))
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 200, 0), 2)
        cv2.putText(overlay, str(i + 1), (x1, max(18, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)

    target_w = max(220, w)
    top_h = max(180, int(h * target_w / w))
    top = cv2.resize(overlay, (target_w, top_h))

    thumbs = []
    thumb_w = max(120, target_w // 4)
    thumb_h = max(100, int(thumb_w * 0.75))
    for i, (x, y, bw, bh) in enumerate(boxes):
        pad = max(6, int(0.15 * max(bw, bh)))
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        crop = img[y1:y2, x1:x2]
        crop = _enhance_crop(crop)
        crop = cv2.resize(crop, (thumb_w, thumb_h))
        cv2.putText(crop, str(i + 1), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2, cv2.LINE_AA)
        thumbs.append(crop)

    if not thumbs:
        return top

    rows = []
    per_row = max(2, target_w // thumb_w)
    for i in range(0, len(thumbs), per_row):
        row = thumbs[i:i + per_row]
        while len(row) < per_row:
            row.append(np.full((thumb_h, thumb_w, 3), 245, dtype=np.uint8))
        rows.append(np.hstack(row))
    grid = np.vstack(rows)

    if grid.shape[1] != target_w:
        grid = cv2.resize(grid, (target_w, grid.shape[0]))

    sep = np.full((12, target_w, 3), 255, dtype=np.uint8)
    return np.vstack([top, sep, grid])


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        boxes = _proposal_regions(img)
        processed_img = _make_contact_sheet(img, boxes)

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