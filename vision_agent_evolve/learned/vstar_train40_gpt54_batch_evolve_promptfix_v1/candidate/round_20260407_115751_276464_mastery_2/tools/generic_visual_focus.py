from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        if img is None:
            raise ValueError("Failed to load image")

        if len(img.shape) == 2:
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        else:
            bgr = img.copy()

        h, w = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Saliency-like map from spectral residual when available; fallback to local contrast.
        saliency_map = None
        try:
            if hasattr(cv2, 'saliency') and hasattr(cv2.saliency, 'StaticSaliencySpectralResidual_create'):
                sal = cv2.saliency.StaticSaliencySpectralResidual_create()
                ok, smap = sal.computeSaliency(bgr)
                if ok:
                    saliency_map = (smap * 255).astype(np.uint8)
        except Exception:
            saliency_map = None

        if saliency_map is None:
            blur_small = cv2.GaussianBlur(gray, (5, 5), 0)
            blur_large = cv2.GaussianBlur(gray, (0, 0), max(3, min(h, w) / 30.0))
            local_contrast = cv2.absdiff(blur_small, blur_large)
            saliency_map = cv2.normalize(local_contrast, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Edge emphasis for object boundaries.
        med = float(np.median(gray))
        lo = int(max(0, 0.66 * med))
        hi = int(min(255, 1.33 * med + 10))
        edges = cv2.Canny(gray, lo, hi)
        edge_dilate = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

        # Smooth saliency and extract candidate regions generically.
        sal_blur = cv2.GaussianBlur(saliency_map, (0, 0), max(1.0, min(h, w) / 120.0))
        thresh_val = int(np.clip(np.mean(sal_blur) + 0.5 * np.std(sal_blur), 60, 200))
        _, mask = cv2.threshold(sal_blur, thresh_val, 255, cv2.THRESH_BINARY)
        k = max(3, int(min(h, w) * 0.01))
        if k % 2 == 0:
            k += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Overlay heatmap.
        heat = cv2.applyColorMap(sal_blur, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(bgr, 0.62, heat, 0.38, 0)

        # Draw generic candidate boxes for prominent regions only.
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        min_area = max(64, int(h * w * 0.002))
        max_area = int(h * w * 0.5)
        kept = []
        for i in range(1, num_labels):
            x, y, bw, bh, area = stats[i]
            if area < min_area or area > max_area:
                continue
            aspect = bw / float(max(bh, 1))
            if aspect > 12 or aspect < 0.08:
                continue
            kept.append((area, x, y, bw, bh))
        kept.sort(reverse=True)
        kept = kept[:12]

        for _, x, y, bw, bh in kept:
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (255, 255, 255), 2)

        # Add edges as bright contours to aid manual localization.
        edge_mask = edge_dilate > 0
        overlay[edge_mask] = (255, 255, 255)

        # Side guides to support later left/right judgment without deciding it here.
        cv2.line(overlay, (w // 2, 0), (w // 2, h), (0, 255, 255), 2)
        cv2.line(overlay, (w // 3, 0), (w // 3, h), (180, 180, 180), 1)
        cv2.line(overlay, (2 * w // 3, 0), (2 * w // 3, h), (180, 180, 180), 1)

        output_path = "artifacts/generic_visual_focus_output.png"
        save_image(overlay, output_path)

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