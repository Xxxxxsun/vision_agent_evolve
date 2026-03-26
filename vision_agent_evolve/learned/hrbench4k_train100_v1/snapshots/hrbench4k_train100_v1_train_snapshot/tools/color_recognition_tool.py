from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2HSV)

        # Define range for yellow detection (shirt)
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])
        yellow_mask = cv2.inRange(hsv_img, lower_yellow, upper_yellow)

        # Use mask to find regions with yellow
        yellow_regions = cv2.bitwise_and(hsv_img, hsv_img, mask=yellow_mask)

        # Extract backpack color in proximity to detected yellow regions
        backpack_color_img = extract_backpack_color(yellow_regions, hsv_img)

        output_path = "artifacts/color_recognition_tool_output.png"
        save_image(backpack_color_img, output_path)

        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))


def extract_backpack_color(yellow_regions, hsv_img):
    # Detect contours in yellow_regions
    contours, _ = cv2.findContours(cv2.cvtColor(yellow_regions, cv2.COLOR_RGB2GRAY), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Assume backpack is close to the largest yellow contour
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)

        # Define region to check for backpack color (simplified assumption)
        backpack_region = hsv_img[y:y+int(h*1.5), x+w:x+w+int(w*0.5)]
        avg_color = cv2.mean(backpack_region)[:3]

        # Create a solid image displaying detected color
        backpack_color_img = np.full((100, 100, 3), avg_color, dtype=np.uint8)
        backpack_color_img = cv2.cvtColor(backpack_color_img, cv2.COLOR_HSV2RGB)

        return backpack_color_img
    return np.zeros_like(hsv_img)


def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        sys.exit(1)

    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()
