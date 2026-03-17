"""Base tool interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from core.types import ToolResult


class Tool(ABC):
    """Base class for all tools."""

    @abstractmethod
    def run(self, **kwargs) -> ToolResult:
        """Execute the tool and return standardized result."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
