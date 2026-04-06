"""Built-in preset tools for skill-only evolution."""

from __future__ import annotations

import importlib.util
import json
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

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
        kernel = np.ones((3, 3), dtype=np.uint8)
        grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
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
        try:
            output_path = "artifacts/localized_text_zoom_output.png"
            source = Image.open(image_path).convert("RGB")
            enlarged = source.resize(
                (max(1, int(source.width * 1.5)), max(1, int(source.height * 1.5))),
                Image.Resampling.LANCZOS,
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            enlarged.save(output_path)
            return ToolResult(
                status="ok",
                answer="",
                artifacts=[output_path],
                debug_info=f"Fallback resize used after OpenCV path failed: {exc}",
            )
        except Exception as fallback_exc:
            return ToolResult(status="error", answer="", error=str(fallback_exc))


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


_VTOOL_TOOLS_MODULE = None


def _load_vtool_tools_module():
    global _VTOOL_TOOLS_MODULE
    if _VTOOL_TOOLS_MODULE is not None:
        return _VTOOL_TOOLS_MODULE

    module_path = Path("/root/VTool-R1/verl/tooluse/tools.py")
    if not module_path.exists():
        raise FileNotFoundError(f"VTool-R1 tools.py not found at {module_path}")

    spec = importlib.util.spec_from_file_location("vtool_r1_tools", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load VTool-R1 tools module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _VTOOL_TOOLS_MODULE = module
    return module


def _run_vtool_bbox_tool(tool_name: str, image_path: str, focus_targets_json: str, bbox_mapping_json: str) -> ToolResult:
    try:
        focus_targets = json.loads(focus_targets_json)
        bbox_mapping = json.loads(bbox_mapping_json)
        if not isinstance(focus_targets, list):
            raise ValueError("The focus targets argument must decode to a JSON list.")
        if not isinstance(bbox_mapping, dict):
            raise ValueError("The bbox mapping argument must decode to a JSON object.")

        module = _load_vtool_tools_module()
        tool_fn = getattr(module, tool_name)
        image = Image.open(image_path).convert("RGBA")
        output_image = tool_fn(image, focus_targets, bbox_mapping)
        output_path = f"artifacts/{tool_name}_output.png"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        output_image.save(output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))


def focus_on_columns_with_mask(image_path: str, columns_to_focus_on_json: str, all_columns_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_columns_with_mask", image_path, columns_to_focus_on_json, all_columns_bounding_boxes_json)


def focus_on_rows_with_mask(image_path: str, rows_to_focus_on_json: str, all_rows_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_rows_with_mask", image_path, rows_to_focus_on_json, all_rows_bounding_boxes_json)


def focus_on_columns_with_draw(image_path: str, columns_to_focus_on_json: str, all_columns_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_columns_with_draw", image_path, columns_to_focus_on_json, all_columns_bounding_boxes_json)


def focus_on_rows_with_draw(image_path: str, rows_to_focus_on_json: str, all_rows_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_rows_with_draw", image_path, rows_to_focus_on_json, all_rows_bounding_boxes_json)


def focus_on_columns_with_highlight(image_path: str, columns_to_focus_on_json: str, all_columns_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_columns_with_highlight", image_path, columns_to_focus_on_json, all_columns_bounding_boxes_json)


def focus_on_rows_with_highlight(image_path: str, rows_to_focus_on_json: str, all_rows_bounding_boxes_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_rows_with_highlight", image_path, rows_to_focus_on_json, all_rows_bounding_boxes_json)


def focus_on_x_values_with_mask(image_path: str, x_values_to_focus_on_json: str, x_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_x_values_with_mask", image_path, x_values_to_focus_on_json, x_values_bbox_json)


def focus_on_y_values_with_mask(image_path: str, y_values_to_focus_on_json: str, y_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_y_values_with_mask", image_path, y_values_to_focus_on_json, y_values_bbox_json)


def focus_on_x_values_with_draw(image_path: str, x_values_to_focus_on_json: str, x_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_x_values_with_draw", image_path, x_values_to_focus_on_json, x_values_bbox_json)


def focus_on_y_values_with_draw(image_path: str, y_values_to_focus_on_json: str, y_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_y_values_with_draw", image_path, y_values_to_focus_on_json, y_values_bbox_json)


def focus_on_x_values_with_highlight(image_path: str, x_values_to_focus_on_json: str, x_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_x_values_with_highlight", image_path, x_values_to_focus_on_json, x_values_bbox_json)


def focus_on_y_values_with_highlight(image_path: str, y_values_to_focus_on_json: str, y_values_bbox_json: str) -> ToolResult:
    return _run_vtool_bbox_tool("focus_on_y_values_with_highlight", image_path, y_values_to_focus_on_json, y_values_bbox_json)


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
    "focus_on_columns_with_mask": BuiltinToolSpec(
        name="focus_on_columns_with_mask",
        description="VTool-R1 table tool that masks out irrelevant columns.",
        applicability="Use for TableVQA when the answer depends on a subset of columns and column bbox metadata is available.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_columns_with_mask,
        usage_example='python -m tools focus_on_columns_with_mask <image_path> \'["Year","Team"]\' \'{"Year":{"x1":0,"y1":0,"x2":100,"y2":200}}\'',
    ),
    "focus_on_rows_with_mask": BuiltinToolSpec(
        name="focus_on_rows_with_mask",
        description="VTool-R1 table tool that masks out irrelevant rows.",
        applicability="Use for TableVQA when the answer depends on a subset of rows and row bbox metadata is available.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_rows_with_mask,
        usage_example='python -m tools focus_on_rows_with_mask <image_path> \'["2004","2005"]\' \'{"Header":{"x1":0,"y1":0,"x2":100,"y2":20}}\'',
    ),
    "focus_on_columns_with_draw": BuiltinToolSpec(
        name="focus_on_columns_with_draw",
        description="VTool-R1 table tool that draws boxes around selected columns.",
        applicability="Use for TableVQA when highlighting the relevant columns is more useful than masking.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_columns_with_draw,
        usage_example='python -m tools focus_on_columns_with_draw <image_path> \'["Year","Team"]\' \'{"Year":{"x1":0,"y1":0,"x2":100,"y2":200}}\'',
    ),
    "focus_on_rows_with_draw": BuiltinToolSpec(
        name="focus_on_rows_with_draw",
        description="VTool-R1 table tool that draws boxes around selected rows.",
        applicability="Use for TableVQA when highlighting the relevant rows is more useful than masking.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_rows_with_draw,
        usage_example='python -m tools focus_on_rows_with_draw <image_path> \'["2004","2005"]\' \'{"Header":{"x1":0,"y1":0,"x2":100,"y2":20}}\'',
    ),
    "focus_on_columns_with_highlight": BuiltinToolSpec(
        name="focus_on_columns_with_highlight",
        description="VTool-R1 table tool that softly highlights selected columns.",
        applicability="Use for TableVQA when preserving context while emphasizing columns is useful.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_columns_with_highlight,
        usage_example='python -m tools focus_on_columns_with_highlight <image_path> \'["Year","Team"]\' \'{"Year":{"x1":0,"y1":0,"x2":100,"y2":200}}\'',
    ),
    "focus_on_rows_with_highlight": BuiltinToolSpec(
        name="focus_on_rows_with_highlight",
        description="VTool-R1 table tool that softly highlights selected rows.",
        applicability="Use for TableVQA when preserving context while emphasizing rows is useful.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_rows_with_highlight,
        usage_example='python -m tools focus_on_rows_with_highlight <image_path> \'["2004","2005"]\' \'{"Header":{"x1":0,"y1":0,"x2":100,"y2":20}}\'',
    ),
    "focus_on_x_values_with_mask": BuiltinToolSpec(
        name="focus_on_x_values_with_mask",
        description="VTool-R1 chart tool that masks out irrelevant x-axis values.",
        applicability="Use for ChartQA when the answer depends on specific x-axis values and bbox metadata is available.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_x_values_with_mask,
        usage_example='python -m tools focus_on_x_values_with_mask <image_path> \'["2018","2019"]\' \'{"2018":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
    ),
    "focus_on_y_values_with_mask": BuiltinToolSpec(
        name="focus_on_y_values_with_mask",
        description="VTool-R1 chart tool that masks out irrelevant y-axis values.",
        applicability="Use for ChartQA when the answer depends on specific y-axis values and bbox metadata is available.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_y_values_with_mask,
        usage_example='python -m tools focus_on_y_values_with_mask <image_path> \'["Asia","Europe"]\' \'{"Asia":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
    ),
    "focus_on_x_values_with_draw": BuiltinToolSpec(
        name="focus_on_x_values_with_draw",
        description="VTool-R1 chart tool that draws boxes around selected x-axis values.",
        applicability="Use for ChartQA when highlighting target x-axis values is more useful than masking.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_x_values_with_draw,
        usage_example='python -m tools focus_on_x_values_with_draw <image_path> \'["2018","2019"]\' \'{"2018":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
    ),
    "focus_on_y_values_with_draw": BuiltinToolSpec(
        name="focus_on_y_values_with_draw",
        description="VTool-R1 chart tool that draws boxes around selected y-axis values.",
        applicability="Use for ChartQA when highlighting target y-axis values is more useful than masking.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_y_values_with_draw,
        usage_example='python -m tools focus_on_y_values_with_draw <image_path> \'["Asia","Europe"]\' \'{"Asia":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
    ),
    "focus_on_x_values_with_highlight": BuiltinToolSpec(
        name="focus_on_x_values_with_highlight",
        description="VTool-R1 chart tool that softly highlights selected x-axis values.",
        applicability="Use for ChartQA when preserving context while emphasizing x-axis values is useful.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_x_values_with_highlight,
        usage_example='python -m tools focus_on_x_values_with_highlight <image_path> \'["2018","2019"]\' \'{"2018":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
    ),
    "focus_on_y_values_with_highlight": BuiltinToolSpec(
        name="focus_on_y_values_with_highlight",
        description="VTool-R1 chart tool that softly highlights selected y-axis values.",
        applicability="Use for ChartQA when preserving context while emphasizing y-axis values is useful.",
        benchmark_notes="Wrapper around the official VTool-R1 tool.",
        chain_safe=True,
        runner=focus_on_y_values_with_highlight,
        usage_example='python -m tools focus_on_y_values_with_highlight <image_path> \'["Asia","Europe"]\' \'{"Asia":{"x1":0,"y1":0,"x2":10,"y2":10}}\'',
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
