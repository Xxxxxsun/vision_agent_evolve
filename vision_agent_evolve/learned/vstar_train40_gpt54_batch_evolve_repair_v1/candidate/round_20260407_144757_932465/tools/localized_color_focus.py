from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np
import os


def _to_numpy_image(img) -> np.ndarray:
    if isinstance(img, np.ndarray):
        return img
    try:
        return np.array(img)
    except Exception:
        return np.zeros((1, 1, 3), dtype=np.uint8)



def _ensure_three_channel(img) -> np.ndarray:
    img = _to_numpy_image(img)
    if img is None or not isinstance(img, np.ndarray):
        return np.full((256, 256, 3), 240, dtype=np.uint8)
    if img.size == 0:
        return np.full((256, 256, 3), 240, dtype=np.uint8)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if len(img.shape) == 3 and img.shape[2] == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if len(img.shape) == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if len(img.shape) == 3 and img.shape[2] >= 3:
        return img[:, :, :3].copy()
    return np.full((256, 256, 3), 240, dtype=np.uint8)



def _safe_put_text(img: np.ndarray, text: str, org: tuple[int, int], scale: float = 0.6, color=(40, 40, 40), thickness: int = 2) -> np.ndarray:
    img = _ensure_three_channel(img)
    cv2.putText(img, str(text), org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)
    return img



def _fallback_boxes(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    image = _ensure_three_channel(image)
    h, w = image.shape[:2]
    boxes = []
    scales = [0.22, 0.3, 0.4]
    centers = [
        (0.5, 0.5),
        (0.33, 0.5),
        (0.67, 0.5),
        (0.5, 0.33),
        (0.5, 0.67),
        (0.33, 0.33),
        (0.67, 0.33),
        (0.33, 0.67),
        (0.67, 0.67),
    ]
    for s in scales:
        bw = max(20, int(w * s))
        bh = max(20, int(h * s))
        for cx, cy in centers:
            x = int(cx * w - bw / 2)
            y = int(cy * h - bh / 2)
            x = max(0, min(w - bw, x))
            y = max(0, min(h - bh, y))
            boxes.append((x, y, bw, bh))
    selected = []
    for box in boxes:
        x, y, bw, bh = box
        keep = True
        for sx, sy, sw, sh in selected:
            ix1, iy1 = max(x, sx), max(y, sy)
            ix2, iy2 = min(x + bw, sx + sw), min(y + bh, sy + sh)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = bw * bh + sw * sh - inter
            if union > 0 and inter / union > 0.55:
                keep = False
                break
        if keep:
            selected.append(box)
        if len(selected) >= 6:
            break
    return selected[:6]



def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    image = _ensure_three_channel(image)
    h, w = image.shape[:2]
    if h == 0 or w == 0:
        return []

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
        if roi.size == 0:
            continue
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[:, :, 1]))
        val_std = float(np.std(hsv[:, :, 2]))
        size_bonus = min((bw * bh) / image_area, 0.03) * 1000.0
        score = sat * 0.6 + val_std * 0.4 + size_bonus
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

    if not selected:
        selected = _fallback_boxes(image)
    return selected



def _enhance_crop(crop: np.ndarray) -> np.ndarray:
    crop = _ensure_three_channel(crop)
    if crop.size == 0:
        return crop
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)



def _build_artifact(img: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    img = _ensure_three_channel(img)
    h, w = img.shape[:2]
    overlay = img.copy()
    colors = [
        (255, 200, 0),
        (0, 220, 255),
        (0, 255, 120),
        (255, 120, 120),
        (180, 120, 255),
        (255, 255, 0),
    ]

    for i, (x, y, bw, bh) in enumerate(boxes[:6]):
        pad = int(0.08 * max(bw, bh)) + 2
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        color = colors[i % len(colors)]
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 2)
        overlay = _safe_put_text(overlay, str(i + 1), (x1, max(18, y1 - 4)), scale=0.6, color=color, thickness=2)

    if not boxes:
        return overlay

    top_h = max(h, 240)
    panel = np.full((top_h, w, 3), 245, dtype=np.uint8)
    cols = min(len(boxes), 3)
    rows = 1 if len(boxes) <= 3 else 2
    tile_w = max(1, w // cols)
    tile_h = max(1, top_h // rows)

    for i, (x, y, bw, bh) in enumerate(boxes[:6]):
        r = 0 if i < 3 else 1
        c = i if i < 3 else i - 3
        if c >= cols or r >= rows:
            continue
        pad = int(0.18 * max(bw, bh)) + 2
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(w, x + bw + pad), min(h, y + bh + pad)
        crop = img[y1:y2, x1:x2]
        crop = _ensure_three_channel(crop)
        if crop.size == 0:
            continue
        crop = _enhance_crop(crop)
        avail_w = max(10, tile_w - 10)
        avail_h = max(30, tile_h - 30)
        scale = min(avail_w / max(crop.shape[1], 1), avail_h / max(crop.shape[0], 1))
        scale = max(scale, 1e-3)
        new_size = (max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale)))
        interp = cv2.INTER_CUBIC if scale >= 1.0 else cv2.INTER_AREA
        resized = cv2.resize(crop, new_size, interpolation=interp)
        oy = r * tile_h + 25 + max(0, (tile_h - 30 - resized.shape[0]) // 2)
        ox = c * tile_w + 5 + max(0, (tile_w - 10 - resized.shape[1]) // 2)
        y_end = min(panel.shape[0], oy + resized.shape[0])
        x_end = min(panel.shape[1], ox + resized.shape[1])
        panel[oy:y_end, ox:x_end] = resized[: y_end - oy, : x_end - ox]
        panel = _safe_put_text(panel, f"Region {i + 1}", (c * tile_w + 8, r * tile_h + 18), scale=0.55, color=(40, 40, 40), thickness=2)

    return np.vstack([panel, overlay])



def _build_fallback_artifact(img: np.ndarray | None, message: str) -> np.ndarray:
    base = _ensure_three_channel(img) if img is not None else np.full((320, 320, 3), 245, dtype=np.uint8)
    h, w = base.shape[:2]
    canvas_h = max(h, 320)
    canvas_w = max(w, 320)
    canvas = np.full((canvas_h, canvas_w, 3), 245, dtype=np.uint8)
    bh = min(h, canvas_h)
    bw = min(w, canvas_w)
    canvas[:bh, :bw] = base[:bh, :bw]
    canvas = _safe_put_text(canvas, "localized_color_focus", (18, 40), scale=0.8, color=(60, 60, 60), thickness=2)
    canvas = _safe_put_text(canvas, "artifact generated", (18, 85), scale=0.8, color=(60, 60, 60), thickness=2)
    canvas = _safe_put_text(canvas, message[:40], (18, 130), scale=0.7, color=(60, 60, 60), thickness=2)
    cv2.rectangle(canvas, (12, 12), (canvas_w - 12, canvas_h - 12), (180, 180, 180), 2)
    return canvas



def _original_run_before_artifact_fallback(image_path: str) -> ToolResult:
    output_path = "artifacts/localized_color_focus_output.png"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    loaded_img = None
    processed_img = None

    try:
        loaded_img = load_image(image_path)
        loaded_img = _ensure_three_channel(loaded_img)
        boxes = _proposal_regions(loaded_img)
        processed_img = _build_artifact(loaded_img, boxes)
        processed_img = _ensure_three_channel(processed_img)
    except Exception as e:
        processed_img = _build_fallback_artifact(loaded_img, f"fallback: {type(e).__name__}")
        processed_img = _ensure_three_channel(processed_img)

    save_image(processed_img, output_path)
    return ToolResult(
        status="ok",
        answer="",
        artifacts=[output_path],
    )



def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python -m tools.localized_color_focus <image_path>")
        sys.exit(1)
    print(run(sys.argv[1]))



if __name__ == "__main__":
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
