"""Built-in preset tools for skill-only evolution."""

from __future__ import annotations

import cv2
import numpy as np

from core.types import ToolResult
from tools.gta_tools import GTA_BUILTIN_TOOLS
from tools.preset_types import BuiltinToolSpec
from tools.implementations.shared.image_utils import load_image, save_image


def _edge_boxes(image: np.ndarray, min_area_ratio: float = 0.005, max_area_ratio: float = 0.7) -> list[tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    image_area = float(max(h * w, 1))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * min_area_ratio or area > image_area * max_area_ratio:
            continue
        boxes.append((x, y, bw, bh))
    boxes.sort(key=lambda item: item[2] * item[3], reverse=True)
    return boxes


def _write_overlay(image: np.ndarray, boxes: list[tuple[int, int, int, int]], color: tuple[int, int, int], output_name: str) -> ToolResult:
    overlay = image.copy()
    for x, y, w, h in boxes[:10]:
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
    output_path = f"artifacts/{output_name}"
    save_image(overlay, output_path)
    return ToolResult(status="ok", answer="", artifacts=[output_path])


def localized_color_focus(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        _, sat_mask = cv2.threshold(sat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, val_mask = cv2.threshold(val, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        mask = cv2.bitwise_and(sat_mask, val_mask)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(contour) for contour in contours]
        return _write_overlay(image, boxes, (0, 200, 255), "localized_color_focus_output.png")
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def localized_text_zoom(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        _, mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        boxes = _edge_boxes(cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR), min_area_ratio=0.002, max_area_ratio=0.2)
        overlay = image.copy()
        for x, y, w, h in boxes[:6]:
            pad_w = max(2, int(w * 0.1))
            pad_h = max(2, int(h * 0.1))
            cv2.rectangle(overlay, (max(0, x - pad_w), max(0, y - pad_h)), (min(image.shape[1], x + w + pad_w), min(image.shape[0], y + h + pad_h)), (255, 255, 0), 2)
        output_path = "artifacts/localized_text_zoom_output.png"
        enlarged = cv2.resize(overlay, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        save_image(enlarged, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def localized_region_zoom(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        boxes = _edge_boxes(image, min_area_ratio=0.01, max_area_ratio=0.4)
        overlay = image.copy()
        for x, y, w, h in boxes[:5]:
            cx, cy = x + w // 2, y + h // 2
            cv2.circle(overlay, (cx, cy), max(6, min(w, h) // 6), (0, 255, 255), 2)
        output_path = "artifacts/localized_region_zoom_output.png"
        enlarged = cv2.resize(overlay, None, fx=1.35, fy=1.35, interpolation=cv2.INTER_CUBIC)
        save_image(enlarged, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def relative_position_marker(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        boxes = _edge_boxes(image, min_area_ratio=0.01, max_area_ratio=0.5)
        overlay = image.copy()
        h, w = image.shape[:2]
        cv2.line(overlay, (w // 2, 0), (w // 2, h), (180, 180, 180), 1)
        for index, (x, y, bw, bh) in enumerate(boxes[:8], start=1):
            cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.putText(overlay, str(index), (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        output_path = "artifacts/relative_position_marker_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def chart_value_overlay(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = image.shape[:2]
        image_area = float(max(h * w, 1))
        overlay = image.copy()
        best_box = (0, 0, w, h)
        best_area = 0.0
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            area = float(bw * bh)
            if area < image_area * 0.08:
                continue
            if area > best_area:
                best_box = (x, y, bw, bh)
                best_area = area
        x, y, bw, bh = best_box
        cv2.rectangle(overlay, (x, y), (x + bw, y + bh), (0, 255, 255), 2)
        roi = gray[y:y + bh, x:x + bw]
        if roi.size:
            grad_x = cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)
            grad = cv2.convertScaleAbs(grad_x)
            _, mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            inner_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in inner_contours[:16]:
                ix, iy, iw, ih = cv2.boundingRect(contour)
                if iw * ih < roi.size * 0.002:
                    continue
                cv2.rectangle(overlay, (x + ix, y + iy), (x + ix + iw, y + iy + ih), (255, 120, 0), 1)
        output_path = "artifacts/chart_value_overlay_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def count_support_view(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        boxes = _edge_boxes(image, min_area_ratio=0.004, max_area_ratio=0.15)
        overlay = image.copy()
        for index, (x, y, w, h) in enumerate(boxes[:20], start=1):
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (255, 0, 255), 1)
            cv2.putText(overlay, str(index), (x, y + max(12, h // 2)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 0, 255), 1, cv2.LINE_AA)
        output_path = "artifacts/count_support_view_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


BUILTIN_TOOLS: dict[str, BuiltinToolSpec] = {
    "localized_color_focus": BuiltinToolSpec(
        name="localized_color_focus",
        description="Highlight candidate local regions that likely contain discriminative color evidence.",
        applicability="Use when the question asks about a local object's color or a short visual attribute.",
        benchmark_notes="Best for hrbench, vstar, and some localized attribute cases.",
        chain_safe=True,
        runner=localized_color_focus,
        usage_example="python -m tools localized_color_focus <image_path>",
    ),
    "localized_text_zoom": BuiltinToolSpec(
        name="localized_text_zoom",
        description="Magnify and highlight candidate text-like regions for manual reading.",
        applicability="Use when the target evidence is a small word, number, label, or year.",
        benchmark_notes="Best for hrbench labels and chart/text-heavy questions.",
        chain_safe=True,
        runner=localized_text_zoom,
        usage_example="python -m tools localized_text_zoom <image_path>",
    ),
    "localized_region_zoom": BuiltinToolSpec(
        name="localized_region_zoom",
        description="Magnify generic local candidate regions without assuming text or color only.",
        applicability="Use when the relevant evidence is small, localized, and not clearly text-only.",
        benchmark_notes="Useful across vstar, hrbench, and some mathvista/chartqa cases.",
        chain_safe=True,
        runner=localized_region_zoom,
        usage_example="python -m tools localized_region_zoom <image_path>",
    ),
    "relative_position_marker": BuiltinToolSpec(
        name="relative_position_marker",
        description="Annotate salient regions to support left/right or top/bottom reasoning.",
        applicability="Use when the task depends on relative spatial position between salient entities.",
        benchmark_notes="Best for vstar and mathvista visual position questions.",
        chain_safe=True,
        runner=relative_position_marker,
        usage_example="python -m tools relative_position_marker <image_path>",
    ),
    "chart_value_overlay": BuiltinToolSpec(
        name="chart_value_overlay",
        description="Overlay likely chart and bar/label regions without computing the final numeric answer.",
        applicability="Use when the question requires reading chart values or labels from a bar-like chart.",
        benchmark_notes="Best for chartqa.",
        chain_safe=True,
        runner=chart_value_overlay,
        usage_example="python -m tools chart_value_overlay <image_path>",
    ),
    "count_support_view": BuiltinToolSpec(
        name="count_support_view",
        description="Mark candidate countable regions to support counting or subtraction questions.",
        applicability="Use when the task requires counting visible objects or comparing counts.",
        benchmark_notes="Best for mathvista counting-style cases.",
        chain_safe=True,
        runner=count_support_view,
        usage_example="python -m tools count_support_view <image_path>",
    ),
}
BUILTIN_TOOLS.update(GTA_BUILTIN_TOOLS)


def list_builtin_tools() -> list[BuiltinToolSpec]:
    return [BUILTIN_TOOLS[name] for name in sorted(BUILTIN_TOOLS)]


def get_builtin_tool(name: str) -> BuiltinToolSpec | None:
    return BUILTIN_TOOLS.get(name)


def execute_builtin_tool(name: str, *args: str) -> str:
    spec = BUILTIN_TOOLS.get(name)
    if spec is None:
        raise KeyError(name)
    return str(spec.runner(*args))
