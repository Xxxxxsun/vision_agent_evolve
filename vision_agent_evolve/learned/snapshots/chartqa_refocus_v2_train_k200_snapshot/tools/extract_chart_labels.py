from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        labels_img = np.zeros(img.shape, dtype=np.uint8)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 10 < w < 200 and 10 < h < 50:
                cv2.rectangle(labels_img, (x, y), (x + w, y + h), (255, 255, 255), -1)

        output_path = "artifacts/extract_chart_labels_output.png"
        save_image(labels_img, output_path)

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