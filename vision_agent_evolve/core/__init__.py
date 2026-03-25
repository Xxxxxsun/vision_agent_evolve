"""Core package exports with lazy imports.

This keeps data-only utilities importable even when runtime VLM deps are not
installed yet, which is important for dataset preparation scripts.
"""

from __future__ import annotations

from .types import TaskCase, AgentResult, AgentStep, ToolResult, Message

__all__ = [
    "TaskCase",
    "AgentResult",
    "AgentStep",
    "ToolResult",
    "Message",
    "VLMClient",
    "ModelSettings",
    "UsageStats",
    "ReActParser",
    "ReActAgent",
    "AgentConfig",
]


def __getattr__(name: str):
    if name in {"VLMClient", "ModelSettings", "UsageStats"}:
        from .vlm_client import VLMClient, ModelSettings, UsageStats

        mapping = {
            "VLMClient": VLMClient,
            "ModelSettings": ModelSettings,
            "UsageStats": UsageStats,
        }
        return mapping[name]

    if name == "ReActParser":
        from .parser import ReActParser

        return ReActParser

    if name in {"ReActAgent", "AgentConfig"}:
        from .agent import ReActAgent, AgentConfig

        mapping = {
            "ReActAgent": ReActAgent,
            "AgentConfig": AgentConfig,
        }
        return mapping[name]

    raise AttributeError(f"module 'core' has no attribute {name!r}")
