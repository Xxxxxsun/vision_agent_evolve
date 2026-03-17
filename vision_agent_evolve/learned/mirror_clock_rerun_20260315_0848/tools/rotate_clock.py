from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import os

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        
        # Rotate 180 degrees
        processed_img = cv2.rotate(img, cv2.ROTATE_180)

        # Ensure directory exists
        output_path = "artifacts/rotate_clock_output.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="Applied 180-degree rotation to correct clock orientation.",
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