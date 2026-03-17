"""Tool registry and dispatcher."""

from __future__ import annotations
from pathlib import Path
from typing import Any

from core.types import ToolResult


class ToolRegistry:
    """Central registry for all tools."""

    def __init__(self):
        self._tools: dict[str, Any] = {}

    def register(self, name: str, tool_cls: type):
        """Register a tool class."""
        self._tools[name] = tool_cls

    def get(self, name: str) -> Any:
        """Get tool class by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_definitions(self) -> str:
        """Get tool definitions for agent prompt."""
        lines = [
            "- bash: Execute shell commands in working directory.",
            "",
            "Available CLI tools (call via bash):",
        ]

        for name, tool_cls in self._tools.items():
            try:
                tool = tool_cls()
                lines.append(f"  - {name}: {tool.description}")
                lines.append(f"    Usage: python -m tools {name} [args...]")
            except Exception:
                pass

        return "\n".join(lines)


# Global registry
_registry = ToolRegistry()


def register_tool(name: str, tool_cls: type):
    """Register a tool."""
    _registry.register(name, tool_cls)


def get_tool(name: str) -> Any:
    """Get tool by name."""
    return _registry.get(name)


def list_tools() -> list[str]:
    """List all tools."""
    return _registry.list_tools()


def get_tool_definitions() -> str:
    """Get tool definitions."""
    return _registry.get_definitions()
