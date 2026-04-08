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

        # Spectral residual saliency for generic object-like regions
        small_w = max(64, min(256, w))
        small_h = max(64, min(256, h))
        small = cv2.resize(gray, (small_w, small_h), interpolation=cv2.INTER_AREA)
        small_f = small.astype(np.float32) + 1.0
        fft = np.fft.fft2(small_f)
        log_amp = np.log(np.abs(fft) + 1e-8)
        phase = np.angle(fft)
        avg_log_amp = cv2.blur(log_amp, (3, 3))
        spectral_residual = log_amp - avg_log_amp
        saliency = np.abs(np.fft.ifft2(np.exp(spectral_residual + 1j * phase))) ** 2
        saliency = cv2.GaussianBlur(saliency.astype(np.float32), (9, 9), 0)
        saliency = cv2.normalize(saliency, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        saliency = cv2.resize(saliency, (w, h), interpolation=cv2.INTER_CUBIC)

        # Blend saliency with edges to favor meaningful object boundaries
        edges = cv2.Canny(gray, 80, 160)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
        combined = cv2.addWeighted(saliency, 0.8, edges, 0.2, 0)

        thr = int(np.clip(np.mean(combined) + 0.7 * np.std(combined), 80, 200))
        _, mask = cv2.threshold(combined, thr, 255, cv2.THRESH_BINARY)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        min_area = max(80, (h * w) // 1200)

        overlay = bgr.copy()
        heat = cv2.applyColorMap(saliency, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(overlay, 0.65, heat, 0.35, 0)

        kept = []
        for i in range(1, num_labels):
            x, y, bw, bh, area = stats[i]
            if area < min_area:
                continue
            if bw >= 0.95 * w and bh >= 0.95 * h:
                continue
            cx, cy = centroids[i]
            kept.append((area, x, y, bw, bh, int(cx), int(cy)))

        kept.sort(reverse=True)
        kept = kept[:12]

        for rank, (_, x, y, bw, bh, cx, cy) in enumerate(kept, start=1):
            color = (0, 255, 0) if rank <= 6 else (255, 255, 0)
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), color, 2)
            cv2.drawMarker(overlay, (cx, cy), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=16, thickness=2)
            cv2.putText(overlay, f"{rank}", (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)

        panel_h = max(80, h // 7)
        legend = np.full((panel_h, w, 3), 245, dtype=np.uint8)
        t1 = "Saliency focus map: highlighted regions are likely object candidates"
        t2 = "Use box/center locations to compare two referenced objects for left-right or above-below reasoning"
        cv2.putText(legend, t1, (12, panel_h // 3), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)
        cv2.putText(legend, t2, (12, 2 * panel_h // 3), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (40, 40, 40), 2, cv2.LINE_AA)

        processed_img = np.vstack([overlay, legend])

        output_path = "artifacts/saliency_focus_map_output.png"
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
