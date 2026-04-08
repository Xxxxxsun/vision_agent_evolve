"""Official-style tool implementations for VisualToolBench."""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import traceback
import types
from html import unescape
import shutil
from pathlib import Path
from typing import Any
from urllib import parse, request

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.types import ToolResult


def get_visualtoolbench_tool_descriptions() -> str:
    """Return the prompt-facing tool catalog."""
    return (
        "- python_image_processing(code): Generate Python code that reads one input image, performs image editing "
        "with PIL/NumPy/OpenCV, and saves PNG outputs as transformed_image_i.png. OCR-only packages such as "
        "pytesseract/easyocr are not preinstalled; prefer PIL/OpenCV transforms.\n"
        "- python_interpreter(code): Run general-purpose Python code and capture stdout/stderr.\n"
        "- web_search(query, num_results=5): Search the web and return concise result snippets.\n"
        "- browser_get_page_text(url): Fetch one webpage and return extracted text content.\n"
        "- historical_weather(location, date): Return historical weather for a given location and date.\n"
        "- calculator(expression): Evaluate a math expression."
    )


def execute_visualtoolbench_tool(
    name: str,
    arguments: dict[str, Any],
    workspace_dir: Path,
    image_paths: list[str],
) -> ToolResult:
    """Execute one VisualToolBench tool call."""
    normalized = name.strip()
    registry = {
        "python_image_processing": python_image_processing,
        "python_interpreter": python_interpreter,
        "web_search": web_search,
        "browser_get_page_text": browser_get_page_text,
        "historical_weather": historical_weather,
        "calculator": calculator,
    }
    if normalized not in registry:
        return ToolResult(status="error", answer="", error=f"Unknown VisualToolBench tool: {name}")
    try:
        return registry[normalized](workspace_dir=workspace_dir, image_paths=image_paths, **arguments)
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc), debug_info=traceback.format_exc(limit=5))


def python_image_processing(
    code: str,
    workspace_dir: Path,
    image_paths: list[str],
    **_: Any,
) -> ToolResult:
    """Run controlled image-processing code and collect written PNG artifacts."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    output_dir = workspace_dir / "processed_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    _materialize_input_images(workspace_dir, image_paths)

    before = _transformed_image_names(workspace_dir, output_dir)
    code = _rewrite_workspace_paths(str(code), workspace_dir)
    globals_dict = _sandbox_globals(workspace_dir, image_paths, output_dir)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with _pushd(workspace_dir), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(code, globals_dict, globals_dict)

    artifacts = _collect_transformed_artifacts(workspace_dir, output_dir, before)
    if not artifacts:
        artifacts = [str(path) for path in _all_transformed_artifacts(workspace_dir, output_dir)]

    answer = stdout.getvalue().strip()
    debug = stderr.getvalue().strip()
    return ToolResult(status="ok", answer=answer, artifacts=artifacts, debug_info=debug)


def python_interpreter(
    code: str,
    workspace_dir: Path,
    image_paths: list[str],
    **_: Any,
) -> ToolResult:
    """Run general-purpose Python code in a constrained namespace."""
    workspace_dir.mkdir(parents=True, exist_ok=True)
    _materialize_input_images(workspace_dir, image_paths)
    code = _rewrite_workspace_paths(str(code), workspace_dir)
    globals_dict = _sandbox_globals(workspace_dir, image_paths, workspace_dir / "processed_images")
    stdout = io.StringIO()
    stderr = io.StringIO()
    with _pushd(workspace_dir), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exec(code, globals_dict, globals_dict)
    return ToolResult(
        status="ok",
        answer=stdout.getvalue().strip(),
        debug_info=stderr.getvalue().strip(),
    )


def web_search(
    query: str,
    num_results: int = 5,
    **_: Any,
) -> ToolResult:
    """Search the web with DuckDuckGo HTML results."""
    k = max(1, min(int(num_results or 5), 10))
    url = "https://html.duckduckgo.com/html/?" + parse.urlencode({"q": query})
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.DOTALL,
    )
    results: list[str] = []
    for match in pattern.finditer(html):
        title = _clean_html(match.group("title"))
        snippet = _clean_html(match.group("snippet"))
        href = unescape(match.group("href"))
        results.append(f"- {title}\n  {snippet}\n  {href}")
        if len(results) >= k:
            break
    if not results:
        raise RuntimeError("No search results returned")
    return ToolResult(status="ok", answer="\n".join(results))


def browser_get_page_text(url: str, **_: Any) -> ToolResult:
    """Fetch a webpage and strip most tags."""
    req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", unescape(text)).strip()
    return ToolResult(status="ok", answer=text[:12000])


def historical_weather(location: str, date: str, **_: Any) -> ToolResult:
    """Fetch historical weather using Open-Meteo archive + geocoding APIs."""
    geo_url = "https://geocoding-api.open-meteo.com/v1/search?" + parse.urlencode(
        {"name": location, "count": 1}
    )
    geo_req = request.Request(geo_url, headers={"User-Agent": "Mozilla/5.0"})
    with request.urlopen(geo_req, timeout=20) as resp:
        geo_payload = json.loads(resp.read().decode("utf-8"))
    results = geo_payload.get("results") or []
    if not results:
        raise RuntimeError(f"Could not geocode location: {location}")
    top = results[0]
    weather_url = "https://archive-api.open-meteo.com/v1/archive?" + parse.urlencode(
        {
            "latitude": top["latitude"],
            "longitude": top["longitude"],
            "start_date": date,
            "end_date": date,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "UTC",
        }
    )
    weather_req = request.Request(weather_url, headers={"User-Agent": "Mozilla/5.0"})
    with request.urlopen(weather_req, timeout=20) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    daily = payload.get("daily") or {}
    summary = {
        "resolved_location": {
            "name": top.get("name"),
            "country": top.get("country"),
            "latitude": top.get("latitude"),
            "longitude": top.get("longitude"),
        },
        "date": date,
        "temperature_2m_max": _daily_value(daily, "temperature_2m_max"),
        "temperature_2m_min": _daily_value(daily, "temperature_2m_min"),
        "precipitation_sum": _daily_value(daily, "precipitation_sum"),
    }
    return ToolResult(status="ok", answer=json.dumps(summary, ensure_ascii=False))


def calculator(expression: str, **_: Any) -> ToolResult:
    """Evaluate a math expression."""
    env: dict[str, Any] = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "sum": sum,
        "pow": pow,
    }
    for name in dir(math):
        if not name.startswith("_"):
            env[name] = getattr(math, name)
    value = eval(expression, {"__builtins__": {}}, env)
    return ToolResult(status="ok", answer=str(value))


def _sandbox_globals(workspace_dir: Path, image_paths: list[str], output_dir: Path) -> dict[str, Any]:
    image_list = [str(Path(path)) for path in image_paths]
    builtins_dict = {
        "__import__": _safe_import,
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "open": open,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
        "Exception": Exception,
        "FileNotFoundError": FileNotFoundError,
        "RuntimeError": RuntimeError,
        "TypeError": TypeError,
        "ValueError": ValueError,
    }
    return {
        "__builtins__": builtins_dict,
        "Path": Path,
        "os": os,
        "json": json,
        "np": np,
        "numpy": np,
        "cv2": cv2,
        "Image": Image,
        "ImageOps": ImageOps,
        "ImageEnhance": ImageEnhance,
        "ImageFilter": ImageFilter,
        "workspace_dir": str(workspace_dir),
        "image_list": image_list,
        "processed_image_save_path": str(output_dir),
    }


def _rewrite_workspace_paths(code: str, workspace_dir: Path) -> str:
    """Map common notebook scratch paths to the tool workspace."""
    workspace = str(workspace_dir)
    return code.replace("/mnt/data", workspace).replace("/content", workspace)


def _materialize_input_images(workspace_dir: Path, image_paths: list[str]) -> None:
    """Expose images in the workspace using the paper-style image_N aliases."""
    for index, raw_path in enumerate(image_paths, start=1):
        source = Path(raw_path)
        if not source.exists():
            continue
        suffix = source.suffix.lower() or ".png"
        alias_path = workspace_dir / f"image_{index}{suffix}"
        if alias_path.exists():
            pass
        else:
            shutil.copy2(source, alias_path)
        basename_path = workspace_dir / source.name
        if not basename_path.exists():
            shutil.copy2(source, basename_path)
        generic_path = workspace_dir / f"input_image{suffix}"
        if index == 1 and not generic_path.exists():
            shutil.copy2(source, generic_path)


def _transformed_image_names(workspace_dir: Path, output_dir: Path) -> set[str]:
    return {path.name for path in _all_transformed_artifacts(workspace_dir, output_dir)}


def _all_transformed_artifacts(workspace_dir: Path, output_dir: Path) -> list[Path]:
    seen: dict[str, Path] = {}
    for base in (workspace_dir, output_dir):
        for path in sorted(base.glob("transformed_image_*.png")):
            seen.setdefault(path.name, path.resolve())
    return list(seen.values())


def _collect_transformed_artifacts(workspace_dir: Path, output_dir: Path, before: set[str]) -> list[str]:
    artifacts = []
    for path in _all_transformed_artifacts(workspace_dir, output_dir):
        if path.name not in before:
            artifacts.append(str(path))
    return artifacts


def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    if name == "pytesseract":
        return _build_pytesseract_shim()
    if name == "easyocr":
        return _build_easyocr_shim()
    return __import__(name, globals, locals, fromlist, level)


def _build_pytesseract_shim():
    module = types.ModuleType("pytesseract")

    def image_to_string(image, *args, **kwargs):
        path = _ensure_image_path(image)
        prompt = (
            "Read all visible text from this image. "
            "Return plain text only, preserving numbers and line breaks when possible."
        )
        return _vlm_ocr_text(path, prompt)

    module.image_to_string = image_to_string
    return module


def _build_easyocr_shim():
    module = types.ModuleType("easyocr")

    class Reader:
        def __init__(self, languages, *args, **kwargs):
            self.languages = languages

        def readtext(self, image, *args, **kwargs):
            path = _ensure_image_path(image)
            prompt = (
                "Read all visible text from this image. "
                "Return one line per detected text span using the format: recognized text"
            )
            text = _vlm_ocr_text(path, prompt)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return [([0, 0, 0, 0], line, 0.5) for line in lines]

    module.Reader = Reader
    return module


def _ensure_image_path(image: Any) -> str:
    if isinstance(image, (str, Path)):
        return str(image)
    if isinstance(image, Image.Image):
        temp_path = Path.cwd() / "_ocr_temp_input.png"
        image.save(temp_path)
        return str(temp_path)
    if isinstance(image, np.ndarray):
        temp_path = Path.cwd() / "_ocr_temp_input.png"
        Image.fromarray(image).save(temp_path)
        return str(temp_path)
    raise TypeError(f"Unsupported image type for OCR shim: {type(image)!r}")


def _vlm_ocr_text(image_path: str, prompt: str) -> str:
    from tools.implementations.shared.vlm_helper import create_vlm_client

    client = create_vlm_client()
    messages = [
        {"role": "system", "content": "You are an OCR system."},
        {"role": "user", "content": client.image_message_parts(str(image_path), prompt)},
    ]
    from core.vlm_client import ModelSettings

    response, _ = client.chat(messages, ModelSettings(temperature=0.0, max_tokens=800))
    return str(response).strip()


@contextlib.contextmanager
def _pushd(path: Path):
    current = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(current)


def _daily_value(daily: dict[str, Any], key: str) -> Any:
    value = daily.get(key)
    if isinstance(value, list) and value:
        return value[0]
    return value


def _clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", unescape(text)).strip()
