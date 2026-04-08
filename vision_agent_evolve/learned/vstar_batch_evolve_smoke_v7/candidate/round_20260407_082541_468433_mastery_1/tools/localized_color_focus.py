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
    mag_u8 = cv2.convertScaleAbs(mag)
    _, edge = cv2.threshold(mag_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(edge, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.0008 or area > image_area * 0.2:
            continue
        if bw < max(8, w // 100) or bh < max(8, h // 100):
            continue
        boxes.append((x, y, bw, bh))
    return boxes


def _merge_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    merged = []
    for box in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
        x, y, w, h = box
        keep = True
        for mx, my, mw, mh in merged:
            ix1, iy1 = max(x, mx), max(y, my)
            ix2, iy2 = min(x + w, mx + mw), min(y + h, my + mh)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            union = w * h + mw * mh - inter
            if union > 0 and inter / union > 0.35:
                keep = False
                break
        if keep:
            merged.append(box)
    return merged


def _score_box(image: np.ndarray, box: tuple[int, int, int, int]) -> float:
    x, y, w, h = box
    patch = image[y:y + h, x:x + w]
    if patch.size == 0:
        return -1.0
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1].astype(np.float32).mean() / 255.0
    val_std = hsv[:, :, 2].astype(np.float32).std() / 255.0
    area = float(w * h) / float(image.shape[0] * image.shape[1])
    compact = 1.0 - min(abs((w / max(h, 1)) - 1.0), 2.0) / 2.0
    return 0.45 * sat + 0.35 * val_std + 0.15 * compact + 0.05 * (1.0 - area)


def _expand(box: tuple[int, int, int, int], shape: tuple[int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = box
    ih, iw = shape[:2]
    pad = int(0.2 * max(w, h)) + 4
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(iw, x + w + pad)
    y2 = min(ih, y + h + pad)
    return x1, y1, x2 - x1, y2 - y1


def _enhance_patch(patch: np.ndarray, size: int) -> np.ndarray:
    enlarged = cv2.resize(patch, (size, size), interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(enlarged, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
    return enhanced


def _make_contact_sheet(image: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    h, w = image.shape[:2]
    overlay = image.copy()
    colors = [(255, 200, 0), (0, 220, 255), (0, 255, 120), (255, 120, 255)]
    top = boxes[:4]
    for i, box in enumerate(top):
        x, y, bw, bh = box
        c = colors[i % len(colors)]
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), c, 2)
        cv2.putText(overlay, str(i + 1), (x, max(18, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2, cv2.LINE_AA)

    tile = max(120, min(w // 4, 220))
    sheet_h = h + tile + 20
    sheet = np.full((sheet_h, w, 3), 255, dtype=np.uint8)
    sheet[:h, :w] = overlay

    for i, box in enumerate(top):
        x, y, bw, bh = _expand(box, image.shape)
        patch = image[y:y + bh, x:x + bw]
        patch = _enhance_patch(patch, tile - 20)
        x0 = i * tile + 10
        if x0 + patch.shape[1] > w:
            break
        y0 = h + 10
        sheet[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
        cv2.putText(sheet, f"{i + 1}", (x0, y0 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2, cv2.LINE_AA)

    return sheet


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        boxes = _proposal_regions(img)
        boxes = _merge_boxes(boxes)
        boxes = sorted(boxes, key=lambda b: _score_box(img, b), reverse=True)
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