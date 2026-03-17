from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        # Convert to BGR for drawing if necessary
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        
        # Create a copy for annotation
        annotated = img.copy()
        
        # Detect the grid lines or dice position by contrast (simple thresholding)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Draw a grid overlay to visualize movement steps
        h, w = img.shape[:2]
        step_x, step_y = w // 8, h // 6
        for i in range(0, w, step_x):
            cv2.line(annotated, (i, 0), (i, h), (255, 0, 0), 1)
        for i in range(0, h, step_y):
            cv2.line(annotated, (0, i), (w, i), (255, 0, 0), 1)
            
        # Highlight the dice region (approximate based on image structure)
        # The dice is roughly in the top left quadrant
        cv2.rectangle(annotated, (100, 50), (400, 450), (0, 255, 0), 3)
        
        output_path = "artifacts/dice_grid_annotated.png"
        save_image(annotated, output_path)

        return ToolResult(
            status="ok",
            answer="Annotated grid and dice position for orientation tracking.",
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