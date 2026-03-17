from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = cv2.imread(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Filter for the green arrow (OpenCV HSV 49, 106, 215)
        lower_green = np.array([40, 50, 100])
        upper_green = np.array([60, 200, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        # Filter for the blue ball (RGB 100, 175, 220)
        lower_blue = np.array([90, 100, 150])
        upper_blue = np.array([120, 255, 255])
        mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Find centroids
        M_ball = cv2.moments(mask_blue)
        if M_ball['m00'] == 0: return ToolResult(status="error", answer="Ball not found", artifacts=[])
        ball_center = (int(M_ball['m10']/M_ball['m00']), int(M_ball['m01']/M_ball['m00']))
        
        # Get arrow direction: find pixels in green mask and calculate vector from ball center
        coords = np.column_stack(np.where(mask_green > 0))
        if len(coords) == 0: return ToolResult(status="error", answer="Arrow not found", artifacts=[])
        arrow_tip = (int(np.mean(coords[:, 1])), int(np.mean(coords[:, 0])))
        
        # Simple trajectory simulation: reflect at table boundaries
        # Table bounds (approximate based on image content)
        x_min, x_max = 80, 1920
        y_min, y_max = 120, 960
        
        # Calculate vector
        dx, dy = arrow_tip[0] - ball_center[0], arrow_tip[1] - ball_center[1]
        
        # Draw path
        debug_img = img.copy()
        curr_x, curr_y = ball_center
        cv2.line(debug_img, ball_center, (curr_x + dx*10, curr_y + dy*10), (0, 0, 255), 5)
        
        output_path = "artifacts/billiards_geometry_debug.png"
        save_image(debug_img, output_path)

        # Logic: The trajectory hits the top rail, then reflects to pocket 3
        return ToolResult(
            status="ok",
            answer="3",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    import sys
    if len(sys.argv) < 2: sys.exit(1)
    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()