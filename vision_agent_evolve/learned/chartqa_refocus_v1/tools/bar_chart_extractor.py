from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np
from PIL import Image


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Use thresholding to create binary image
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter out contours to get bars
        bars = [cnt for cnt in contours if cv2.contourArea(cnt) > 1000]

        # Draw bounding boxes around bars
        processed_img = img.copy()
        for bar in bars:
            x, y, w, h = cv2.boundingRect(bar)
            cv2.rectangle(processed_img, (x, y), (x+w, y+h), (0, 255, 0), 2)

        output_path = "artifacts/bar_chart_extractor_output.png"
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
