from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import sys

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        
        # Perform horizontal flip (mirror transformation)
        # 1 indicates horizontal flip in cv2.flip
        processed_img = cv2.flip(img, 1)

        output_path = "artifacts/mirror_flip_output.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="The image has been horizontally flipped to correct the mirror reflection.",
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