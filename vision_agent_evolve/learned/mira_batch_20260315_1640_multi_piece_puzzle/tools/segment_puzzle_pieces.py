from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np
import os

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        h, w = img.shape[:2]
        
        # The image is a 3x3 grid. We need to find the grid lines.
        # Convert to grayscale and detect edges to find the grid.
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Find grid lines by looking at projections
        v_proj = np.sum(thresh, axis=0)
        h_proj = np.sum(thresh, axis=1)
        
        # Simple heuristic: find peaks in projections
        def get_lines(proj, threshold=0.1):
            lines = []
            for i in range(1, len(proj)-1):
                if proj[i] > threshold * np.max(proj) and proj[i-1] < proj[i] and proj[i+1] < proj[i]:
                    lines.append(i)
            return lines

        # For a 3x3 grid, we expect 2 internal lines in each dimension
        # If auto-detection fails, we fallback to uniform grid division
        v_lines = get_lines(v_proj)
        h_lines = get_lines(h_proj)
        
        if len(v_lines) < 2 or len(h_lines) < 2:
            # Fallback to uniform grid
            v_cuts = [0, w//3, 2*w//3, w]
            h_cuts = [0, h//3, 2*h//3, h]
        else:
            v_cuts = [0] + sorted(v_lines)[:2] + [w]
            h_cuts = [0] + sorted(h_lines)[:2] + [h]

        os.makedirs("artifacts/pieces", exist_ok=True)
        artifact_paths = []
        
        count = 1
        for i in range(3):
            for j in range(3):
                piece = img[h_cuts[i]:h_cuts[i+1], v_cuts[j]:v_cuts[j+1]]
                path = f"artifacts/pieces/piece_{count}.png"
                save_image(piece, path)
                artifact_paths.append(path)
                count += 1

        return ToolResult(
            status="ok",
            answer="Successfully segmented 9 pieces into artifacts/pieces/",
            artifacts=artifact_paths,
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