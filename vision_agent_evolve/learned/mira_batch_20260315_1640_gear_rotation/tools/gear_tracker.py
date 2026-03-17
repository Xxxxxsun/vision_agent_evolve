from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect circular gear centers using Hough Circles
        # Gears are dark, centers are light/white circles
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=50,
            param1=50, param2=30, minRadius=15, maxRadius=60
        )

        output_img = img.copy()
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for i, (x, y, r) in enumerate(circles[0, :]):
                # Draw center point
                cv2.circle(output_img, (x, y), 5, (0, 255, 0), -1)
                # Label gear index
                cv2.putText(output_img, f"G{i+1}", (x + 10, y - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        output_path = "artifacts/gear_tracker_output.png"
        save_image(output_img, output_path)

        return ToolResult(
            status="ok",
            answer="Labeled gear centers to assist in manual rotation tracing.",
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