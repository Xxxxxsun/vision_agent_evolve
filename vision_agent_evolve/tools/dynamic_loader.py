"""Dynamic tool loader for learned tools."""

from __future__ import annotations
import sys
import importlib.util
import re
import os
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any


def discover_learned_tools(learned_dir: Path) -> dict[str, Path]:
    """Discover all learned tool files."""
    tools_dir = learned_dir / "tools"
    if not tools_dir.exists():
        return {}

    learned_tools = {}
    for tool_file in tools_dir.glob("*.py"):
        if tool_file.stem.startswith("_"):
            continue
        learned_tools[tool_file.stem] = tool_file

    return learned_tools


def load_tool_module(tool_path: Path) -> Any:
    """Dynamically load a tool module."""
    spec = importlib.util.spec_from_file_location(tool_path.stem, tool_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {tool_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[tool_path.stem] = module
    spec.loader.exec_module(module)

    return module


def get_tool_callable(module: Any, tool_name: str) -> Any:
    """Get the callable tool class from module."""
    # Try common patterns
    candidates = [
        tool_name,  # exact name
        "".join(word.capitalize() for word in tool_name.split("_")),  # PascalCase
        f"{tool_name}_tool",
        f"{tool_name}Tool",
    ]

    for candidate in candidates:
        if hasattr(module, candidate):
            return getattr(module, candidate)

    # Fallback: find any class that has 'run' method
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and hasattr(obj, "run"):
            return obj

    raise AttributeError(f"Cannot find tool class in {module}")


def execute_learned_tool(tool_path: Path, args: list[str]) -> str:
    """Execute a learned tool with given arguments."""
    try:
        execution_root = tool_path.parent
        project_root = Path(os.environ.get("VISION_AGENT_PROJECT_ROOT", "") or Path(__file__).parents[1])
        artifact_dir = Path(os.environ.get("VISION_AGENT_WORK_DIR", "") or execution_root / "artifacts")
        before_artifacts = _snapshot_artifacts(artifact_dir)
        old_cwd = Path.cwd()
        os.chdir(execution_root)
        try:
            module = load_tool_module(tool_path)

            # Preferred path: a simple top-level run(image_path, ...)
            if hasattr(module, "run") and callable(module.run):
                try:
                    result = module.run(*_normalize_run_args(args))
                    if result is not None:
                        output = str(result).strip() or "Tool executed with no output"
                        return _normalize_artifact_output(output, artifact_dir, before_artifacts, project_root)
                except TypeError:
                    # Some generated tools may expose run() but expect main()-style parsing.
                    pass

            # Try to call main() if exists
            if hasattr(module, "main"):
                # Temporarily replace sys.argv
                old_argv = sys.argv
                sys.argv = [str(tool_path)] + args
                try:
                    stdout_buffer = StringIO()
                    stderr_buffer = StringIO()
                    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                        module.main()
                    output = stdout_buffer.getvalue() + stderr_buffer.getvalue()
                    output = output.strip() or "Tool executed with no output"
                    return _normalize_artifact_output(output, artifact_dir, before_artifacts, project_root)
                finally:
                    sys.argv = old_argv

            # Otherwise try to instantiate and run
            tool_cls = get_tool_callable(module, tool_path.stem)
            tool = tool_cls()

            # Parse args into kwargs (simple: key=value pairs)
            kwargs = {}
            for arg in args:
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    kwargs[key] = value
                else:
                    # Positional args as numbered
                    kwargs[f"arg{len(kwargs)}"] = arg

            result = tool.run(**kwargs)
            return _normalize_artifact_output(str(result), artifact_dir, before_artifacts, project_root)
        finally:
            os.chdir(old_cwd)

    except Exception as e:
        return f"Error executing learned tool: {e}"


def _normalize_run_args(args: list[str]) -> list[str]:
    """Allow generated run(image_path) tools to accept common key=value image args."""
    if len(args) == 1 and "=" in args[0]:
        key, value = args[0].split("=", 1)
        if key.strip() in {"image", "image_path", "input", "path"}:
            return [value.strip()]
    return args


def _snapshot_artifacts(artifact_dir: Path) -> dict[Path, tuple[int, int]]:
    """Capture current artifact files with simple metadata."""
    if not artifact_dir.exists():
        return {}

    snapshot: dict[Path, tuple[int, int]] = {}
    for path in artifact_dir.rglob("*"):
        if path.is_file():
            stat = path.stat()
            snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def _normalize_artifact_output(
    output: str,
    artifact_dir: Path,
    before: dict[Path, tuple[int, int]],
    project_root: Path,
) -> str:
    """Normalize ARTIFACTS to the actual files written during this execution."""
    after = _snapshot_artifacts(artifact_dir)
    created_or_updated: list[str] = []
    for path, stat in after.items():
        if before.get(path) != stat:
            created_or_updated.append(_artifact_reference(path, project_root))

    actual_artifacts = sorted(created_or_updated)
    reported_artifacts = _extract_reported_artifacts(output)
    if os.environ.get("VISION_AGENT_WORK_DIR", "").strip():
        work_dir_artifacts = _resolve_reported_artifacts(reported_artifacts, artifact_dir, project_root)
        if work_dir_artifacts:
            actual_artifacts = work_dir_artifacts

    if not actual_artifacts:
        actual_artifacts = _resolve_reported_artifacts(reported_artifacts, artifact_dir, project_root)
        if not actual_artifacts:
            return output

    if reported_artifacts and reported_artifacts == actual_artifacts:
        return output

    artifact_line = f"ARTIFACTS: {', '.join(actual_artifacts)}"
    if "ARTIFACTS:" not in output:
        if not output.strip():
            return artifact_line
        return f"{output.rstrip()}\n{artifact_line}"

    return re.sub(r"ARTIFACTS:\s*.+", artifact_line, output, count=1)


def _artifact_reference(path: Path, project_root: Path) -> str:
    """Return an artifact path that downstream agents and validators can resolve."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _resolve_reported_artifacts(reported_artifacts: list[str], artifact_dir: Path, project_root: Path) -> list[str]:
    """Map reported artifact basenames to real work-dir files when snapshot diff is empty."""
    resolved: list[str] = []
    for artifact in reported_artifacts:
        path = Path(artifact)
        candidates = [path] if path.is_absolute() else [project_root / path, artifact_dir / path.name, artifact_dir / path]
        for candidate in candidates:
            if candidate.exists():
                resolved.append(_artifact_reference(candidate, project_root))
                break
    return sorted(resolved)


def _extract_reported_artifacts(output: str) -> list[str]:
    """Extract reported artifacts from tool output."""
    import re

    match = re.search(r"ARTIFACTS:\s*(.+)", output)
    if not match:
        return []
    return [artifact.strip() for artifact in match.group(1).split(",") if artifact.strip()]
