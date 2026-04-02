"""Shared types for preset tool registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.types import ToolResult


@dataclass(frozen=True)
class BuiltinToolSpec:
    name: str
    description: str
    applicability: str
    benchmark_notes: str
    chain_safe: bool
    runner: Callable[..., ToolResult]
    usage_example: str
