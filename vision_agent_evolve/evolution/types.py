"""Data types for evolution system."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FailureAnalysis:
    """Analysis of why a task failed."""
    root_cause: str
    next_action: Literal["generate_tool", "generate_skill", "generate_both", "generate_code_skill", "give_up"]
    confidence: float
    missing_step: str = ""
    tool_goal: str = ""
    skill_update_note: str = ""
    failure_stage: str = ""
    missing_capabilities: list[str] = field(default_factory=list)
    rationale: str = ""
    differentiation_note: str = ""


@dataclass
class FailedDirection:
    """Semantic record of one tried-and-failed evolve direction."""

    case_id: str
    attempt: int
    created_at: str
    root_cause: str
    missing_step: str
    next_action: Literal["generate_tool", "generate_skill", "generate_both", "generate_code_skill", "give_up"]
    tool_goal: str = ""
    skill_update_note: str = ""
    chain_trace: list[str] = field(default_factory=list)
    used_tool: str | None = None
    retry_answer: str | None = None
    failure_reason: str = ""
    source: str = "retry_failed"
    direction_signature: str = ""
    times_failed: int = 1
    last_failed_at: str = ""
    last_case_id: str = ""
    last_attempt: int = 0


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


@dataclass
class TrainSetEvalRecord:
    """One evaluation row from a frozen pass over a training subset."""

    case_id: str
    dataset_name: str
    capability_family: str
    prompt: str
    expected: str
    answer: str
    correct: bool
    score: float | None = None
    turns: int = 0
    tool_names: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    chain_trace: list[str] = field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


@dataclass
class TrainSetEvalSummary:
    """Aggregate score summary for one full training-subset evaluation."""

    total_cases: int
    correct_cases: int
    primary_score: float
    per_dataset_scores: dict[str, float] = field(default_factory=dict)
    per_family_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class FailureCluster:
    """A compact failure cluster used by the subset planner."""

    cluster_id: str
    dataset_name: str
    capability_family: str
    cluster_key: str
    total_cases: int
    representative_case_ids: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)


@dataclass
class TrainingSetDigest:
    """Planner-facing summary of baseline performance and recent history."""

    baseline_summary: TrainSetEvalSummary
    failure_clusters: list[FailureCluster] = field(default_factory=list)
    representative_cases: list[dict[str, str]] = field(default_factory=list)
    recent_rejected_plans: list[dict] = field(default_factory=list)
    candidate_summary: TrainSetEvalSummary | None = None
    per_dataset_delta: dict[str, float] = field(default_factory=dict)
    per_family_delta: dict[str, float] = field(default_factory=dict)
    top_regressions: list[dict[str, str | float]] = field(default_factory=list)
    top_improvements: list[dict[str, str | float]] = field(default_factory=list)


@dataclass
class CapabilityBundleProposal:
    """A planner proposal that may contain multiple tool and skill edits."""

    run_id: str
    target_family: str
    target_cluster_ids: list[str] = field(default_factory=list)
    representative_case_ids: list[str] = field(default_factory=list)
    rationale: str = ""
    expected_gain: str = ""
    tools: list[ToolProposal] = field(default_factory=list)
    skills: list[SkillProposal] = field(default_factory=list)


@dataclass
class CandidateEvalResult:
    """Outcome of one candidate bundle round."""

    run_id: str
    accepted: bool
    reason: str
    baseline_score: float
    candidate_score: float
    score_delta: float
    smoke_passed: bool
    target_family: str = ""
    target_cluster_ids: list[str] = field(default_factory=list)
    representative_case_ids: list[str] = field(default_factory=list)
    activated_snapshot: str = ""
    baseline_summary: TrainSetEvalSummary | None = None
    candidate_summary: TrainSetEvalSummary | None = None
