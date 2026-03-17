from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        # Load image using shared helper
        img = load_image(image_path)
        
        # Perform horizontal flip
        # cv2.flip with flipCode 1 flips horizontally
        processed_img = cv2.flip(img, 1)

        output_path = "artifacts/mirror_fixer_output.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="The image has been horizontally flipped to correct the mirror effect.",
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