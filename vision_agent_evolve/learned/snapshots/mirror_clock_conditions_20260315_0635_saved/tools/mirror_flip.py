from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        # Perform horizontal flip (flipCode 1 means horizontal)
        processed_img = cv2.flip(img, 1)

        output_path = "artifacts/mirror_flip_output.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="Image horizontally flipped to correct mirror effect.",
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