import cv2
import sys
from core.types import ToolResult
from tools.implementations.shared import load_image, save_image

def run(image_path: str) -> ToolResult:
    try:
        # Load the image using the shared helper
        img = load_image(image_path)
        
        # Perform horizontal flip to correct the mirror reflection
        # 1 indicates horizontal flip in OpenCV
        processed_img = cv2.flip(img, 1)

        # Save the processed image to artifacts
        output_path = "artifacts/mirror_corrected.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="Successfully flipped the image horizontally to correct mirror reflection.",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <image_path>")
        sys.exit(1)

    result = run(sys.argv[1])
    print(f"ANSWER: {result.answer}")
    print(f"STATUS: {result.status}")
    print(f"ARTIFACTS: {','.join(result.artifacts)}")

if __name__ == "__main__":
    main()