"""Preflight checks for GTA official-tool experiments."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


OFFICIAL_TOOL_NAMES = [
    "Calculator",
    "GoogleSearch",
    "Plot",
    "Solver",
    "OCR",
    "ImageDescription",
    "TextToBbox",
    "CountGivenObject",
    "MathOCR",
    "DrawBox",
    "AddText",
    "TextToImage",
    "ImageStylization",
    "RegionAttributeDescription",
]

LOCAL_REQUIRED_MODULES = [
    "easyocr",
    "mmpretrain",
    "mmengine",
    "mmcv",
    "mmdet",
    "sympy",
    "matplotlib",
    "requests",
    "diffusers",
    "langid",
]


def _check_env_var(name: str) -> dict[str, Any]:
    value = os.environ.get(name, "").strip()
    return {"name": name, "present": bool(value)}


def _check_command(name: str) -> dict[str, Any]:
    return {"name": name, "path": shutil.which(name) or ""}


def _check_import(name: str) -> dict[str, Any]:
    try:
        importlib.import_module(name)
        return {"name": name, "ok": True}
    except Exception as exc:  # pragma: no cover - defensive
        return {"name": name, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _check_repo(repo_root: Path) -> dict[str, Any]:
    return {
        "path": str(repo_root),
        "exists": repo_root.exists(),
        "agentlego_benchmark_exists": (repo_root / "agentlego" / "benchmark.py").exists(),
        "toollist_exists": (repo_root / "agentlego" / "benchmark_toollist.txt").exists(),
    }


def _check_server(server_url: str, required_tools: list[str]) -> dict[str, Any]:
    openapi_url = server_url.rstrip("/") + "/openapi.json"
    try:
        with request.urlopen(openapi_url, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.URLError as exc:
        return {"url": server_url, "reachable": False, "error": f"{type(exc).__name__}: {exc}"}

    paths = payload.get("paths", {}) if isinstance(payload, dict) else {}
    available = sorted(path.strip("/") for path in paths.keys())
    missing = [name for name in required_tools if name not in available]
    return {
        "url": server_url,
        "reachable": True,
        "available_count": len(available),
        "missing_tools": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the environment is ready for GTA official-tool experiments.")
    parser.add_argument("--repo-root", default=os.environ.get("VISION_AGENT_GTA_OFFICIAL_REPO", "/tmp/GTA_official"))
    parser.add_argument("--server-url", default=os.environ.get("VISION_AGENT_GTA_TOOL_SERVER", ""))
    parser.add_argument("--mode", choices=["server", "local"], default="server")
    parser.add_argument("--require-keys", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    payload: dict[str, Any] = {
        "mode": args.mode,
        "official_tool_names": list(OFFICIAL_TOOL_NAMES),
        "repo": _check_repo(repo_root),
        "commands": [_check_command(name) for name in ["agentlego-server", "mim", "nvidia-smi"]],
        "env": [
            _check_env_var("SERPER_API_KEY"),
            _check_env_var("MATHPIX_APP_ID"),
            _check_env_var("MATHPIX_APP_KEY"),
            _check_env_var("VISION_AGENT_GTA_TOOL_MODE"),
            _check_env_var("VISION_AGENT_GTA_TOOL_SERVER"),
            _check_env_var("VISION_AGENT_GTA_OFFICIAL_REPO"),
            _check_env_var("VISION_AGENT_GTA_DEVICE"),
        ],
    }

    if args.mode == "local":
        payload["imports"] = [_check_import(name) for name in LOCAL_REQUIRED_MODULES]

    if args.mode == "server" and args.server_url:
        payload["server"] = _check_server(args.server_url, OFFICIAL_TOOL_NAMES)
    elif args.mode == "server":
        payload["server"] = {"url": "", "reachable": False, "error": "Missing --server-url"}

    failures: list[str] = []
    if not payload["repo"]["agentlego_benchmark_exists"]:
        failures.append("official GTA repo is missing agentlego/benchmark.py")
    if args.mode == "server":
        server = payload.get("server", {})
        if not server.get("reachable"):
            failures.append("official tool server is not reachable")
        if server.get("missing_tools"):
            failures.append("official tool server is missing required GTA tools")
        if not any(item["path"] for item in payload["commands"] if item["name"] == "agentlego-server"):
            failures.append("agentlego-server command is not available")
    if args.mode == "local":
        missing_imports = [item["name"] for item in payload.get("imports", []) if not item.get("ok")]
        if missing_imports:
            failures.append("missing local AgentLego dependencies: " + ", ".join(missing_imports))
    if args.require_keys:
        env_map = {item["name"]: item["present"] for item in payload["env"]}
        if not env_map.get("SERPER_API_KEY"):
            failures.append("SERPER_API_KEY is missing")
        if not env_map.get("MATHPIX_APP_ID") or not env_map.get("MATHPIX_APP_KEY"):
            failures.append("MATHPIX_APP_ID or MATHPIX_APP_KEY is missing")
    if not any(item["path"] for item in payload["commands"] if item["name"] == "nvidia-smi"):
        failures.append("GPU runtime check failed: nvidia-smi not found")

    payload["ok"] = not failures
    payload["failures"] = failures
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
