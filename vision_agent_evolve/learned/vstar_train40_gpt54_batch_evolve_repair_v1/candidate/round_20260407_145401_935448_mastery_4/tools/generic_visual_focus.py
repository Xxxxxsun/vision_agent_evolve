from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _candidate_regions(img: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, edge_mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1]
    sat = cv2.GaussianBlur(sat, (5, 5), 0)
    _, sat_mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    mask = cv2.bitwise_or(edge_mask, sat_mask)
    k = max(3, (min(h, w) // 100) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    image_area = float(h * w)
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = float(bw * bh)
        if area < image_area * 0.003 or area > image_area * 0.6:
            continue
        fill = cv2.contourArea(c) / max(area, 1.0)
        aspect = bw / max(bh, 1)
        if fill < 0.08 or aspect > 8 or aspect < 0.125:
            continue
        score = fill * area
        boxes.append((x, y, bw, bh, score))

    boxes.sort(key=lambda b: b[4], reverse=True)
    selected = []
    for box in boxes:
        x, y, bw, bh, score = box
        keep = True
        for sx, sy, sw, sh, _ in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.35:
                keep = False
                break
        if keep:
            selected.append(box)
        if len(selected) >= 12:
            break
    return selected


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        processed_img = img.copy()
        h, w = img.shape[:2]

        boxes = _candidate_regions(img)

        cv2.line(processed_img, (w // 2, 0), (w // 2, h - 1), (255, 255, 0), 2)
        cv2.putText(processed_img, "L", (max(10, w // 20), max(30, h // 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(processed_img, "R", (w - max(30, w // 20), max(30, h // 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)

        for i, (x, y, bw, bh, _) in enumerate(boxes, start=1):
            cx = x + bw // 2
            cy = y + bh // 2
            color = (0, 255, 0) if cx < w // 2 else (0, 140, 255)
            cv2.rectangle(processed_img, (x, y), (x + bw, y + bh), color, 2)
            cv2.drawMarker(processed_img, (cx, cy), color, markerType=cv2.MARKER_CROSS,
                           markerSize=max(12, min(h, w) // 30), thickness=2)
            cv2.line(processed_img, (cx, max(0, y - 12)), (cx, min(h - 1, y + bh + 12)), color, 1)
            label = f"{i}@{cx}"
            ty = y - 6 if y > 18 else y + 18
            cv2.putText(processed_img, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, color, 1, cv2.LINE_AA)

        output_path = "artifacts/generic_visual_focus_output.png"
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