from core.types import ToolResult
from tools.implementations.shared import load_image, save_image


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)

        import cv2
        import numpy as np

        if img is None:
            raise ValueError("Could not load image")

        arr = np.array(img)
        if arr.ndim == 2:
            bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        elif arr.shape[2] == 4:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        else:
            bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        h, w = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Spectral residual saliency for generic object prominence.
        small_w = max(64, min(256, w))
        small_h = max(64, min(256, h))
        small = cv2.resize(gray, (small_w, small_h), interpolation=cv2.INTER_AREA)
        small_f = small.astype(np.float32) + 1.0
        fft = np.fft.fft2(small_f)
        log_amp = np.log(np.abs(fft) + 1e-8)
        phase = np.angle(fft)
        avg = cv2.GaussianBlur(log_amp, (0, 0), 3)
        spectral_residual = log_amp - avg
        recon = np.fft.ifft2(np.exp(spectral_residual + 1j * phase))
        sal = np.abs(recon) ** 2
        sal = cv2.GaussianBlur(sal, (0, 0), 3)
        sal = cv2.resize(sal, (w, h), interpolation=cv2.INTER_CUBIC)
        sal = cv2.normalize(sal, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

        # Edge map to reveal object contours for later manual grounding.
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        med = float(np.median(blur))
        lower = int(max(0, 0.66 * med))
        upper = int(min(255, 1.33 * med + 20))
        edges = cv2.Canny(blur, lower, upper)
        edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

        # Build a heatmap overlay and annotate image center for left/right reasoning.
        heat = cv2.applyColorMap(sal, cv2.COLORMAP_JET)
        overlay = cv2.addWeighted(bgr, 0.62, heat, 0.38, 0)
        overlay[edges > 0] = (255, 255, 255)

        cv2.line(overlay, (w // 2, 0), (w // 2, h - 1), (0, 255, 255), max(1, w // 400))
        cv2.line(overlay, (0, h // 2), (w - 1, h // 2), (0, 255, 255), max(1, h // 400))

        # Add faint rule-of-thirds guides to support relative position inspection.
        guide_color = (180, 255, 180)
        t1x, t2x = w // 3, (2 * w) // 3
        t1y, t2y = h // 3, (2 * h) // 3
        for x in (t1x, t2x):
            cv2.line(overlay, (x, 0), (x, h - 1), guide_color, 1)
        for y in (t1y, t2y):
            cv2.line(overlay, (0, y), (w - 1, y), guide_color, 1)

        # Compose artifact with original, saliency, edges, and focused overlay.
        sal_bgr = cv2.cvtColor(sal, cv2.COLOR_GRAY2BGR)
        edge_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        top = np.hstack([bgr, sal_bgr])
        bottom = np.hstack([edge_bgr, overlay])
        panel = np.vstack([top, bottom])
        panel = cv2.cvtColor(panel, cv2.COLOR_BGR2RGB)

        output_path = "artifacts/generic_visual_focus_output.png"
        save_image(panel, output_path)

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