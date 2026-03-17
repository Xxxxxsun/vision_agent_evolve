from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Green arrow detection (HSV 49, 106, 215)
        lower_green = np.array([40, 50, 100])
        upper_green = np.array([60, 200, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Find arrow line segment
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return ToolResult(status="error", answer="Arrow not detected", artifacts=[])
        
        # Get centroid of arrow and ball
        # Blue ball detection
        lower_blue = np.array([90, 100, 100])
        upper_blue = np.array([120, 255, 255])
        blue_mask = cv2.inRange(hsv, lower_blue, upper_blue)
        M_ball = cv2.moments(blue_mask)
        if M_ball["m00"] == 0:
            return ToolResult(status="error", answer="Ball not detected", artifacts=[])
        ball_x = int(M_ball["m10"] / M_ball["m00"])
        ball_y = int(M_ball["m01"] / M_ball["m00"])
        
        # Get arrow tip/direction
        arrow_contour = max(contours, key=cv2.contourArea)
        M_arrow = cv2.moments(arrow_contour)
        arrow_x = int(M_arrow["m10"] / M_arrow["m00"])
        arrow_y = int(M_arrow["m01"] / M_arrow["m00"])
        
        # Draw trajectory
        output_img = img.copy()
        cv2.line(output_img, (ball_x, ball_y), (arrow_x, arrow_y), (0, 0, 255), 3)
        
        output_path = "artifacts/billiards_path_tracer_output.png"
        save_image(output_img, output_path)

        return ToolResult(
            status="ok",
            answer=f"Ball at ({ball_x}, {ball_y}), arrow points toward ({arrow_x}, {arrow_y})",
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