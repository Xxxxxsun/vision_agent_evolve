from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)

        # Convert image to grayscale
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply threshold to get binary image
        _, binary_img = cv2.threshold(gray_img, 200, 255, cv2.THRESH_BINARY_INV)

        # Find contours
        contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        heights = []

        # Extract height of each bar
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            heights.append(h)

        # Apply approximation logic to refine results
        # Calculate average height and refine

        average_height = np.mean(heights)
        refined_heights = [h if abs(h - average_height) < (0.1 * average_height) else average_height for h in heights]

        # Draw refined heights on image for visualization
        processed_img = img.copy()
        for i, h in enumerate(refined_heights):
            x, y, w = cv2.boundingRect(contours[i])[:3]
            cv2.rectangle(processed_img, (x, y), (x + w, y + int(h)), (0, 0, 255), 1)

        output_path = "artifacts/chart_bar_approximation_tool_output.png"
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