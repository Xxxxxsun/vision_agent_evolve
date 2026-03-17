from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Blue ball mask (RGB 100, 175, 220 -> HSV approx 106, 137, 220)
        lower_blue = np.array([100, 100, 150])
        upper_blue = np.array([115, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)

        # Green arrow mask (RGB 158, 215, 126 -> HSV approx 49, 106, 215)
        lower_green = np.array([40, 50, 150])
        upper_green = np.array([60, 200, 255])
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        def get_centroid(mask):
            M = cv2.moments(mask)
            if M["m00"] == 0: return None
            return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        ball_center = get_centroid(blue_mask)
        arrow_center = get_centroid(green_mask)

        if not ball_center or not arrow_center:
            return ToolResult(status="error", answer="Could not detect ball or arrow.", artifacts=[])

        # Calculate vector and extend
        vec = np.array(arrow_center) - np.array(ball_center)
        vec = vec / np.linalg.norm(vec)
        
        # Draw path
        vis = img.copy()
        end_point = (int(ball_center[0] + vec[0] * 1000), int(ball_center[1] + vec[1] * 1000))
        cv2.line(vis, ball_center, end_point, (0, 0, 255), 3)
        cv2.circle(vis, ball_center, 10, (255, 0, 0), -1)

        output_path = "artifacts/billiards_trajectory.png"
        save_image(vis, output_path)

        return ToolResult(
            status="ok",
            answer=f"Ball at {ball_center}, direction vector {vec}",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    import sys
    if len(sys.argv) < 2:
        sys.exit(1)
    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()