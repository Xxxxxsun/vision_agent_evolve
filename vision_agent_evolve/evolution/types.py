"""Data types for evolution system."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FailureAnalysis:
    """Analysis of why a task failed."""
    root_cause: str
    next_action: Literal["generate_tool", "generate_skill", "generate_both", "give_up"]
    confidence: float
    missing_step: str = ""
    tool_goal: str = ""
    skill_update_note: str = ""
    failure_stage: str = ""
    missing_capabilities: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class ToolProposal:
    """Proposal for a new tool."""
    name: str
    description: str
    applicability_conditions: str
    code: str
    usage_example: str
    expected_inputs: list[str]
    expected_outputs: list[str]


@dataclass
class SkillProposal:
    """Proposal for a new skill."""
    name: str
    description: str
    applicability_conditions: str
    content: str
    level: Literal["foundation", "high", "mid", "low"]
    depends_on: list[str]


@dataclass
class ValidationResult:
    """Result of validating a proposal."""
    passed: bool
    static_ok: bool = False
    origin_ok: bool = False
    regression_ok: bool = False
    reason: str = ""
    leakage_detected: bool = False
    failed_cases: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    input_image: str = ""
    chain_trace: list[str] = field(default_factory=list)
    replaced_existing_tool: bool = False


@dataclass
class ToolChainContext:
    """Current chained-tool context for a case."""
    tool_sequence: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    latest_input_image: str = ""
    latest_artifact: str = ""
    failed: bool = False
    reason: str = ""

    def summary(self) -> str:
        """Short human-readable summary for prompts/logs."""
        if not self.tool_sequence:
            return "No existing tool chain."

        lines = [
            f"Existing tool chain: {' -> '.join(self.tool_sequence)}",
            f"Latest input image: {self.latest_input_image or 'N/A'}",
            f"Latest artifact: {self.latest_artifact or 'N/A'}",
        ]
        if self.failed:
            lines.append(f"Chain status: failed ({self.reason})")
        return "\n".join(lines)


@dataclass
class ToolAvailabilitySnapshot:
    """Current trusted/ignored tool inventory for a learned subset."""
    available_tools: list[str] = field(default_factory=list)
    manifest_only_tools: list[str] = field(default_factory=list)
    untrusted_tools: list[str] = field(default_factory=list)

    def capability_lines(self) -> list[str]:
        """Human-readable lines for prompts/logs."""
        lines: list[str] = []
        if self.available_tools:
            lines.append("Available tools:")
            lines.extend(f"- tool:{name}" for name in self.available_tools)
        else:
            lines.append("Available tools:")
            lines.append("- none")

        ignored: list[str] = []
        ignored.extend(f"tool:{name} (missing source file)" for name in self.manifest_only_tools)
        ignored.extend(f"tool:{name} (untrusted due to hardcoded final answers)" for name in self.untrusted_tools)
        if ignored:
            lines.append("Ignored tools:")
            lines.extend(f"- {entry}" for entry in ignored)

        return lines

    def summary(self) -> str:
        """Short summary for analyzer logs."""
        return "\n".join(self.capability_lines())


@dataclass
class EvolutionStep:
    """Single step in evolution process."""
    iteration: int
    case_id: str
    analysis: FailureAnalysis | None = None
    tool_proposal: ToolProposal | None = None
    skill_proposal: SkillProposal | None = None
    validation: ValidationResult | None = None
    decision: Literal["keep", "discard", "give_up"] = "discard"
    solve_success: bool = False
