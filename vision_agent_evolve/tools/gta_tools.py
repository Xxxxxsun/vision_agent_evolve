"""GTA-compatible preset tool implementations."""

from __future__ import annotations

from core.types import ToolResult
from tools.implementations.shared.gta_utils import (
    add_text,
    create_text_image,
    crop_bbox,
    draw_box,
    duckduckgo_search,
    optional_arg,
    parse_bool,
    parse_int,
    parse_tool_args,
    required_arg,
    run_plot_code,
    run_solver_code,
    safe_eval_expression,
    vlm_image_text,
)
from tools.preset_types import BuiltinToolSpec


def gta_ocr(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    text = vlm_image_text(
        image,
        "You are an OCR system.",
        "Read all visible text in the image. Return one line per detected text span using the format "
        "(x1, y1, x2, y2): recognized text. If coordinates are uncertain, still provide your best approximate boxes.",
        max_tokens=800,
    )
    return ToolResult(status="ok", answer=text)


def gta_image_description(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    text = vlm_image_text(
        image,
        "You are a concise image description system.",
        "Describe the image briefly and factually in 2-4 sentences. Focus on objects, scene, and any text that matters.",
        max_tokens=250,
    )
    return ToolResult(status="ok", answer=text)


def gta_count_given_object(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    target = required_arg(params, "text")
    text = vlm_image_text(
        image,
        "You count objects in images.",
        f"Count how many instances match this description: {target}. Reply with only the integer count.",
        max_tokens=40,
    )
    return ToolResult(status="ok", answer=text)


def gta_text_to_bbox(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    target = required_arg(params, "text")
    top1 = parse_bool(optional_arg(params, "top1", "true"), default=True)
    mode = "Return only the single best match." if top1 else "Return all plausible matches."
    text = vlm_image_text(
        image,
        "You localize described objects in images.",
        f"Find the region matching this description: {target}. {mode} "
        "Return each result on its own line using the format (x1, y1, x2, y2), score=0.xx",
        max_tokens=300,
    )
    return ToolResult(status="ok", answer=text)


def gta_region_attribute_description(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    bbox = required_arg(params, "bbox")
    attribute = required_arg(params, "attribute")
    crop = crop_bbox(image, bbox)
    text = vlm_image_text(
        str(crop),
        "You describe a specific visual attribute inside a cropped image region.",
        f"Describe this attribute only: {attribute}. Be concise and concrete.",
        max_tokens=200,
    )
    return ToolResult(status="ok", answer=text, artifacts=[str(crop)])


def gta_math_ocr(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    text = vlm_image_text(
        image,
        "You transcribe mathematical expressions.",
        "Read the mathematical expression in the image and return only the LaTeX-style expression.",
        max_tokens=200,
    )
    return ToolResult(status="ok", answer=text)


def gta_calculator(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    expression = required_arg(params, "expression")
    return ToolResult(status="ok", answer=safe_eval_expression(expression))


def gta_solver(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    command = required_arg(params, "command")
    return ToolResult(status="ok", answer=run_solver_code(command))


def gta_plot(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    command = required_arg(params, "command")
    return run_plot_code(command)


def gta_draw_box(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    bbox = required_arg(params, "bbox")
    annotation = optional_arg(params, "annotation")
    return draw_box(image, bbox, annotation=annotation)


def gta_add_text(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    text = required_arg(params, "text")
    position = required_arg(params, "position")
    color = optional_arg(params, "color", "red")
    return add_text(image, text, position, color=color)


def gta_google_search(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    query = required_arg(params, "query")
    k = parse_int(optional_arg(params, "k", "5"), default=5)
    return ToolResult(status="ok", answer=duckduckgo_search(query, k=max(1, min(k, 10))))


def gta_text_to_image(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    keywords = required_arg(params, "keywords")
    return create_text_image(f"Generated from keywords:\n{keywords}", "gta_text_to_image_output.png")


def gta_image_stylization(*args, **kwargs) -> ToolResult:
    params = parse_tool_args(args, kwargs)
    image = required_arg(params, "image")
    instruction = required_arg(params, "instruction")
    return create_text_image(f"Stylization instruction:\n{instruction}", "gta_image_stylization_output.png", source_image=image)


GTA_BUILTIN_TOOLS: dict[str, BuiltinToolSpec] = {
    "OCR": BuiltinToolSpec(
        name="OCR",
        description="Recognize visible text in an image and return approximate bbox-tagged lines.",
        applicability="Use when the answer depends on reading text, numbers, labels, or signs from the image.",
        benchmark_notes="GTA-compatible OCR approximation.",
        chain_safe=True,
        runner=gta_ocr,
        usage_example='python -m tools OCR image=<image_path>',
    ),
    "ImageDescription": BuiltinToolSpec(
        name="ImageDescription",
        description="Describe the image briefly and factually.",
        applicability="Use when you need to identify the scene, objects, or high-level context before further reasoning.",
        benchmark_notes="GTA-compatible image captioning approximation.",
        chain_safe=True,
        runner=gta_image_description,
        usage_example='python -m tools ImageDescription image=<image_path>',
    ),
    "CountGivenObject": BuiltinToolSpec(
        name="CountGivenObject",
        description="Count how many objects matching a text description appear in an image.",
        applicability="Use when the task requires counting a described object in the image.",
        benchmark_notes="GTA-compatible counting approximation.",
        chain_safe=True,
        runner=gta_count_given_object,
        usage_example='python -m tools CountGivenObject image=<image_path> text="object description"',
    ),
    "TextToBbox": BuiltinToolSpec(
        name="TextToBbox",
        description="Locate a described object in the image and return approximate bounding boxes.",
        applicability="Use when you need the location of an object before cropping, boxing, or attribute inspection.",
        benchmark_notes="GTA-compatible localization approximation.",
        chain_safe=True,
        runner=gta_text_to_bbox,
        usage_example='python -m tools TextToBbox image=<image_path> text="object description" top1=true',
    ),
    "RegionAttributeDescription": BuiltinToolSpec(
        name="RegionAttributeDescription",
        description="Describe a requested attribute inside a specified image region.",
        applicability="Use after you already know the target bbox and need a local attribute answer.",
        benchmark_notes="GTA-compatible region-attribute approximation.",
        chain_safe=True,
        runner=gta_region_attribute_description,
        usage_example='python -m tools RegionAttributeDescription image=<image_path> bbox="(x1, y1, x2, y2)" attribute="attribute to describe"',
    ),
    "MathOCR": BuiltinToolSpec(
        name="MathOCR",
        description="Transcribe mathematical expressions from an image into LaTeX-like text.",
        applicability="Use when the image contains equations, formulas, or symbolic math.",
        benchmark_notes="GTA-compatible math OCR approximation.",
        chain_safe=True,
        runner=gta_math_ocr,
        usage_example='python -m tools MathOCR image=<image_path>',
    ),
    "Calculator": BuiltinToolSpec(
        name="Calculator",
        description="Evaluate a single numeric Python expression with math functions allowed.",
        applicability="Use when arithmetic or simple numeric computation is needed after extracting values.",
        benchmark_notes="GTA-compatible calculator.",
        chain_safe=True,
        runner=gta_calculator,
        usage_example='python -m tools Calculator expression="round(75 / 59 * 100)"',
    ),
    "Solver": BuiltinToolSpec(
        name="Solver",
        description="Execute restricted SymPy-based Python code to solve math equations.",
        applicability="Use for symbolic equation solving after you have transcribed the problem.",
        benchmark_notes="GTA-compatible symbolic solver.",
        chain_safe=False,
        runner=gta_solver,
        usage_example='python -m tools Solver command="<python code with solution()>"',
    ),
    "Plot": BuiltinToolSpec(
        name="Plot",
        description="Execute restricted plotting code and return the generated figure as an artifact.",
        applicability="Use when visualizing equations or data will help solve the task.",
        benchmark_notes="GTA-compatible plotting tool.",
        chain_safe=False,
        runner=gta_plot,
        usage_example='python -m tools Plot command="<python code with solution()>"',
    ),
    "DrawBox": BuiltinToolSpec(
        name="DrawBox",
        description="Draw a bounding box and optional annotation onto the image.",
        applicability="Use when you need to mark a region for later inspection or final output.",
        benchmark_notes="GTA-compatible box drawing tool.",
        chain_safe=True,
        runner=gta_draw_box,
        usage_example='python -m tools DrawBox image=<image_path> bbox="(x1, y1, x2, y2)" annotation="optional text"',
    ),
    "AddText": BuiltinToolSpec(
        name="AddText",
        description="Overlay text onto the image at a coordinate or anchor position.",
        applicability="Use when a final edited image needs textual labeling.",
        benchmark_notes="GTA-compatible text overlay tool.",
        chain_safe=True,
        runner=gta_add_text,
        usage_example='python -m tools AddText image=<image_path> text="label" position="mt" color=red',
    ),
    "GoogleSearch": BuiltinToolSpec(
        name="GoogleSearch",
        description="Fetch lightweight web search results for a query and return top snippets.",
        applicability="Use when the answer requires external factual knowledge not contained in the image.",
        benchmark_notes="GTA-compatible web search approximation.",
        chain_safe=True,
        runner=gta_google_search,
        usage_example='python -m tools GoogleSearch query="who won 2021 olympic table tennis mixed doubles" k=4',
    ),
    "TextToImage": BuiltinToolSpec(
        name="TextToImage",
        description="Generate a simple image artifact from text keywords.",
        applicability="Use for GTA editing/generation tasks that require creating an output image from text.",
        benchmark_notes="GTA-compatible practical placeholder generator.",
        chain_safe=True,
        runner=gta_text_to_image,
        usage_example='python -m tools TextToImage keywords="fireworks, night sky, city"',
    ),
    "ImageStylization": BuiltinToolSpec(
        name="ImageStylization",
        description="Create a stylized output artifact from an input image and instruction.",
        applicability="Use for GTA editing tasks that require modifying an existing image.",
        benchmark_notes="GTA-compatible practical placeholder stylizer.",
        chain_safe=True,
        runner=gta_image_stylization,
        usage_example='python -m tools ImageStylization image=<image_path> instruction="turn him into cyborg"',
    ),
}
