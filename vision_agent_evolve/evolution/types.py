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
    primitive_category: str = ""


@dataclass
class CoverageContract:
    """Cluster-level generalization contract created before generation."""

    target_family: str
    target_cluster_ids: list[str] = field(default_factory=list)
    problem_pattern: str = ""
    supported_variations: list[str] = field(default_factory=list)
    unsupported_variations: list[str] = field(default_factory=list)
    forbidden_case_specific_assumptions: list[str] = field(default_factory=list)
    primitive_category: str = ""
    tool_validation_scope: Literal["cluster", "family"] = "cluster"
    recommended_action: Literal["generate_tool", "generate_skill", "generate_both", "generate_code_skill", "give_up"] = "generate_skill"
    why_this_should_generalize: str = ""


@dataclass
class RevisionBrief:
    """Structured rewrite guidance derived from validator failures."""

    failure_type: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    rewrite_requirements: list[str] = field(default_factory=list)
    banned_patterns: list[str] = field(default_factory=list)
    retry_action: Literal["revise_tool", "revise_skill", "switch_to_skill", "switch_to_tool", "give_up"] = "give_up"


@dataclass
class SkillReferenceProposal:
    """One referenced branch/detail document inside a skill package."""

    path: str
    content: str
    description: str = ""


@dataclass
class SkillProposal:
    """Proposal for a new skill."""
    name: str
    description: str
    applicability_conditions: str
    content: str
    level: Literal["foundation", "high", "mid", "low"]
    depends_on: list[str]
    references: list[SkillReferenceProposal] = field(default_factory=list)


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
    failure_type: str = ""
    revision_brief: RevisionBrief | None = None
    smoke_case_results: list[dict[str, str | bool]] = field(default_factory=list)


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
    case_ids: list[str] = field(default_factory=list)
    representative_case_ids: list[str] = field(default_factory=list)
    summary_lines: list[str] = field(default_factory=list)
    common_failure_signals: list[str] = field(default_factory=list)
    shared_tool_patterns: list[str] = field(default_factory=list)
    shared_prompt_patterns: list[str] = field(default_factory=list)


@dataclass
class ClusterMemory:
    """Structured training-memory record for one failure cluster."""

    cluster_id: str
    dataset_name: str
    capability_family: str
    cluster_key: str
    total_cases: int
    case_ids: list[str] = field(default_factory=list)
    representative_case_ids: list[str] = field(default_factory=list)
    common_failure_signals: list[str] = field(default_factory=list)
    shared_tool_patterns: list[str] = field(default_factory=list)
    shared_prompt_patterns: list[str] = field(default_factory=list)
    example_case_summaries: list[str] = field(default_factory=list)
    primitive_category: str = ""
    toolability: str = "unknown"


@dataclass
class ToolboxGap:
    """One reusable primitive the family appears to be missing."""

    primitive_category: str
    summary: str
    target_cluster_ids: list[str] = field(default_factory=list)
    target_case_ids: list[str] = field(default_factory=list)
    supported_patterns: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    recommended_action: Literal["generate_tool", "generate_skill", "give_up"] = "generate_skill"


@dataclass
class FamilyToolRecord:
    """One active family tool tracked in planner memory."""

    name: str
    primitive_category: str
    applicability_conditions: str = ""
    supported_families: list[str] = field(default_factory=list)
    supported_cluster_patterns: list[str] = field(default_factory=list)
    validation_scope: Literal["cluster", "family"] = "cluster"
    notes: list[str] = field(default_factory=list)


@dataclass
class MasteryStrategyCandidate:
    """One candidate policy for using existing tools in a family."""

    name: str
    tool_sequence: list[str] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)
    avoid_conditions: list[str] = field(default_factory=list)
    fallback_action: str = "answer_directly"
    rationale: str = ""


@dataclass
class MasteryEvalResult:
    """Evaluation result for one mastery strategy candidate."""

    strategy_name: str
    evaluated_case_ids: list[str] = field(default_factory=list)
    supported_case_ids: list[str] = field(default_factory=list)
    failed_case_ids: list[str] = field(default_factory=list)
    coverage: float = 0.0
    precision: float = 0.0
    score_delta: float = 0.0
    supported_cluster_patterns: list[str] = field(default_factory=list)
    failure_cluster_patterns: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class MasteryProfile:
    """Family-level tool-boundary profile learned during mastery exploration."""

    capability_family: str
    primary_tool: str = ""
    tool_sequence: list[str] = field(default_factory=list)
    supported_families: list[str] = field(default_factory=list)
    supported_cluster_patterns: list[str] = field(default_factory=list)
    negative_cluster_patterns: list[str] = field(default_factory=list)
    success_case_ids: list[str] = field(default_factory=list)
    failure_case_ids: list[str] = field(default_factory=list)
    common_success_signals: list[str] = field(default_factory=list)
    common_failure_signals: list[str] = field(default_factory=list)
    recommended_trigger_conditions: list[str] = field(default_factory=list)
    negative_trigger_conditions: list[str] = field(default_factory=list)
    best_chain_patterns: list[str] = field(default_factory=list)
    bad_chain_patterns: list[str] = field(default_factory=list)
    best_strategy_name: str = ""
    coverage: float = 0.0
    precision: float = 0.0
    score_delta: float = 0.0
    candidate_evaluations: list[MasteryEvalResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class FamilyMemory:
    """Structured training-memory record for one capability family."""

    capability_family: str
    dataset_names: list[str] = field(default_factory=list)
    total_cases: int = 0
    failed_cases: int = 0
    baseline_score: float = 0.0
    common_question_patterns: list[str] = field(default_factory=list)
    recurring_failure_signals: list[str] = field(default_factory=list)
    tool_usage_patterns: list[str] = field(default_factory=list)
    recent_revision_briefs: list[str] = field(default_factory=list)
    recent_coverage_notes: list[str] = field(default_factory=list)
    cluster_memories: list[ClusterMemory] = field(default_factory=list)
    toolbox_gaps: list[ToolboxGap] = field(default_factory=list)
    family_toolbox: list[FamilyToolRecord] = field(default_factory=list)
    cross_cluster_validation_history: list[str] = field(default_factory=list)
    mastery_profiles: list[MasteryProfile] = field(default_factory=list)
    mastery_history: list[str] = field(default_factory=list)


@dataclass
class TrainingSetDigest:
    """Planner-facing summary of baseline performance and recent history."""

    baseline_summary: TrainSetEvalSummary
    failure_clusters: list[FailureCluster] = field(default_factory=list)
    representative_cases: list[dict[str, str]] = field(default_factory=list)
    recent_rejected_plans: list[dict] = field(default_factory=list)
    family_memories: list[FamilyMemory] = field(default_factory=list)
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
    coverage_contract: CoverageContract | None = None
    primitive_category: str = ""
    tools: list[ToolProposal] = field(default_factory=list)
    skills: list[SkillProposal] = field(default_factory=list)
    mastery_profile: MasteryProfile | None = None


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
    eval_diff: dict[str, object] = field(default_factory=dict)
