from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        
        # Create a copy for drawing
        output = img.copy()
        
        # Detect edges to find the cube structure
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        
        # Find lines to identify the grid structure
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=50, maxLineGap=10)
        
        # Draw a subtle grid overlay to help the agent visualize columns
        # We draw a light cyan grid to make columns distinct
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(output, (x1, y1), (x2, y2), (255, 255, 0), 1)
        
        # Add coordinate labels (placeholder for agent to fill in)
        # We draw a grid of points to help the agent map columns
        step = 40
        for i in range(0, w, step):
            for j in range(0, h, step):
                cv2.circle(output, (i, j), 2, (0, 0, 255), -1)

        output_path = "artifacts/grid_overlay_output.png"
        save_image(output, output_path)

        return ToolResult(
            status="ok",
            answer="Grid overlay applied to assist in column height identification.",
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