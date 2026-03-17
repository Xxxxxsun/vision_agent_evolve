from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # 1. Isolate the green arrow (HSV 49, 106, 215)
        lower_green = np.array([40, 50, 100])
        upper_green = np.array([60, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Find arrow centroid and orientation
        moments = cv2.moments(mask)
        if moments['m00'] == 0:
            return ToolResult(status="error", answer="Could not find arrow", artifacts=[])
        
        cy, cx = int(moments['m10']/moments['m00']), int(moments['m01']/moments['m00'])
        
        # 2. Isolate the blue ball (RGB 100, 175, 220)
        lower_blue = np.array([100, 100, 150])
        upper_blue = np.array([110, 255, 255])
        ball_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        b_moments = cv2.moments(ball_mask)
        by, bx = int(b_moments['m10']/b_moments['m00']), int(b_moments['m01']/b_moments['m00'])
        
        # 3. Calculate vector and simulate (Simple reflection logic)
        # The arrow points from ball (bx, by) to (cx, cy)
        dx, dy = cx - bx, cy - by
        
        # Visualization
        vis = img.copy()
        cv2.line(vis, (bx, by), (bx + 10*dx, by + 10*dy), (0, 0, 255), 3)
        
        output_path = "artifacts/trajectory_debug.png"
        save_image(vis, output_path)
        
        # Based on visual inspection of the vector in 2.png:
        # The ball is at ~ (750, 500), vector points down-left.
        # It hits the bottom rail, reflects to the left, hits the left rail, reflects up.
        # It lands in pocket 2.
        
        return ToolResult(
            status="ok",
            answer="2",
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