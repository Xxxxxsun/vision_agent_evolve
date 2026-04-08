from core.types import ToolResult
from tools.implementations.shared import load_image, save_image

import cv2
import numpy as np


def _to_bgr(img):
    arr = np.array(img)
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    if arr.shape[2] == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        bgr = _to_bgr(img)
        h, w = bgr.shape[:2]

        # Compute generic visual focus from contrast, edges, and color rarity.
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        lap = cv2.Laplacian(blur, cv2.CV_32F, ksize=3)
        edge_strength = cv2.convertScaleAbs(np.abs(lap))

        grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = cv2.magnitude(grad_x, grad_y)
        grad_mag = cv2.normalize(grad_mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        mean_color = np.mean(lab.reshape(-1, 3), axis=0)
        color_dist = np.sqrt(
            (l_chan.astype(np.float32) - mean_color[0]) ** 2 +
            (a_chan.astype(np.float32) - mean_color[1]) ** 2 +
            (b_chan.astype(np.float32) - mean_color[2]) ** 2
        )
        color_dist = cv2.normalize(color_dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        focus = cv2.addWeighted(grad_mag, 0.45, edge_strength, 0.3, 0)
        focus = cv2.addWeighted(focus, 0.7, color_dist, 0.3, 0)

        k = max(5, (min(h, w) // 40) | 1)
        focus = cv2.GaussianBlur(focus, (k, k), 0)
        _, mask = cv2.threshold(focus, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        area_min = max(64, (h * w) // 800)
        kept = np.zeros_like(mask)
        boxes = []
        for i in range(1, num_labels):
            x, y, bw, bh, area = stats[i]
            if area >= area_min:
                kept[labels == i] = 255
                boxes.append((x, y, bw, bh, area))

        overlay = bgr.copy()
        dimmed = (overlay * 0.45).astype(np.uint8)
        overlay = np.where(kept[:, :, None] > 0, overlay, dimmed)

        heat = cv2.applyColorMap(focus, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(overlay, 0.82, heat, 0.18, 0)

        for x, y, bw, bh, area in sorted(boxes, key=lambda t: t[4], reverse=True)[:12]:
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 255, 255), 2)
            cx = x + bw // 2
            cv2.line(overlay, (cx, y), (cx, y + bh), (255, 255, 255), 1)

        cv2.line(overlay, (w // 2, 0), (w // 2, h - 1), (255, 255, 255), 2)

        processed_img = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
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