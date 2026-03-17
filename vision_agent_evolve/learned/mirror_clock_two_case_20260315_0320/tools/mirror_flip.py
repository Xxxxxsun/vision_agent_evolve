from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import os

def run(image_path: str) -> ToolResult:
    try:
        # Load image as numpy array
        img = load_image(image_path)
        
        # Flip horizontally (cv2.flip with flipCode 1)
        processed_img = cv2.flip(img, 1)

        # Ensure artifacts directory exists
        os.makedirs("artifacts", exist_ok=True)
        output_path = "artifacts/mirror_flip_output.png"
        
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="Image successfully flipped horizontally.",
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