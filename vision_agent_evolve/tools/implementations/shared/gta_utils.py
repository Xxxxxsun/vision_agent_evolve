"""Shared helpers for GTA-compatible preset tools."""

from __future__ import annotations

import ast
import math
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib import parse, request

import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

from core.types import ToolResult
from core.vlm_client import ModelSettings
from tools.implementations.shared.image_utils import load_image, save_image
from tools.implementations.shared.vlm_helper import create_vlm_client

try:
    import sympy
except ImportError:  # pragma: no cover - optional at runtime
    sympy = None  # type: ignore[assignment]


def parse_tool_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, str]:
    """Parse CLI-style positional and key=value args into a normalized dict."""
    parsed: dict[str, str] = {}
    for key, value in kwargs.items():
        parsed[str(key)] = str(value)
    positional: list[str] = []
    for arg in args:
        text = str(arg)
        if "=" in text:
            key, value = text.split("=", 1)
            parsed[key.strip()] = value.strip()
        else:
            positional.append(text)
    if positional and "image" not in parsed:
        parsed["image"] = positional[0]
    for index, value in enumerate(positional[1:], start=0):
        parsed[f"arg{index}"] = value
    return parsed


def required_arg(params: dict[str, str], key: str) -> str:
    value = str(params.get(key, "")).strip()
    if not value:
        raise ValueError(f"Missing required argument: {key}")
    return value


def optional_arg(params: dict[str, str], key: str, default: str = "") -> str:
    return str(params.get(key, default)).strip()


def parse_bool(value: str, default: bool = False) -> bool:
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "yes", "y", "top1"}


def parse_int(value: str, default: int) -> int:
    text = str(value).strip()
    if not text:
        return default
    return int(float(text))


def parse_bbox(value: str) -> tuple[int, int, int, int]:
    numbers = [int(float(token)) for token in re.findall(r"-?\d+(?:\.\d+)?", str(value))]
    if len(numbers) < 4:
        raise ValueError(f"Invalid bbox: {value}")
    x1, y1, x2, y2 = numbers[:4]
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return x1, y1, x2, y2


def clamp_bbox(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1 + 1, min(width, x2))
    y2 = max(y1 + 1, min(height, y2))
    return x1, y1, x2, y2


def format_bbox(box: tuple[int, int, int, int]) -> str:
    return f"({box[0]}, {box[1]}, {box[2]}, {box[3]})"


def crop_bbox(image_path: str, bbox: str) -> Path:
    image = load_image(image_path)
    h, w = image.shape[:2]
    x1, y1, x2, y2 = clamp_bbox(parse_bbox(bbox), w, h)
    crop = image[y1:y2, x1:x2]
    output_path = save_image(crop, "artifacts/gta_region_crop.png")
    return output_path


def vlm_image_text(image_path: str, system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    client = create_vlm_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": client.image_message_parts(str(image_path), user_prompt)},
    ]
    response, _ = client.chat(messages, ModelSettings(temperature=0.0, max_tokens=max_tokens))
    return str(response).strip()


def safe_eval_expression(expression: str) -> str:
    env: dict[str, Any] = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "sum": sum,
        "pow": pow,
    }
    for name in dir(math):
        if name.startswith("_"):
            continue
        env[name] = getattr(math, name)
    value = eval(expression, {"__builtins__": {}}, env)
    return str(value)


def extract_python_code(command: str) -> str:
    text = str(command).strip()
    fenced = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text


def run_solver_code(command: str) -> str:
    if sympy is None:
        raise RuntimeError("sympy is required for Solver but is not installed")
    code = extract_python_code(command)
    namespace: dict[str, Any] = {
        "__builtins__": {"str": str, "len": len, "range": range, "min": min, "max": max, "sum": sum, "abs": abs},
        "sympy": sympy,
    }
    for name in dir(sympy):
        if not name.startswith("_"):
            namespace[name] = getattr(sympy, name)
    exec(code, namespace, namespace)
    solution = namespace.get("solution")
    if not callable(solution):
        raise ValueError("Solver code must define a callable solution()")
    return str(solution())


def run_plot_code(command: str) -> ToolResult:
    code = extract_python_code(command)
    namespace: dict[str, Any] = {
        "__builtins__": {"str": str, "len": len, "range": range, "min": min, "max": max, "sum": sum, "abs": abs},
        "plt": plt,
        "np": np,
        "numpy": np,
    }
    exec(code, namespace, namespace)
    solution = namespace.get("solution")
    if not callable(solution):
        raise ValueError("Plot code must define a callable solution()")
    figure = solution()
    if figure is None:
        figure = plt.gcf()
    output_path = Path("artifacts/gta_plot_output.png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path)
    plt.close(figure)
    return ToolResult(status="ok", answer="", artifacts=[str(output_path)])


def create_text_image(text: str, output_name: str, source_image: str | None = None) -> ToolResult:
    width = 1024
    height = 768
    if source_image:
        base = Image.open(source_image).convert("RGB")
    else:
        base = Image.new("RGB", (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(base)
    draw.rectangle((20, 20, base.width - 20, min(base.height - 20, 180)), fill=(255, 255, 255), outline=(200, 40, 40), width=3)
    draw.multiline_text((40, 40), text, fill=(20, 20, 20), spacing=8)
    output_path = Path("artifacts") / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(output_path)
    return ToolResult(status="ok", answer="", artifacts=[str(output_path)])


def draw_box(image_path: str, bbox: str, annotation: str = "") -> ToolResult:
    image = load_image(image_path)
    h, w = image.shape[:2]
    x1, y1, x2, y2 = clamp_bbox(parse_bbox(bbox), w, h)
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 255), 3)
    if annotation:
        cv2.putText(overlay, annotation, (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
    output_path = save_image(overlay, "artifacts/gta_draw_box_output.png")
    return ToolResult(status="ok", answer="", artifacts=[str(output_path)])


def add_text(image_path: str, text: str, position: str, color: str = "red") -> ToolResult:
    image = load_image(image_path)
    h, w = image.shape[:2]
    x, y = resolve_position(position, w, h)
    overlay = image.copy()
    palette = {
        "red": (0, 0, 255),
        "green": (0, 180, 0),
        "blue": (255, 0, 0),
        "yellow": (0, 255, 255),
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }
    bgr = palette.get(color.strip().lower(), (0, 0, 255))
    cv2.putText(overlay, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, bgr, 2, cv2.LINE_AA)
    output_path = save_image(overlay, "artifacts/gta_add_text_output.png")
    return ToolResult(status="ok", answer="", artifacts=[str(output_path)])


def resolve_position(position: str, width: int, height: int) -> tuple[int, int]:
    text = str(position).strip().lower()
    if re.search(r"-?\d", text):
        numbers = [int(float(token)) for token in re.findall(r"-?\d+(?:\.\d+)?", text)]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
    horizontal = {"l": int(width * 0.08), "m": int(width * 0.4), "r": int(width * 0.72)}
    vertical = {"t": int(height * 0.12), "m": int(height * 0.5), "b": int(height * 0.88)}
    key = text or "mm"
    if len(key) == 2:
        return horizontal.get(key[0], horizontal["m"]), vertical.get(key[1], vertical["m"])
    return horizontal["m"], vertical["m"]


def duckduckgo_search(query: str, k: int = 5) -> str:
    url = "https://html.duckduckgo.com/html/?" + parse.urlencode({"q": query})
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    results: list[str] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        title = _clean_html(match.group("title"))
        snippet = _clean_html(match.group("snippet"))
        href = unescape(match.group("href"))
        results.append(f"- {title}\n  {snippet}\n  {href}")
        if len(results) >= k:
            break
    if not results:
        raise RuntimeError("No search results returned")
    return "\n".join(results)


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()
