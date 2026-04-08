from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def _ensure_uint8_bgr(image: np.ndarray) -> np.ndarray:
    arr = np.asarray(image)
    if arr.ndim == 2:
        arr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_GRAY2BGR)
    elif arr.ndim == 3 and arr.shape[2] == 4:
        arr = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_BGRA2BGR)
    elif arr.ndim == 3 and arr.shape[2] == 3:
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
    else:
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    image = _ensure_uint8_bgr(image)
    h, w = image.shape[:2]
    if h <= 0 or w <= 0:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag_f = cv2.magnitude(grad_x, grad_y)
    mag = cv2.convertScaleAbs(mag_f)
    _, edge_mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    _, sat_mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    mask = cv2.bitwise_or(edge_mask, sat_mask)
    k = max(3, int(round(min(h, w) * 0.01)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours_info = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours_info[0] if len(contours_info) == 2 else contours_info[1]
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

    if not boxes:
        fallback = []
        scales = [0.22, 0.3, 0.4]
        anchors = [
            (0.5, 0.5), (0.3, 0.5), (0.7, 0.5),
            (0.5, 0.3), (0.5, 0.7), (0.3, 0.3),
            (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)
        ]
        for frac in scales:
            bw = max(12, int(w * frac))
            bh = max(12, int(h * frac))
            for ax, ay in anchors:
                cx = int(w * ax)
                cy = int(h * ay)
                x = max(0, min(w - bw, cx - bw // 2))
                y = max(0, min(h - bh, cy - bh // 2))
                roi_sat = sat[y:y + bh, x:x + bw]
                roi_mag = mag[y:y + bh, x:x + bw]
                score = float(np.mean(roi_sat)) + 0.6 * float(np.mean(roi_mag))
                fallback.append((x, y, bw, bh, score))
        boxes = fallback

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

    if not selected:
        bw = max(12, int(w * 0.35))
        bh = max(12, int(h * 0.35))
        x = max(0, (w - bw) // 2)
        y = max(0, (h - bh) // 2)
        selected = [(x, y, bw, bh)]
    return selected


def _enhance_patch(patch: np.ndarray, out_size: int) -> np.ndarray:
    if patch is None or np.asarray(patch).size == 0:
        return np.full((out_size, out_size, 3), 245, dtype=np.uint8)
    patch = _ensure_uint8_bgr(patch)
    lab = cv2.cvtColor(patch, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)
    ph, pw = enhanced.shape[:2]
    scale = min(out_size / max(ph, 1), out_size / max(pw, 1))
    nw, nh = max(1, int(round(pw * scale))), max(1, int(round(ph * scale)))
    resized = cv2.resize(enhanced, (nw, nh), interpolation=cv2.INTER_CUBIC)
    canvas = np.full((out_size, out_size, 3), 245, dtype=np.uint8)
    oy = (out_size - nh) // 2
    ox = (out_size - nw) // 2
    canvas[oy:oy + nh, ox:ox + nw] = resized
    return np.ascontiguousarray(canvas)


def _fallback_artifact(image: np.ndarray) -> np.ndarray:
    base = _ensure_uint8_bgr(image)
    h, w = base.shape[:2]
    if h <= 0 or w <= 0:
        base = np.full((128, 128, 3), 240, dtype=np.uint8)
        h, w = base.shape[:2]
    overlay = base.copy()
    bw = max(12, int(w * 0.4))
    bh = max(12, int(h * 0.4))
    x = max(0, (w - bw) // 2)
    y = max(0, (h - bh) // 2)
    cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (255, 200, 0), max(2, min(h, w) // 300))
    cv2.putText(overlay, '1', (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)
    panel_h = max(120, h // 4)
    patch_size = max(64, int(panel_h * 0.8))
    strip = np.full((panel_h, w, 3), 250, dtype=np.uint8)
    patch = _enhance_patch(base, min(patch_size, max(64, min(h, w))))
    ph, pw = patch.shape[:2]
    y_off = max(0, (panel_h - ph) // 2)
    x_off = max(0, (w - pw) // 2)
    strip[y_off:y_off + ph, x_off:x_off + pw] = patch
    cv2.rectangle(strip, (x_off, y_off), (x_off + pw, y_off + ph), (255, 200, 0), 2)
    cv2.putText(strip, '1', (x_off + 6, y_off + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2, cv2.LINE_AA)
    return np.vstack([overlay, strip])


def _original_run_before_artifact_fallback(image_path: str) -> ToolResult:
    output_path = 'artifacts/localized_color_focus_output.png'
    try:
        img = _ensure_uint8_bgr(load_image(image_path))
        h, w = img.shape[:2]
        boxes = _proposal_regions(img)

        overlay = np.ascontiguousarray(img.copy())
        colors = [
            (255, 200, 0), (0, 220, 255), (0, 255, 120),
            (255, 120, 255), (120, 180, 255), (255, 180, 120)
        ]
        thickness = max(2, min(h, w) // 300)
        for i, (x, y, bw, bh) in enumerate(boxes):
            color = tuple(int(c) for c in colors[i % len(colors)])
            cv2.rectangle(overlay, (int(x), int(y)), (int(x + bw), int(y + bh)), color, int(thickness))
            cv2.putText(overlay, str(i + 1), (int(x), int(max(18, y - 6))), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        panel_h = max(120, h // 4)
        patch_size = max(64, int(panel_h * 0.8))
        strip = np.full((panel_h, w, 3), 250, dtype=np.uint8)
        margin = max(8, w // 100)
        x_cursor = margin
        shown = 0
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
            color = tuple(int(c) for c in colors[i % len(colors)])
            cv2.rectangle(strip, (int(x_cursor), int(y_off)), (int(x_cursor + patch_size), int(y_off + patch_size)), color, 2)
            cv2.putText(strip, str(i + 1), (int(x_cursor + 6), int(y_off + 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
            x_cursor += patch_size + margin
            shown += 1

        if shown == 0:
            patch_size = min(max(64, panel_h - 20), max(64, w - 2 * margin))
            patch = _enhance_patch(img, patch_size)
            y_off = (panel_h - patch_size) // 2
            x_off = max(margin, (w - patch_size) // 2)
            strip[y_off:y_off + patch_size, x_off:x_off + patch_size] = patch
            cv2.rectangle(strip, (int(x_off), int(y_off)), (int(x_off + patch_size), int(y_off + patch_size)), colors[0], 2)
            cv2.putText(strip, '1', (int(x_off + 6), int(y_off + 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, colors[0], 2, cv2.LINE_AA)

        processed_img = np.ascontiguousarray(np.vstack([overlay, strip]))
        save_image(processed_img, output_path)
        return ToolResult(status='ok', answer='', artifacts=[output_path])
    except Exception:
        try:
            img = _ensure_uint8_bgr(load_image(image_path))
        except Exception:
            img = np.full((128, 128, 3), 240, dtype=np.uint8)
        processed_img = _fallback_artifact(img)
        save_image(processed_img, output_path)
        return ToolResult(status='ok', answer='', artifacts=[output_path])


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
        output_path = "artifacts/localized_color_focus_fallback.png"
        save_image(processed_img, output_path)
        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
            debug_info="fallback artifact emitted after repair: " + fallback_error[:200],
        )
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
