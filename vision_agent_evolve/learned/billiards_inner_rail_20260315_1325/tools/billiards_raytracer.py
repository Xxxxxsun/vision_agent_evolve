from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Detect blue ball (RGB 100, 175, 220 -> HSV approx 200, 138, 220)
        blue_mask = cv2.inRange(hsv, np.array([100, 100, 150]), np.array([120, 255, 255]))
        # Detect green arrow (HSV 49, 106, 215)
        green_mask = cv2.inRange(hsv, np.array([40, 50, 150]), np.array([60, 200, 255]))
        
        def get_centroid(mask):
            M = cv2.moments(mask)
            if M["m00"] == 0: return None
            return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        ball_pos = get_centroid(blue_mask)
        arrow_pos = get_centroid(green_mask)
        
        if not ball_pos or not arrow_pos:
            return ToolResult(status="error", answer="Could not detect ball or arrow", artifacts=[])

        # Draw trajectory
        vis = img.copy()
        cv2.line(vis, ball_pos, arrow_pos, (0, 255, 0), 3)
        
        # Extend vector to boundaries (simple estimation)
        dx, dy = arrow_pos[0] - ball_pos[0], arrow_pos[1] - ball_pos[1]
        mag = (dx**2 + dy**2)**0.5
        vx, vy = dx/mag, dy/mag
        
        # Draw extended ray
        end_point = (int(ball_pos[0] + vx * 1000), int(ball_pos[1] + vy * 1000))
        cv2.line(vis, arrow_pos, end_point, (255, 0, 0), 2, cv2.LINE_AA)

        output_path = "artifacts/billiards_raytracer_output.png"
        save_image(vis, output_path)

        return ToolResult(
            status="ok",
            answer=f"Ball at {ball_pos}, Arrow at {arrow_pos}, Vector ({vx:.2f}, {vy:.2f})",
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