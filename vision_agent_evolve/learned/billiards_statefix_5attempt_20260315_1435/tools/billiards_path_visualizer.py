from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Blue ball: RGB(100, 175, 220) -> HSV approx (105, 137, 220)
        ball_mask = cv2.inRange(hsv, (100, 100, 150), (115, 255, 255))
        # Arrow: HSV (49, 106, 215)
        arrow_mask = cv2.inRange(hsv, (40, 80, 150), (60, 150, 255))
        
        def get_centroid(mask):
            M = cv2.moments(mask)
            if M["m00"] == 0: return None
            return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

        ball_c = get_centroid(ball_mask)
        arrow_c = get_centroid(arrow_mask)
        
        if not ball_c or not arrow_c:
            return ToolResult(status="error", answer="Could not detect ball or arrow", artifacts=[])

        # Define table bounds (inner playing surface)
        # Based on visual inspection of 2.png
        x_min, x_max = 85, 1915
        y_min, y_max = 115, 885

        curr = np.array(ball_c, dtype=float)
        vec = np.array(arrow_c, dtype=float) - curr
        vec /= np.linalg.norm(vec)
        
        path = [tuple(curr.astype(int))]
        for _ in range(5): # Max 5 reflections
            # Find intersection with rails
            t = float('inf')
            hit = None
            # Check all 4 walls
            for wall in [('x', x_min), ('x', x_max), ('y', y_min), ('y', y_max)]:
                if wall[0] == 'x' and vec[0] != 0:
                    ti = (wall[1] - curr[0]) / vec[0]
                    if ti > 1e-3 and ti < t:
                        t, hit = ti, wall
                elif wall[0] == 'y' and vec[1] != 0:
                    ti = (wall[1] - curr[1]) / vec[1]
                    if ti > 1e-3 and ti < t:
                        t, hit = ti, wall
            
            curr = curr + vec * t
            path.append(tuple(curr.astype(int)))
            if hit[0] == 'x': vec[0] *= -1
            else: vec[1] *= -1

        vis = img.copy()
        for i in range(len(path)-1):
            cv2.line(vis, path[i], path[i+1], (0, 0, 255), 5)
        
        output_path = "artifacts/billiards_path.png"
        save_image(vis, output_path)

        return ToolResult(status="ok", answer="Path visualized", artifacts=[output_path])
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    import sys
    if len(sys.argv) < 2:
        sys.exit(1)
    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()