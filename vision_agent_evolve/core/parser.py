"""Response parser for ReAct agent."""

from __future__ import annotations
import json
import re
from dataclasses import dataclass
from typing import Any

from .types import AgentAction


@dataclass
class ParseResult:
    """Result of parsing agent response."""
    is_task_complete: bool = False
    is_format_error: bool = False
    action: AgentAction | None = None
    error_message: str | None = None


class ReActParser:
    """Parse ReAct format responses."""

    TASK_COMPLETE_PATTERN = re.compile(r"ACTION:\s*TASK_COMPLETE", re.IGNORECASE)
    FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.+?)(?:\nACTION:\s*TASK_COMPLETE|\Z)", re.IGNORECASE | re.DOTALL)

    def parse_response(self, response: str) -> ParseResult:
        """Parse agent response into action or completion signal."""
        # Try to extract action JSON
        action = self._extract_action(response)
        if action:
            return ParseResult(action=action)

        # Check for task completion only if no action was provided.
        if self.TASK_COMPLETE_PATTERN.search(response):
            if not self.FINAL_ANSWER_PATTERN.search(response):
                return ParseResult(
                    is_format_error=True,
                    error_message=(
                        "Completion is missing a final answer. Expected:\n"
                        "Final Answer: <your answer>\n"
                        "ACTION: TASK_COMPLETE"
                    ),
                )
            return ParseResult(is_task_complete=True)

        # Format error
        return ParseResult(
            is_format_error=True,
            error_message=(
                "Invalid action format. Expected:\n"
                "Action:\n"
                '{"name": "bash", "arguments": {"command": "..."}}\n'
                "Or:\n"
                "Final Answer: <your answer>\n"
                "ACTION: TASK_COMPLETE"
            ),
        )

    def _extract_action(self, response: str) -> AgentAction | None:
        """Extract action JSON from response."""
        # Locate the Action marker, then parse the first JSON object that follows.
        action_match = re.search(r"Action:\s*", response, re.IGNORECASE)
        if not action_match:
            return None

        action_text = response[action_match.end():].lstrip()
        json_start = action_text.find("{")
        if json_start == -1:
            return None

        decoder = json.JSONDecoder()
        try:
            action_dict, _ = decoder.raw_decode(action_text[json_start:])
            if not isinstance(action_dict, dict):
                return None
            if "name" not in action_dict or "arguments" not in action_dict:
                return None

            return AgentAction(
                name=str(action_dict["name"]),
                arguments=dict(action_dict["arguments"]),
            )
        except json.JSONDecodeError:
            return None

    def extract_final_answer(self, response: str) -> str:
        """Extract final answer from completion response."""
        match = self.FINAL_ANSWER_PATTERN.search(response)
        if match:
            return match.group(1).strip()
        return response.strip()

    @staticmethod
    def format_observation(text: str, max_length: int = 6000) -> str:
        """Format observation for agent, with truncation if needed."""
        if len(text) <= max_length:
            return f"Observation:\n{text}"

        # Truncate middle
        head_chars = 3000
        tail_chars = 3000
        omitted = len(text) - head_chars - tail_chars

        truncated = (
            f"{text[:head_chars]}\n"
            f"... [{omitted} characters omitted] ...\n"
            f"{text[-tail_chars:]}"
        )
        return f"Observation:\n{truncated}"
