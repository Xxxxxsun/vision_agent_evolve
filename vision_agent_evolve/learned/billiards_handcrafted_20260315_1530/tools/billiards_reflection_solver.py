from __future__ import annotations

import math

import cv2
import numpy as np

from core.types import ToolResult
from tools.implementations.shared import load_image, save_image


def _mask_centroid(mask: np.ndarray) -> np.ndarray | None:
    moments = cv2.moments(mask)
    if moments["m00"] == 0:
        return None
    return np.array(
        [moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]],
        dtype=float,
    )


def _first_dark_along_row(row: np.ndarray, start: int, step: int, threshold: int = 60) -> int:
    index = start
    while 0 <= index < len(row):
        if int(row[index]) < threshold:
            return index
        index += step
    raise ValueError("Failed to detect inner rail boundary on row scan.")


def _first_dark_along_col(col: np.ndarray, start: int, step: int, threshold: int = 60) -> int:
    index = start
    while 0 <= index < len(col):
        if int(col[index]) < threshold:
            return index
        index += step
    raise ValueError("Failed to detect inner rail boundary on column scan.")


def _detect_ball_and_arrow(hsv: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Blue ball: centered on RGB(100, 175, 220), converted to a stable HSV neighborhood.
    blue_mask = cv2.inRange(hsv, (95, 80, 120), (125, 255, 255))
    # Muted green arrow: centered on the provided OpenCV HSV (49, 106, 215).
    green_mask = cv2.inRange(hsv, (43, 70, 120), (55, 180, 255))

    ball_center = _mask_centroid(blue_mask)
    if ball_center is None:
        raise ValueError("Could not detect the blue ball.")

    arrow_points_y, arrow_points_x = np.where(green_mask > 0)
    if len(arrow_points_x) == 0:
        raise ValueError("Could not detect the green direction arrow.")

    arrow_points = np.column_stack([arrow_points_x, arrow_points_y]).astype(float)
    distances_to_ball = np.linalg.norm(arrow_points - ball_center, axis=1)
    tail = arrow_points[int(np.argmin(distances_to_ball))]
    tip = arrow_points[int(np.argmax(distances_to_ball))]
    direction = tip - tail
    norm = float(np.linalg.norm(direction))
    if norm == 0:
        raise ValueError("Detected arrow has zero-length direction vector.")
    direction /= norm

    return ball_center, tail, tip, direction, green_mask


def _detect_inner_bounds(gray: np.ndarray, ball_center: np.ndarray) -> tuple[int, int, int, int]:
    x = int(round(ball_center[0]))
    y = int(round(ball_center[1]))
    row = gray[y]
    col = gray[:, x]
    left = _first_dark_along_row(row, x, -1)
    right = _first_dark_along_row(row, x, 1)
    top = _first_dark_along_col(col, y, -1)
    bottom = _first_dark_along_col(col, y, 1)
    return left, right, top, bottom


def _pocket_map(left: int, right: int, top: int, bottom: int) -> dict[int, np.ndarray]:
    mid_x = (left + right) / 2.0
    return {
        1: np.array([left, top], dtype=float),
        2: np.array([mid_x, top], dtype=float),
        3: np.array([right, top], dtype=float),
        4: np.array([left, bottom], dtype=float),
        5: np.array([mid_x, bottom], dtype=float),
        6: np.array([right, bottom], dtype=float),
    }


def _trace_to_pocket(
    ball_center: np.ndarray,
    direction: np.ndarray,
    left: int,
    right: int,
    top: int,
    bottom: int,
    max_bounces: int = 8,
    pocket_tolerance: float = 85.0,
) -> tuple[int | None, list[np.ndarray]]:
    pockets = _pocket_map(left, right, top, bottom)
    current = ball_center.copy()
    vector = direction.copy()
    path = [current.copy()]

    for _ in range(max_bounces):
        candidates: list[tuple[float, str, int]] = []
        if vector[0] < -1e-6:
            candidates.append(((left - current[0]) / vector[0], "x", left))
        if vector[0] > 1e-6:
            candidates.append(((right - current[0]) / vector[0], "x", right))
        if vector[1] < -1e-6:
            candidates.append(((top - current[1]) / vector[1], "y", top))
        if vector[1] > 1e-6:
            candidates.append(((bottom - current[1]) / vector[1], "y", bottom))

        positive = [entry for entry in candidates if entry[0] > 1e-6]
        if not positive:
            break

        distance, axis, boundary = min(positive, key=lambda item: item[0])
        hit = current + vector * distance
        path.append(hit.copy())

        rail_pockets: list[tuple[int, float]] = []
        for pocket_id, center in pockets.items():
            if axis == "x" and abs(center[0] - boundary) < 1e-6:
                rail_pockets.append((pocket_id, float(np.linalg.norm(hit - center))))
            if axis == "y" and abs(center[1] - boundary) < 1e-6:
                rail_pockets.append((pocket_id, float(np.linalg.norm(hit - center))))

        if rail_pockets:
            best_id, best_distance = min(rail_pockets, key=lambda item: item[1])
            if best_distance <= pocket_tolerance:
                return best_id, path

        if axis == "x":
            vector[0] *= -1.0
        else:
            vector[1] *= -1.0
        current = hit

    return None, path


def _draw_solution(
    img: np.ndarray,
    ball_center: np.ndarray,
    tail: np.ndarray,
    tip: np.ndarray,
    bounds: tuple[int, int, int, int],
    path: list[np.ndarray],
    pocket_id: int | None,
) -> np.ndarray:
    vis = img.copy()
    left, right, top, bottom = bounds
    pockets = _pocket_map(left, right, top, bottom)

    cv2.rectangle(vis, (left, top), (right, bottom), (0, 255, 255), 3)
    for label, center in pockets.items():
        center_int = tuple(np.round(center).astype(int))
        cv2.circle(vis, center_int, 16, (0, 128, 255), 2)
        cv2.putText(
            vis,
            str(label),
            (center_int[0] + 8, center_int[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 128, 255),
            2,
            cv2.LINE_AA,
        )

    ball_int = tuple(np.round(ball_center).astype(int))
    tail_int = tuple(np.round(tail).astype(int))
    tip_int = tuple(np.round(tip).astype(int))
    cv2.circle(vis, ball_int, 18, (255, 0, 255), 3)
    cv2.circle(vis, tail_int, 8, (255, 255, 0), -1)
    cv2.circle(vis, tip_int, 8, (0, 0, 255), -1)
    cv2.line(vis, tail_int, tip_int, (255, 255, 0), 3)

    for start, end in zip(path, path[1:]):
        start_int = tuple(np.round(start).astype(int))
        end_int = tuple(np.round(end).astype(int))
        cv2.line(vis, start_int, end_int, (0, 0, 255), 4)
        cv2.circle(vis, end_int, 7, (0, 0, 255), -1)

    summary = f"predicted pocket: {pocket_id}" if pocket_id is not None else "predicted pocket: unknown"
    cv2.putText(
        vis,
        summary,
        (40, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 255),
        3,
        cv2.LINE_AA,
    )
    return vis


def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        ball_center, tail, tip, direction, _ = _detect_ball_and_arrow(hsv)
        bounds = _detect_inner_bounds(gray, ball_center)
        pocket_id, path = _trace_to_pocket(ball_center, direction, *bounds)
        solved = _draw_solution(img, ball_center, tail, tip, bounds, path, pocket_id)

        output_path = "artifacts/billiards_reflection_solver_output.png"
        save_image(solved, output_path)

        debug_info = (
            f"ball_center={tuple(np.round(ball_center, 1))}\n"
            f"arrow_tail={tuple(np.round(tail, 1))}\n"
            f"arrow_tip={tuple(np.round(tip, 1))}\n"
            f"inner_bounds={bounds}\n"
            f"path_points={[tuple(np.round(point, 1)) for point in path]}"
        )
        answer = str(pocket_id) if pocket_id is not None else ""
        status = "ok" if pocket_id is not None else "error"
        error = None if pocket_id is not None else "Failed to resolve a pocket from the traced path."

        return ToolResult(
            status=status,
            answer=answer,
            artifacts=[output_path],
            error=error,
            debug_info=debug_info,
        )
    except Exception as exc:
        return ToolResult(status="error", answer="", artifacts=[], error=str(exc))


def main():
    import sys

    if len(sys.argv) < 2:
        raise SystemExit(1)
    print(run(sys.argv[1]))


if __name__ == "__main__":
    main()
