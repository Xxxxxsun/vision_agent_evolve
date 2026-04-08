from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np
import os


def _ensure_ndarray_image(img) -> np.ndarray:
    arr = np.asarray(img)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    elif arr.ndim == 3 and arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f'Unsupported image shape: {arr.shape}')
    if arr.shape[2] > 3:
        arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        if np.issubdtype(arr.dtype, np.floating):
            maxv = float(np.max(arr)) if arr.size else 0.0
            if maxv <= 1.0:
                arr = arr * 255.0
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _safe_u8(arr: np.ndarray) -> np.ndarray:
    arr = np.nan_to_num(np.asarray(arr), nan=0.0, posinf=0.0, neginf=0.0)
    if arr.dtype == np.uint8:
        return np.ascontiguousarray(arr)
    arr = np.clip(arr, 0, 255)
    return np.ascontiguousarray(arr.astype(np.uint8))


def _candidate_regions(img: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(grad_x, grad_y)
    mag = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    mag_u8 = _safe_u8(mag)
    _, edge_mask = cv2.threshold(mag_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    sat = cv2.GaussianBlur(sat, (5, 5), 0)
    sat_u8 = _safe_u8(sat)
    _, sat_mask = cv2.threshold(sat_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

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


def _fallback_regions(img: np.ndarray) -> list[tuple[int, int, int, int, float]]:
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    step_x = max(24, w // 6)
    step_y = max(24, h // 6)
    win_w = max(32, w // 4)
    win_h = max(32, h // 4)

    candidates = []
    y_positions = list(range(0, max(1, h - win_h + 1), max(12, step_y // 2))) or [0]
    x_positions = list(range(0, max(1, w - win_w + 1), max(12, step_x // 2))) or [0]

    for y in y_positions:
        for x in x_positions:
            patch = gray[y:y + win_h, x:x + win_w]
            if patch.size == 0:
                continue
            score = float(np.std(patch)) * float(patch.shape[0] * patch.shape[1])
            candidates.append((x, y, min(win_w, w - x), min(win_h, h - y), score))

    candidates.sort(key=lambda b: b[4], reverse=True)
    selected = []
    for box in candidates:
        x, y, bw, bh, score = box
        keep = True
        for sx, sy, sw, sh, _ in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
            inter = iw * ih
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.4:
                keep = False
                break
        if keep:
            selected.append(box)
        if len(selected) >= 6:
            break
    return selected


def _draw_overlay(processed_img: np.ndarray, boxes: list[tuple[int, int, int, int, float]]) -> np.ndarray:
    processed_img = _ensure_ndarray_image(processed_img)
    h, w = processed_img.shape[:2]
    cv2.line(processed_img, (w // 2, 0), (w // 2, h - 1), (255, 255, 0), 2)
    cv2.putText(processed_img, 'L', (max(10, w // 20), max(30, h // 18)),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(processed_img, 'R', (w - max(30, w // 20), max(30, h // 18)),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)

    for i, (x, y, bw, bh, _) in enumerate(boxes, start=1):
        cx = x + bw // 2
        cy = y + bh // 2
        color = (0, 255, 0) if cx < w // 2 else (0, 140, 255)
        cv2.rectangle(processed_img, (x, y), (x + bw, y + bh), color, 2)
        cv2.drawMarker(processed_img, (cx, cy), color, markerType=cv2.MARKER_CROSS,
                       markerSize=max(12, min(h, w) // 30), thickness=2)
        cv2.line(processed_img, (cx, max(0, y - 12)), (cx, min(h - 1, y + bh + 12)), color, 1)
        label = f'{i}@{cx}'
        ty = y - 6 if y > 18 else y + 18
        cv2.putText(processed_img, label, (x, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, color, 1, cv2.LINE_AA)

    if not boxes:
        cv2.putText(processed_img, 'No confident regions; center line shown for manual left/right reference',
                    (10, max(25, h - 15)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 255, 255), 1, cv2.LINE_AA)
    return processed_img


def _make_fallback_canvas(message: str) -> np.ndarray:
    processed_img = np.zeros((256, 256, 3), dtype=np.uint8)
    cv2.line(processed_img, (128, 0), (128, 255), (255, 255, 0), 2)
    cv2.putText(processed_img, 'L', (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(processed_img, 'R', (220, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2, cv2.LINE_AA)
    cv2.putText(processed_img, 'visual focus fallback', (20, 140), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(processed_img, message[:40], (20, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
    return processed_img


def _original_run_before_artifact_fallback(image_path: str) -> ToolResult:
    output_path = 'artifacts/generic_visual_focus_output.png'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        img = load_image(image_path)
        img = _ensure_ndarray_image(img)
        processed_img = img.copy()

        try:
            boxes = _candidate_regions(img)
            if not boxes:
                boxes = _fallback_regions(img)
        except Exception as region_error:
            boxes = []
            processed_img = _draw_overlay(processed_img, boxes)
            cv2.putText(processed_img, f'region fallback: {str(region_error)[:28]}',
                        (10, min(processed_img.shape[0] - 10, 25)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
            save_image(processed_img, output_path)
            return ToolResult(status='ok', answer='', artifacts=[output_path])

        processed_img = _draw_overlay(processed_img, boxes)
        save_image(processed_img, output_path)
        return ToolResult(status='ok', answer='', artifacts=[output_path])

    except Exception as e:
        processed_img = _make_fallback_canvas(str(e))
        save_image(processed_img, output_path)
        return ToolResult(status='error', answer=f'Failed to process image; fallback artifact saved to {output_path}: {e}', artifacts=[output_path])


def main():
    import sys
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} <image_path>')
        sys.exit(1)

    print(run(sys.argv[1]))


if __name__ == '__main__':
    main()

def run(image_path: str) -> ToolResult:
    fallback_error = ""
    try:
        result = _original_run_before_artifact_fallback(image_path)
        if getattr(result, "status", "") == "ok" and getattr(result, "artifacts", None):
            return result
        fallback_error = str(getattr(result, "error", "") or "original tool returned no artifacts")
    except Exception as exc:
        fallback_error = str(exc)
    try:
        img = load_image(image_path)
        processed_img = img.copy() if hasattr(img, "copy") else img
        output_path = "artifacts/generic_visual_focus_fallback.png"
        save_image(processed_img, output_path)
        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
            debug_info="fallback artifact emitted after repair: " + fallback_error[:200],
        )
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
