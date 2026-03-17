from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import os

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        
        # Rotate the image 180 degrees to fix the upside-down orientation
        # cv2.ROTATE_180 is the standard way to flip both vertically and horizontally
        processed_img = cv2.rotate(img, cv2.ROTATE_180)

        # Create directory if it doesn't exist
        output_dir = "artifacts/rotation_fixer"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/rotation_fixer_output.png"
        
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="Clock face rotated 180 degrees to correct upside-down orientation.",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        sys.exit(1)

    result = run(sys.argv[1])
    print(f"ANSWER: {result.answer}")
    print(f"STATUS: {result.status}")
    print(f"ARTIFACTS: {','.join(result.artifacts)}")

if __name__ == "__main__":
    main()