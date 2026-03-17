"""Shared image processing utilities."""

from __future__ import annotations
import cv2
import numpy as np
import os
from pathlib import Path


def load_image(path: str | Path) -> np.ndarray:
    """Load image from path."""
    img = cv2.imread(str(path))
    if img is None:
        raise ValueError(f"Failed to load image: {path}")
    return img


def save_image(img: np.ndarray, path: str | Path) -> Path:
    """Save image to path."""
    requested_path = Path(path)
    resolved_path = _resolve_output_path(requested_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(resolved_path), img)
    return resolved_path


def _resolve_output_path(path: Path) -> Path:
    """Resolve tool output into a unique run-scoped artifact location when configured."""
    if path.is_absolute():
        return path

    work_dir = os.environ.get("VISION_AGENT_WORK_DIR", "").strip()
    if not work_dir:
        return path

    work_root = Path(work_dir)
    if path.parts and path.parts[0] == "artifacts":
        return work_root / path.name
    return work_root / path


def flip_horizontal(img: np.ndarray) -> np.ndarray:
    """Flip image horizontally (mirror)."""
    return cv2.flip(img, 1)


def rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image by angle (degrees)."""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img, matrix, (w, h))


def crop_image(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """Crop image to bounding box."""
    return img[y:y+h, x:x+w]


def resize_image(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize image to specified dimensions."""
    return cv2.resize(img, (width, height))


def to_grayscale(img: np.ndarray) -> np.ndarray:
    """Convert image to grayscale."""
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
