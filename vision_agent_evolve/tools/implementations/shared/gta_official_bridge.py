"""Bridge for invoking official GTA AgentLego tools when available."""

from __future__ import annotations

import base64
import importlib
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

from core.types import ToolResult


_TOOL_CACHE: dict[tuple[str, str, str], Any] = {}
_OFFICIAL_IMAGE_TOOLS = {"DrawBox", "AddText", "Plot", "TextToImage", "ImageStylization"}
_DEFAULT_REPO_CANDIDATES = [
    Path("/tmp/GTA_official"),
    Path("/root/vision_agent_evolve/GTA"),
]


def maybe_run_official_gta_tool(tool_name: str, params: dict[str, str]) -> ToolResult | None:
    """Attempt to run a GTA tool via the official implementation.

    Returns ``None`` when official execution is not configured or not available
    in ``auto`` mode. In strict official modes, failures are surfaced as
    ``ToolResult(status="error", ...)`` so the caller does not silently fall
    back to approximations.
    """
    mode = os.environ.get("VISION_AGENT_GTA_TOOL_MODE", "auto").strip().lower() or "auto"
    if mode in {"approx", "approx_only", "fallback"}:
        return None

    try:
        if mode in {"official_server", "server"}:
            return _run_via_tool_server(tool_name, params)
        if mode in {"official_local", "local"}:
            return _run_via_local_agentlego(tool_name, params)

        server_url = os.environ.get("VISION_AGENT_GTA_TOOL_SERVER", "").strip()
        if server_url:
            try:
                return _run_via_tool_server(tool_name, params)
            except Exception:
                pass
        return _run_via_local_agentlego(tool_name, params)
    except Exception as exc:
        if mode == "auto":
            return None
        return ToolResult(status="error", answer="", error=f"Official GTA tool '{tool_name}' failed: {exc}")


def _run_via_local_agentlego(tool_name: str, params: dict[str, str]) -> ToolResult:
    repo_root = _resolve_repo_root()
    if repo_root is None:
        raise RuntimeError(
            "Official GTA repo not found. Set VISION_AGENT_GTA_OFFICIAL_REPO to the cloned open-compass/GTA path."
        )

    agentlego_root = repo_root / "agentlego"
    if not agentlego_root.exists():
        raise RuntimeError(f"Missing agentlego/ under official GTA repo: {repo_root}")
    if str(agentlego_root) not in sys.path:
        sys.path.insert(0, str(agentlego_root))

    from agentlego.apis.tool import load_tool, register_all_tools

    benchmark_path = agentlego_root / "benchmark.py"
    if benchmark_path.exists():
        register_all_tools(_load_module_from_path("gta_official_benchmark", benchmark_path))

    device = os.environ.get("VISION_AGENT_GTA_DEVICE")
    cache_key = (str(agentlego_root), tool_name, device or "")
    tool = _TOOL_CACHE.get(cache_key)
    if tool is None:
        kwargs: dict[str, Any] = {}
        if device:
            kwargs["device"] = device
        tool = load_tool(tool_name, **kwargs)
        _TOOL_CACHE[cache_key] = tool

    call_kwargs = _coerce_params_for_tool(tool, params)
    result = tool(**call_kwargs)
    return _normalize_official_output(tool_name, result)


def _run_via_tool_server(tool_name: str, params: dict[str, str]) -> ToolResult:
    server_url = os.environ.get("VISION_AGENT_GTA_TOOL_SERVER", "").strip()
    if not server_url:
        raise RuntimeError("VISION_AGENT_GTA_TOOL_SERVER is not set.")

    endpoint = server_url.rstrip("/") + f"/{tool_name}"
    body, content_type = _encode_multipart_formdata(params)
    req = request.Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            payload = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code} {exc.reason}: {detail}") from exc

    parsed = json.loads(payload)
    return _normalize_official_output(tool_name, parsed)


def _normalize_official_output(tool_name: str, result: Any) -> ToolResult:
    if tool_name in _OFFICIAL_IMAGE_TOOLS:
        artifact = _normalize_image_artifact(tool_name, result)
        return ToolResult(status="ok", answer="", artifacts=[artifact] if artifact else [])

    if isinstance(result, bool):
        return ToolResult(status="ok", answer="true" if result else "false")
    if isinstance(result, (int, float, str)):
        return ToolResult(status="ok", answer=str(result))
    if isinstance(result, tuple):
        return ToolResult(status="ok", answer="\n".join(str(item) for item in result))
    if isinstance(result, dict):
        return ToolResult(status="ok", answer=json.dumps(result, ensure_ascii=False))
    if result is None:
        return ToolResult(status="ok", answer="")
    return ToolResult(status="ok", answer=str(result))


def _normalize_image_artifact(tool_name: str, result: Any) -> str | None:
    if isinstance(result, str):
        candidate = Path(result)
        if candidate.exists():
            return str(candidate)
        try:
            decoded = base64.b64decode(result, validate=True)
        except Exception:
            return None
        return _write_image_artifact(tool_name, decoded)

    if isinstance(result, dict):
        for value in result.values():
            artifact = _normalize_image_artifact(tool_name, value)
            if artifact:
                return artifact
        return None

    if isinstance(result, (list, tuple)):
        for item in result:
            artifact = _normalize_image_artifact(tool_name, item)
            if artifact:
                return artifact
        return None
    return None


def _write_image_artifact(tool_name: str, payload: bytes) -> str:
    output_dir = Path("artifacts")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"gta_official_{tool_name.lower()}_{uuid.uuid4().hex[:8]}.png"
    output_path.write_bytes(payload)
    return str(output_path)


def _encode_multipart_formdata(params: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----VisionAgentGTA" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for key, value in params.items():
        text = str(value)
        path = Path(text)
        if key == "image" and path.exists():
            filename = path.name
            mime_type = _guess_image_mime_type(path)
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode(),
                    f"Content-Type: {mime_type}\r\n\r\n".encode(),
                    path.read_bytes(),
                    b"\r\n",
                ]
            )
            continue

        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                text.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _guess_image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _coerce_params_for_tool(tool: Any, params: dict[str, str]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    arguments = getattr(tool, "arguments", {}) or {}
    for key, value in params.items():
        param = arguments.get(key)
        if param is None:
            coerced[key] = value
            continue
        target_type = getattr(param, "type", None)
        if target_type is bool:
            coerced[key] = str(value).strip().lower() in {"1", "true", "yes", "y"}
        elif target_type is int:
            coerced[key] = int(float(value))
        elif target_type is float:
            coerced[key] = float(value)
        else:
            coerced[key] = value
    return coerced


def _resolve_repo_root() -> Path | None:
    configured = os.environ.get("VISION_AGENT_GTA_OFFICIAL_REPO", "").strip()
    candidates = [Path(configured)] if configured else []
    candidates.extend(_DEFAULT_REPO_CANDIDATES)
    for candidate in candidates:
        if not candidate:
            continue
        if (candidate / "agentlego" / "benchmark.py").exists():
            return candidate
    return None


def _load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
