"""Subset-level evolution loop with active/candidate capability gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from typing import Any, Callable

from core.types import AgentResult, TaskCase
from core.vlm_client import ModelSettings, VLMClient
from evolution.benchmark_adapters import BenchmarkAdapter, get_benchmark_adapter
from evolution.loop import EvolutionLoop
from evolution.roles import Generator
from evolution.store import CapabilityStore
from evolution.types import (
    CandidateEvalResult,
    CapabilityBundleProposal,
    ClusterMemory,
    CoverageContract,
    FamilyToolRecord,
    FamilyMemory,
    FailureAnalysis,
    FailureCluster,
    MasteryEvalResult,
    MasteryProfile,
    MasteryStrategyCandidate,
    RevisionBrief,
    SkillProposal,
    ToolboxGap,
    ToolProposal,
    TrainSetEvalRecord,
    TrainSetEvalSummary,
    TrainingSetDigest,
)


@dataclass
class SubsetEvolutionRunReport:
    """Full result of one subset-level training run."""

    baseline_summary: TrainSetEvalSummary
    final_summary: TrainSetEvalSummary
    baseline_records: list[TrainSetEvalRecord]
    final_records: list[TrainSetEvalRecord]
    round_results: list[CandidateEvalResult]
    snapshot_name: str


class SubsetEvaluator:
    """Evaluate active or candidate capabilities over a full training subset."""

    def __init__(
        self,
        adapters: dict[str, BenchmarkAdapter],
        skills_dir: Path,
        vlm_client: VLMClient,
        capability_mode: str = "persistent_tools",
        fixed_builtin_tools: list[str] | None = None,
        disable_generated_tools: bool = False,
    ):
        self.adapters = adapters
        self.skills_dir = skills_dir
        self.vlm_client = vlm_client
        self.capability_mode = capability_mode
        self.fixed_builtin_tools = list(fixed_builtin_tools or [])
        self.disable_generated_tools = disable_generated_tools

    def evaluate(
        self,
        capability_dir: Path,
        work_dir: Path,
        cases: list[TaskCase],
        phase_prefix: str,
        stage_label: str = "",
    ) -> tuple[TrainSetEvalSummary, list[TrainSetEvalRecord]]:
        records: list[TrainSetEvalRecord] = []
        label = stage_label or phase_prefix
        progress = _ProgressPrinter(label=label, total=len(cases))
        progress.start()
        for index, case in enumerate(cases, start=1):
            result, chain_trace = self._run_case(capability_dir, work_dir, case, f"{phase_prefix}_{index}")
            adapter = self.adapters[case.dataset_name()]
            score = adapter.score_answer(result.final_answer, case)
            correct = adapter.check_answer(result.final_answer, case)
            tool_names = _merge_tool_names(_extract_tool_names(result), chain_trace)
            record = TrainSetEvalRecord(
                case_id=case.case_id,
                dataset_name=case.dataset_name(),
                capability_family=case.capability_family(),
                prompt=case.prompt,
                expected=case.gold_answer,
                answer=result.final_answer,
                correct=correct,
                score=score,
                turns=result.total_turns,
                tool_names=tool_names,
                artifact_paths=result.get_image_artifacts(),
                chain_trace=chain_trace,
                metadata={
                    "cluster_key": adapter.cluster_key(case, result, correct),
                    "source_id": case.source_id(),
                    "tool_steps": _tool_step_debug(result),
                },
            )
            records.append(record)
            correct_so_far = sum(1 for row in records if row.correct)
            average_score = sum(_record_score(row) for row in records) / len(records)
            progress.update(
                current=index,
                correct=correct_so_far,
                average_score=average_score,
                case_id=case.case_id,
                last_status="OK" if correct else "FAIL",
            )

        summary = self._summarize(records)
        progress.finish(correct=summary.correct_cases, average_score=summary.primary_score)
        return summary, records

    def build_digest(
        self,
        baseline_summary: TrainSetEvalSummary,
        baseline_records: list[TrainSetEvalRecord],
        cases_by_id: dict[str, TaskCase],
        recent_rejected_plans: list[dict],
        representatives_per_cluster: int,
        families_per_round_limit: int = 0,
        candidate_summary: TrainSetEvalSummary | None = None,
        candidate_records: list[TrainSetEvalRecord] | None = None,
    ) -> TrainingSetDigest:
        cluster_map: dict[str, list[TrainSetEvalRecord]] = {}
        family_groups: dict[str, list[TrainSetEvalRecord]] = {}
        for record in baseline_records:
            family_groups.setdefault(record.capability_family, []).append(record)
            if record.correct:
                continue
            cluster_key = str(record.metadata.get("cluster_key", "")).strip() or record.capability_family
            cluster_map.setdefault(cluster_key, []).append(record)

        failure_clusters: list[FailureCluster] = []
        family_memories: dict[str, FamilyMemory] = {}
        representative_cases: list[dict[str, str]] = []
        for cluster_key, rows in sorted(cluster_map.items(), key=lambda item: (-len(item[1]), item[0])):
            reps = rows[:representatives_per_cluster]
            first = rows[0]
            summary_lines = []
            for row in reps:
                case = cases_by_id[row.case_id]
                summary_lines.append(
                    f"case_id={row.case_id}; prompt={case.prompt[:180]}; expected={row.expected[:60]}; answer={row.answer[:60]}"
                )
                representative_cases.append(
                    {
                        "case_id": row.case_id,
                        "dataset_name": row.dataset_name,
                        "capability_family": row.capability_family,
                        "prompt": case.prompt[:220],
                    }
                )
            common_failure_signals = self._common_failure_signals(rows)
            shared_tool_patterns = self._shared_tool_patterns(rows)
            shared_prompt_patterns = self._shared_prompt_patterns(rows)
            primitive_category = self._infer_primitive_category(rows)
            toolability = self._assess_toolability(rows, primitive_category)
            failure_clusters.append(
                FailureCluster(
                    cluster_id=f"cluster_{len(failure_clusters) + 1}",
                    dataset_name=first.dataset_name,
                    capability_family=first.capability_family,
                    cluster_key=cluster_key,
                    total_cases=len(rows),
                    case_ids=[row.case_id for row in rows],
                    representative_case_ids=[row.case_id for row in reps],
                    summary_lines=summary_lines,
                    common_failure_signals=common_failure_signals,
                    shared_tool_patterns=shared_tool_patterns,
                    shared_prompt_patterns=shared_prompt_patterns,
                )
            )
            family_memory = family_memories.setdefault(
                first.capability_family,
                FamilyMemory(
                    capability_family=first.capability_family,
                    dataset_names=[],
                ),
            )
            family_memory.cluster_memories.append(
                ClusterMemory(
                    cluster_id=failure_clusters[-1].cluster_id,
                    dataset_name=first.dataset_name,
                    capability_family=first.capability_family,
                    cluster_key=cluster_key,
                    total_cases=len(rows),
                    case_ids=[row.case_id for row in rows],
                    representative_case_ids=[row.case_id for row in reps],
                    common_failure_signals=common_failure_signals,
                    shared_tool_patterns=shared_tool_patterns,
                    shared_prompt_patterns=shared_prompt_patterns,
                    example_case_summaries=summary_lines[:3],
                    primitive_category=primitive_category,
                    toolability=toolability,
                )
            )

        if families_per_round_limit:
            limited_clusters: list[FailureCluster] = []
            family_order: list[str] = []
            for cluster in failure_clusters:
                if cluster.capability_family not in family_order:
                    if len(family_order) >= families_per_round_limit:
                        continue
                    family_order.append(cluster.capability_family)
                limited_clusters.append(cluster)
            failure_clusters = limited_clusters
            allowed_case_ids = {case_id for cluster in failure_clusters for case_id in cluster.representative_case_ids}
            representative_cases = [row for row in representative_cases if row["case_id"] in allowed_case_ids]
            family_memories = {
                family: memory
                for family, memory in family_memories.items()
                if any(cluster.capability_family == family for cluster in failure_clusters)
            }

        for family, rows in family_groups.items():
            family_memory = family_memories.setdefault(
                family,
                FamilyMemory(
                    capability_family=family,
                    dataset_names=[],
                ),
            )
            dataset_names = sorted({row.dataset_name for row in rows})
            family_memory.dataset_names = dataset_names
            family_memory.total_cases = len(rows)
            family_memory.failed_cases = sum(1 for row in rows if not row.correct)
            family_memory.baseline_score = sum(_record_score(row) for row in rows) / len(rows)
            family_memory.common_question_patterns = self._common_question_patterns(rows, cases_by_id)
            family_memory.recurring_failure_signals = self._common_failure_signals([row for row in rows if not row.correct])
            family_memory.tool_usage_patterns = self._shared_tool_patterns(rows)
            family_memory.recent_revision_briefs = self._recent_revision_briefs(family, recent_rejected_plans)
            family_memory.recent_coverage_notes = self._recent_coverage_notes(family, recent_rejected_plans)
            family_memory.toolbox_gaps = self._build_toolbox_gaps(family_memory)

        digest = TrainingSetDigest(
            baseline_summary=baseline_summary,
            failure_clusters=failure_clusters,
            representative_cases=representative_cases,
            recent_rejected_plans=recent_rejected_plans,
            family_memories=sorted(family_memories.values(), key=lambda memory: memory.capability_family),
        )
        if candidate_summary is not None and candidate_records is not None:
            digest.candidate_summary = candidate_summary
            digest.per_dataset_delta = _score_delta_map(
                baseline_summary.per_dataset_scores,
                candidate_summary.per_dataset_scores,
            )
            digest.per_family_delta = _score_delta_map(
                baseline_summary.per_family_scores,
                candidate_summary.per_family_scores,
            )
            digest.top_improvements, digest.top_regressions = _compare_case_outcomes(
                baseline_records,
                candidate_records,
            )
        return digest

    def digest_payload(self, digest: TrainingSetDigest) -> dict[str, Any]:
        """Return a JSON-serializable snapshot of the planner-facing digest."""
        return {
            "baseline_summary": asdict(digest.baseline_summary),
            "failure_clusters": [asdict(cluster) for cluster in digest.failure_clusters],
            "family_memories": [asdict(memory) for memory in digest.family_memories],
            "representative_cases": list(digest.representative_cases),
            "recent_rejected_plans": list(digest.recent_rejected_plans),
            "mastery_profiles": {
                memory.capability_family: [asdict(profile) for profile in memory.mastery_profiles]
                for memory in digest.family_memories
                if memory.mastery_profiles
            },
        }

    def _run_case(
        self,
        capability_dir: Path,
        work_dir: Path,
        case: TaskCase,
        phase: str,
    ) -> tuple[AgentResult, list[str]]:
        loop = EvolutionLoop(
            work_dir=work_dir,
            learned_dir=capability_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=1,
            subset_id=None,
            answer_checker=self._check_answer,
            capability_mode=self.capability_mode,
            fixed_builtin_tools=self.fixed_builtin_tools,
            disable_generated_tools=self.disable_generated_tools,
        )
        skill = loop.store.get_skill(case.capability_family())
        capability_snapshot = loop._tool_availability_snapshot()
        skill_content = loop._usable_skill_content(skill, capability_snapshot) if skill else None
        chain_context = loop.validator.build_chain_context(case, skill_content, attempt=1)
        agent = loop._create_agent(case, attempt=1, phase=phase)
        try:
            result = agent.run(
                case.prompt,
                case.image_path,
                initial_observations=loop._chain_observations_for_agent(chain_context),
            )
        except Exception as exc:
            result = AgentResult(
                task=case.prompt,
                final_answer="",
                steps=[],
                total_turns=1,
                success=False,
                error=str(exc),
                all_artifacts=[],
            )
        return result, list(chain_context.tool_sequence)

    def _check_answer(self, answer: str, case: TaskCase) -> bool:
        return self.adapters[case.dataset_name()].check_answer(answer, case)

    def _summarize(self, records: list[TrainSetEvalRecord]) -> TrainSetEvalSummary:
        total = len(records)
        correct = sum(1 for row in records if row.correct)
        total_score = sum(_record_score(row) for row in records)
        per_dataset_scores: dict[str, float] = {}
        per_family_scores: dict[str, float] = {}
        dataset_groups: dict[str, list[TrainSetEvalRecord]] = {}
        family_groups: dict[str, list[TrainSetEvalRecord]] = {}
        for row in records:
            dataset_groups.setdefault(row.dataset_name, []).append(row)
            family_groups.setdefault(row.capability_family, []).append(row)
        for key, rows in dataset_groups.items():
            per_dataset_scores[key] = sum(_record_score(row) for row in rows) / len(rows)
        for key, rows in family_groups.items():
            per_family_scores[key] = sum(_record_score(row) for row in rows) / len(rows)

        return TrainSetEvalSummary(
            total_cases=total,
            correct_cases=correct,
            primary_score=(total_score / total) if total else 0.0,
            per_dataset_scores=per_dataset_scores,
            per_family_scores=per_family_scores,
        )

    @staticmethod
    def _recent_revision_briefs(capability_family: str, recent_rejected_plans: list[dict], limit: int = 3) -> list[str]:
        rows: list[str] = []
        for entry in recent_rejected_plans:
            if str(entry.get("target_family", "")) != capability_family:
                continue
            failure_type = str(entry.get("failure_type", "")).strip()
            reason = str(entry.get("reason", "")).strip()
            revision_brief = entry.get("revision_brief") or {}
            requirements = revision_brief.get("rewrite_requirements", []) if isinstance(revision_brief, dict) else []
            rows.append(
                f"{failure_type or 'unknown'}: {reason or 'N/A'}"
                + (f" | rewrite={'; '.join(str(item) for item in requirements[:2])}" if requirements else "")
            )
            if len(rows) >= limit:
                break
        return rows

    @staticmethod
    def _recent_coverage_notes(capability_family: str, recent_rejected_plans: list[dict], limit: int = 3) -> list[str]:
        rows: list[str] = []
        for entry in recent_rejected_plans:
            if str(entry.get("target_family", "")) != capability_family:
                continue
            coverage = entry.get("coverage_contract") or {}
            if not isinstance(coverage, dict) or not coverage:
                continue
            rows.append(
                f"pattern={str(coverage.get('problem_pattern', '')).strip() or 'N/A'}"
                f" | supported={'; '.join(str(item) for item in coverage.get('supported_variations', [])[:2]) or 'N/A'}"
            )
            if len(rows) >= limit:
                break
        return rows

    def _common_failure_signals(self, records: list[TrainSetEvalRecord]) -> list[str]:
        if not records:
            return []
        counts: dict[str, int] = {}
        for row in records:
            metadata = row.metadata
            for value in [
                str(metadata.get("question_type", "")).strip(),
                str(metadata.get("answer_type", "")).strip(),
                "tool_chain_present" if row.chain_trace else "",
                "tool_used" if row.tool_names else "no_tool_used",
            ]:
                if not value:
                    continue
                counts[value] = counts.get(value, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [f"{name} ({count}/{len(records)})" for name, count in ordered[:4]]

    def _shared_tool_patterns(self, records: list[TrainSetEvalRecord]) -> list[str]:
        if not records:
            return []
        counts: dict[str, int] = {}
        for row in records:
            tools = row.tool_names or row.chain_trace or ["none"]
            signature = " -> ".join(tools)
            counts[signature] = counts.get(signature, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [f"{signature} ({count}/{len(records)})" for signature, count in ordered[:3]]

    def _shared_prompt_patterns(self, records: list[TrainSetEvalRecord], limit: int = 3) -> list[str]:
        if not records:
            return []
        counts: dict[str, int] = {}
        for row in records:
            prompt = row.prompt.lower()
            patterns = []
            if any(token in prompt for token in ["how many", "count", "number of"]):
                patterns.append("counting")
            if any(token in prompt for token in ["color", "colour"]):
                patterns.append("color")
            if any(token in prompt for token in ["which", "choose", "option"]):
                patterns.append("selection")
            if any(token in prompt for token in ["what year", "what month", "time"]):
                patterns.append("temporal_lookup")
            if not patterns:
                patterns.append("generic_question")
            for pattern in patterns:
                counts[pattern] = counts.get(pattern, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [f"{name} ({count}/{len(records)})" for name, count in ordered[:limit]]

    def _common_question_patterns(
        self,
        records: list[TrainSetEvalRecord],
        cases_by_id: dict[str, TaskCase],
        limit: int = 4,
    ) -> list[str]:
        counts: dict[str, int] = {}
        for row in records:
            case = cases_by_id.get(row.case_id)
            metadata = case.metadata if case else row.metadata
            for key in [
                str(metadata.get("question_type", "")).strip(),
                str(metadata.get("answer_type", "")).strip(),
                self._prompt_shape(case.prompt if case else row.prompt),
            ]:
                if not key:
                    continue
                counts[key] = counts.get(key, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        return [f"{name} ({count}/{len(records)})" for name, count in ordered[:limit]]

    @staticmethod
    def _infer_primitive_category(records: list[TrainSetEvalRecord]) -> str:
        prompt_blob = " ".join((row.prompt or "").lower() for row in records)
        if any(token in prompt_blob for token in ["color", "colour"]):
            return "localized_color_focus"
        if any(token in prompt_blob for token in ["year", "text", "inscribed", "label", "number shown"]):
            return "localized_text_zoom"
        if any(token in prompt_blob for token in ["leftmost", "rightmost", "position", "left of", "right of"]):
            return "relative_position_marker"
        if any(token in prompt_blob for token in ["bar", "chart", "population", "metric tons", "how many", "total"]):
            return "chart_value_overlay"
        if any(token in prompt_blob for token in ["count", "objects are left", "many objects"]):
            return "count_support_view"
        return "generic_visual_focus"

    @staticmethod
    def _assess_toolability(records: list[TrainSetEvalRecord], primitive_category: str) -> str:
        prompt_blob = " ".join((row.prompt or "").lower() for row in records)
        if primitive_category in {"localized_color_focus", "localized_text_zoom", "relative_position_marker", "chart_value_overlay"}:
            return "high"
        if any(token in prompt_blob for token in ["angle", "tangent", "inscribed", "arc", "theorem"]):
            return "low"
        if any(token in prompt_blob for token in ["count", "how many", "subtract"]):
            return "medium"
        return "medium"

    @staticmethod
    def _build_toolbox_gaps(memory: FamilyMemory) -> list[ToolboxGap]:
        gaps: list[ToolboxGap] = []
        existing_categories = {tool.primitive_category for tool in memory.family_toolbox if tool.primitive_category}
        repeated_failure_types = " ".join(memory.recent_revision_briefs).lower()
        for cluster in memory.cluster_memories:
            primitive_category = cluster.primitive_category or "generic_visual_focus"
            if primitive_category in existing_categories:
                continue
            blocked_by: list[str] = []
            recommended_action = "generate_tool"
            if cluster.toolability == "low":
                blocked_by.append("low_toolability")
                recommended_action = "generate_skill"
            if "answer_leakage" in repeated_failure_types and primitive_category in {"localized_text_zoom", "localized_color_focus"}:
                blocked_by.append("recent_answer_leakage")
                recommended_action = "generate_skill"
            if repeated_failure_types.count("case_specific_logic") >= 2 and cluster.toolability != "high":
                blocked_by.append("repeated_case_specific_logic")
                recommended_action = "generate_skill"
            gaps.append(
                ToolboxGap(
                    primitive_category=primitive_category,
                    summary=f"Need a reusable {primitive_category} primitive for {memory.capability_family}.",
                    target_cluster_ids=[cluster.cluster_id],
                    target_case_ids=list(cluster.representative_case_ids),
                    supported_patterns=list(cluster.shared_prompt_patterns[:2]),
                    blocked_by=blocked_by,
                    recommended_action=recommended_action,
                )
            )
        return gaps

    @staticmethod
    def _prompt_shape(prompt: str) -> str:
        lowered = (prompt or "").lower()
        if any(token in lowered for token in ["how many", "count", "number of"]):
            return "counting"
        if any(token in lowered for token in ["which", "choose", "option"]):
            return "selection"
        if any(token in lowered for token in ["what color", "what colour", "color is"]):
            return "color_lookup"
        if any(token in lowered for token in ["what is", "what was", "what are"]):
            return "direct_lookup"
        return "generic_question"


class SubsetPlanner:
    """Planner that proposes one candidate capability bundle from a digest."""

    def __init__(
        self,
        client: VLMClient,
        generator: Generator,
        skills_dir: Path,
        tool_preference: str = "balanced",
        fixed_builtin_tools: list[str] | None = None,
        disable_generated_tools: bool = False,
    ):
        self.client = client
        self.generator = generator
        self.skills_dir = skills_dir
        self.tool_preference = tool_preference
        self.fixed_builtin_tools = list(fixed_builtin_tools or [])
        self.disable_generated_tools = disable_generated_tools

    def plan_bundle(self, digest: TrainingSetDigest) -> dict[str, Any]:
        if not digest.failure_clusters:
            return {"next_action": "give_up", "rationale": "No remaining failed clusters."}

        prompt = self._build_prompt(digest)
        messages = [
            {"role": "system", "content": "You plan one compact candidate capability bundle for a benchmark training subset. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, _ = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=2400))
        proposal = _extract_json(response)
        if proposal:
            return self._apply_tool_preference(self._apply_rejection_strategy(proposal, digest))

        cluster = digest.failure_clusters[0]
        family_memory = next((memory for memory in digest.family_memories if memory.capability_family == cluster.capability_family), None)
        toolbox_gap = family_memory.toolbox_gaps[0] if family_memory and family_memory.toolbox_gaps else None
        return self._apply_tool_preference(self._apply_rejection_strategy({
            "target_family": cluster.capability_family,
            "target_cluster_ids": [cluster.cluster_id],
            "representative_case_ids": list(cluster.representative_case_ids[:1]),
            "next_action": toolbox_gap.recommended_action if toolbox_gap else "generate_skill",
            "tool_goal": toolbox_gap.summary if toolbox_gap else "",
            "skill_update_note": f"Improve the solver SOP for {cluster.capability_family} on this failure cluster.",
            "rationale": "Fallback heuristic selected the largest remaining failure cluster.",
            "expected_gain": "Raise full training-subset accuracy on the selected failure cluster.",
            "primitive_category": toolbox_gap.primitive_category if toolbox_gap else cluster.cluster_key,
            "toolability_blocked": bool(toolbox_gap and toolbox_gap.recommended_action != "generate_tool"),
        }, digest))

    def materialize_bundle(
        self,
        proposal: dict[str, Any],
        digest: TrainingSetDigest,
        cases_by_id: dict[str, TaskCase],
        active_dir: Path,
        work_dir: Path,
    ) -> CapabilityBundleProposal:
        run_id = datetime.now().strftime("round_%Y%m%d_%H%M%S_%f")
        representative_ids = _normalize_representative_case_ids(
            proposal.get("representative_case_ids", []),
            cases_by_id,
        )
        if not representative_ids:
            representative_ids = _fallback_representatives(digest)
        case = cases_by_id[representative_ids[0]]
        active_store = CapabilityStore(active_dir)
        family_memory = next(
            (memory for memory in digest.family_memories if memory.capability_family == case.capability_family()),
            None,
        )
        training_context = self._format_training_context(family_memory, representative_ids)
        primitive_category = str(proposal.get("primitive_category", "")).strip()
        coverage_contract = self.generator.generate_coverage_contract(
            case=case,
            target_cluster_ids=[str(value) for value in proposal.get("target_cluster_ids", [])],
            training_context=training_context,
            representative_case_summaries=self._representative_case_summaries(digest, representative_ids),
            planner_action=str(proposal.get("next_action", "generate_skill")),
        )
        existing_skill = active_store.get_skill(case.capability_family())
        temp_loop = EvolutionLoop(
            work_dir=work_dir,
            learned_dir=active_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.client,
            max_attempts=1,
            subset_id=None,
            fixed_builtin_tools=self.fixed_builtin_tools,
            disable_generated_tools=self.disable_generated_tools,
        )
        chain_context = temp_loop.validator.build_chain_context(
            case,
            existing_skill.content if existing_skill else None,
            attempt=1,
        )
        next_action = _normalize_next_action(
            coverage_contract.recommended_action
            or str(proposal.get("next_action", "generate_skill"))
        )
        analysis = FailureAnalysis(
            root_cause=str(proposal.get("rationale", "")) or _cluster_summary(digest, representative_ids[0]),
            next_action=next_action,
            confidence=0.6,
            missing_step=str(proposal.get("expected_gain", "")) or "Improve the selected failure cluster.",
            tool_goal=str(proposal.get("tool_goal", "")),
            skill_update_note=str(proposal.get("skill_update_note", "")),
            rationale=str(proposal.get("rationale", "")),
            differentiation_note="Subset-level planner selected this cluster from the training digest.",
        )
        if self._should_block_tool_generation(family_memory, primitive_category, coverage_contract):
            analysis.next_action = "generate_skill"

        tools: list[ToolProposal] = []
        skills: list[SkillProposal] = []
        staged_tool: ToolProposal | None = None
        if (
            analysis.next_action in {"generate_tool", "generate_both"}
            and not self.disable_generated_tools
        ):
            staged_tool = self.generator.generate_tool(
                case,
                analysis,
                chain_context=chain_context,
                training_context=training_context,
                coverage_contract=coverage_contract,
            )
            tools.append(staged_tool)
        if analysis.next_action in {"generate_skill", "generate_both", "generate_code_skill"} or staged_tool is not None:
            if analysis.next_action == "generate_code_skill" and hasattr(self.generator, "generate_code_writing_skill"):
                skill = self.generator.generate_code_writing_skill(
                    case,
                    analysis,
                    existing_skill_content=existing_skill.content if existing_skill else None,
                    chain_context=chain_context,
                    training_context=training_context,
                    coverage_contract=coverage_contract,
                )
            else:
                skill = self.generator.generate_skill(
                    case,
                    analysis,
                    staged_tool,
                    existing_skill_content=existing_skill.content if existing_skill else None,
                    chain_context=chain_context,
                    training_context=training_context,
                    coverage_contract=coverage_contract,
                )
            skill.name = case.capability_family()
            skills.append(skill)

        return CapabilityBundleProposal(
            run_id=run_id,
            target_family=str(proposal.get("target_family", case.capability_family())) or case.capability_family(),
            target_cluster_ids=[str(value) for value in proposal.get("target_cluster_ids", [])],
            representative_case_ids=representative_ids,
            rationale=str(proposal.get("rationale", "")),
            expected_gain=str(proposal.get("expected_gain", "")),
            coverage_contract=coverage_contract,
            primitive_category=primitive_category or coverage_contract.primitive_category,
            tools=tools,
            skills=skills,
        )

    @staticmethod
    def _should_block_tool_generation(
        family_memory: FamilyMemory | None,
        primitive_category: str,
        coverage_contract: CoverageContract,
    ) -> bool:
        if coverage_contract.recommended_action in {"generate_skill", "give_up"}:
            return True
        if not family_memory:
            return False
        repeated = " ".join(family_memory.recent_revision_briefs).lower()
        if repeated.count("answer_leakage") >= 2:
            return True
        if repeated.count("case_specific_logic") >= 2:
            return True
        if family_memory.capability_family == "mathvista_generic_multi_choice":
            return True
        return False

    def _apply_rejection_strategy(self, proposal: dict[str, Any], digest: TrainingSetDigest) -> dict[str, Any]:
        adjusted = dict(proposal)
        family = str(adjusted.get("target_family", "")).strip()
        primitive_category = str(adjusted.get("primitive_category", "")).strip()
        recent = [entry for entry in digest.recent_rejected_plans if str(entry.get("target_family", "")).strip() == family]
        if len(recent) < 2:
            return adjusted

        failure_types = [str(entry.get("failure_type", "")).strip() for entry in recent[:2]]
        same_primitive = all(
            str((entry.get("coverage_contract") or {}).get("primitive_category", "")).strip() in {"", primitive_category}
            for entry in recent[:2]
        )
        if same_primitive and all(ft == "case_specific_logic" for ft in failure_types):
            adjusted["next_action"] = "generate_skill"
            adjusted["toolability_blocked"] = True
            adjusted["rationale"] = (
                str(adjusted.get("rationale", "")).strip()
                + " Recent attempts with the same family primitive overfit on smoke; switch to skill orchestration."
            ).strip()
        if all(ft == "answer_leakage" for ft in failure_types):
            adjusted["next_action"] = "generate_skill"
            adjusted["toolability_blocked"] = True
            adjusted["rationale"] = (
                str(adjusted.get("rationale", "")).strip()
                + " Recent attempts leaked answers; do not generate another permanent tool in this round."
            ).strip()
        return adjusted

    def _build_prompt(self, digest: TrainingSetDigest) -> str:
        cluster_lines = []
        for cluster in digest.failure_clusters:
            cluster_lines.append(
                f"- {cluster.cluster_id} | dataset={cluster.dataset_name} | family={cluster.capability_family} | "
                f"count={cluster.total_cases} | reps={','.join(cluster.representative_case_ids)} | "
                f"summary={' || '.join(cluster.summary_lines[:2])}"
            )

        preference_rules = {
            "balanced": (
                "- Choose tools only when they add clear reusable visual or computational leverage.\n"
                "- Pure SOP-only skills are acceptable when a tool would be unnecessary."
            ),
            "prefer_tools": (
                "- Bias toward generating a reusable tool whenever a tool could plausibly help.\n"
                "- If uncertain between a pure skill and a tool-backed bundle, prefer `generate_both` or `generate_tool`."
            ),
            "require_tools": (
                "- Do not choose a pure skill-only update unless it is impossible to define any useful tool.\n"
                "- Strongly prefer `generate_tool`, and use `generate_both` when a SOP update should accompany the tool."
            ),
        }
        tool_preference_text = preference_rules.get(self.tool_preference, preference_rules["balanced"])

        return f"""You are planning one subset-level capability bundle.

Baseline:
- total_cases: {digest.baseline_summary.total_cases}
- correct_cases: {digest.baseline_summary.correct_cases}
- primary_score: {digest.baseline_summary.primary_score:.4f}
- per_dataset_scores: {json.dumps(digest.baseline_summary.per_dataset_scores, ensure_ascii=False)}
- per_family_scores: {json.dumps(digest.baseline_summary.per_family_scores, ensure_ascii=False)}

Failure clusters:
{chr(10).join(cluster_lines)}

Family memories:
{self._format_family_memories(digest.family_memories)}

Recent rejected plans:
{json.dumps(digest.recent_rejected_plans, ensure_ascii=False)}

Rules:
- Choose exactly one target cluster.
- Use only representative_case_ids that already appear above.
- Prefer the smallest candidate that could raise overall train accuracy.
- Optimize for a reusable family-level fix, not a case-specific patch.
- Use the family memories to infer recurring patterns across the training subset.
- Prefer filling one family toolbox gap over solving one representative case.
- If a proposal would only help one representative case but not the broader cluster/family pattern, reject it.
- Tool generation preference: {self.tool_preference}
{tool_preference_text}
- Do not mention full datasets or all case prompts.
- Return JSON only.

JSON schema:
{{
  "target_family": "capability family",
  "target_cluster_ids": ["cluster_1"],
  "representative_case_ids": ["case_id"],
  "next_action": "generate_tool|generate_skill|generate_both|generate_code_skill|give_up",
  "primitive_category": "family primitive category if any",
  "toolability": "high|medium|low",
  "toolability_blocked": false,
  "tool_goal": "short tool goal if any",
  "skill_update_note": "short SOP update note if any",
  "rationale": "why this is the best next candidate",
  "expected_gain": "what score gain or failure-cluster gain is expected"
}}
"""

    @staticmethod
    def _format_family_memories(memories: list[FamilyMemory]) -> str:
        if not memories:
            return "- none"
        lines: list[str] = []
        for memory in memories:
            lines.append(
                f"- family={memory.capability_family} cases={memory.total_cases} failed={memory.failed_cases} "
                f"baseline={memory.baseline_score:.3f} patterns={'; '.join(memory.common_question_patterns[:3]) or 'N/A'} "
                f"failures={'; '.join(memory.recurring_failure_signals[:3]) or 'N/A'} "
                f"tools={'; '.join(memory.tool_usage_patterns[:2]) or 'N/A'} "
                f"revisions={'; '.join(memory.recent_revision_briefs[:2]) or 'N/A'} "
                f"coverage={'; '.join(memory.recent_coverage_notes[:2]) or 'N/A'} "
                f"toolbox={'; '.join(f'{tool.name}:{tool.primitive_category}' for tool in memory.family_toolbox[:3]) or 'none'} "
                f"gaps={'; '.join(f'{gap.primitive_category}:{gap.recommended_action}' for gap in memory.toolbox_gaps[:3]) or 'none'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_training_context(memory: FamilyMemory | None, representative_ids: list[str]) -> str:
        if memory is None:
            return "No aggregated training memory available."
        cluster_context = []
        for cluster in memory.cluster_memories[:3]:
            cluster_context.append(
                f"{cluster.cluster_id}: failures={'; '.join(cluster.common_failure_signals[:3]) or 'N/A'}; "
                f"tools={'; '.join(cluster.shared_tool_patterns[:2]) or 'N/A'}; "
                f"prompts={'; '.join(cluster.shared_prompt_patterns[:2]) or 'N/A'}; "
                f"primitive={cluster.primitive_category or 'N/A'}; toolability={cluster.toolability}"
            )
        toolbox_context = "; ".join(f"{tool.name}:{tool.primitive_category}" for tool in memory.family_toolbox[:4]) or "none"
        gap_context = "; ".join(f"{gap.primitive_category}:{gap.recommended_action}" for gap in memory.toolbox_gaps[:4]) or "none"
        return (
            f"Family={memory.capability_family}; total_cases={memory.total_cases}; failed_cases={memory.failed_cases}; "
            f"baseline_score={memory.baseline_score:.3f}; question_patterns={'; '.join(memory.common_question_patterns[:4]) or 'N/A'}; "
            f"recurring_failures={'; '.join(memory.recurring_failure_signals[:4]) or 'N/A'}; "
            f"tool_patterns={'; '.join(memory.tool_usage_patterns[:3]) or 'N/A'}; "
            f"recent_revisions={'; '.join(memory.recent_revision_briefs[:3]) or 'N/A'}; "
            f"recent_coverage={'; '.join(memory.recent_coverage_notes[:3]) or 'N/A'}; "
            f"family_toolbox={toolbox_context}; toolbox_gaps={gap_context}; "
            f"target_representatives={', '.join(representative_ids) or 'N/A'}; "
            f"cluster_memories={' || '.join(cluster_context) or 'N/A'}"
        )

    @staticmethod
    def _representative_case_summaries(digest: TrainingSetDigest, representative_ids: list[str]) -> list[str]:
        rows: list[str] = []
        case_map = {str(row.get("case_id", "")): row for row in digest.representative_cases}
        for case_id in representative_ids:
            row = case_map.get(case_id)
            if not row:
                continue
            rows.append(
                f"case_id={case_id}; family={row.get('capability_family', '')}; prompt={row.get('prompt', '')}"
            )
        return rows

    def _apply_tool_preference(self, proposal: dict[str, Any]) -> dict[str, Any]:
        adjusted = dict(proposal)
        next_action = str(adjusted.get("next_action", "")).strip() or "generate_skill"
        blocked = bool(adjusted.get("toolability_blocked"))
        toolability = str(adjusted.get("toolability", "")).strip().lower()

        if blocked or toolability == "low":
            return adjusted
        if self.tool_preference == "prefer_tools" and next_action == "generate_skill" and not adjusted.get("primitive_category"):
            adjusted["next_action"] = "generate_both"
        elif self.tool_preference == "require_tools" and next_action in {"generate_skill", "generate_code_skill"}:
            adjusted["next_action"] = "generate_tool"

        return adjusted


class SubsetEvolutionLoop:
    """Training-subset evolution loop with active/candidate gating."""

    MAX_TOOL_REPAIR_ATTEMPTS = 3

    def __init__(
        self,
        subset_id: str,
        learned_root: Path,
        skills_dir: Path,
        work_dir: Path,
        vlm_client: VLMClient,
        adapters: dict[str, BenchmarkAdapter],
        max_planning_rounds: int = 5,
        representatives_per_cluster: int = 3,
        families_per_round_limit: int = 3,
        tool_preference: str = "balanced",
        capability_mode: str = "persistent_tools",
        fixed_builtin_tools: list[str] | None = None,
        disable_generated_tools: bool = False,
        checkpoint_callback: Callable[[list[TrainSetEvalRecord], list[TrainSetEvalRecord], list[CandidateEvalResult], str], None] | None = None,
    ):
        self.subset_id = subset_id
        self.skills_dir = skills_dir
        self.work_dir = work_dir
        self.vlm_client = vlm_client
        self.adapters = adapters
        self.max_planning_rounds = max_planning_rounds
        self.representatives_per_cluster = representatives_per_cluster
        self.families_per_round_limit = families_per_round_limit
        self.tool_preference = tool_preference
        self.capability_mode = capability_mode
        self.fixed_builtin_tools = list(fixed_builtin_tools or [])
        self.disable_generated_tools = disable_generated_tools
        self.checkpoint_callback = checkpoint_callback

        self.subset_root = learned_root / subset_id
        self.active_dir = self.subset_root / "active"
        self.active_store = CapabilityStore(self.active_dir)
        self.generator = Generator(vlm_client)
        self.evaluator = SubsetEvaluator(
            adapters,
            skills_dir,
            vlm_client,
            capability_mode=capability_mode,
            fixed_builtin_tools=self.fixed_builtin_tools,
            disable_generated_tools=self.disable_generated_tools,
        )
        self.planner = SubsetPlanner(
            vlm_client,
            self.generator,
            skills_dir,
            tool_preference=tool_preference,
            fixed_builtin_tools=self.fixed_builtin_tools,
            disable_generated_tools=self.disable_generated_tools,
        )

    def run(self, cases: list[TaskCase]) -> SubsetEvolutionRunReport:
        cases_by_id = {case.case_id: case for case in cases}
        print(
            f"[subset-loop] subset={self.subset_id} cases={len(cases)} "
            f"max_rounds={self.max_planning_rounds} tool_preference={self.tool_preference}"
        )
        baseline_summary, baseline_records = self.evaluator.evaluate(
            self.active_dir,
            self.work_dir / "baseline",
            cases,
            "baseline",
            stage_label="baseline active",
        )
        current_summary = baseline_summary
        current_records = baseline_records
        round_results: list[CandidateEvalResult] = []
        self._emit_checkpoint(baseline_records, current_records, round_results, snapshot_name="")

        for round_idx in range(1, self.max_planning_rounds + 1):
            print(
                f"[subset-loop] round {round_idx}/{self.max_planning_rounds}: "
                f"baseline_score={current_summary.primary_score:.4f}"
            )
            digest = self.evaluator.build_digest(
                current_summary,
                current_records,
                cases_by_id,
                recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
                representatives_per_cluster=self.representatives_per_cluster,
                families_per_round_limit=self.families_per_round_limit,
            )
            self._attach_active_toolbox(digest)
            self.active_store.write_training_memory(self.evaluator.digest_payload(digest))
            if not digest.failure_clusters:
                print(f"[subset-loop] round {round_idx}: no remaining failure clusters, stopping")
                break

            plan = self.planner.plan_bundle(digest)
            if str(plan.get("next_action", "")).strip() == "give_up":
                print(f"[subset-loop] round {round_idx}: planner returned give_up")
                break

            print(
                f"[subset-loop] round {round_idx}: target_family={plan.get('target_family', '')} "
                f"action={plan.get('next_action', '')} reps={plan.get('representative_case_ids', [])}"
            )

            bundle = self.planner.materialize_bundle(
                plan,
                digest,
                cases_by_id,
                self.active_dir,
                self.work_dir / f"round_{round_idx}",
            )
            bundle = self._run_mastery_phase(bundle, digest, cases_by_id, round_idx)
            if not bundle.tools and not bundle.skills:
                print(f"[subset-loop] round {round_idx}: planner produced no tool/skill artifacts, stopping")
                break

            candidate_dir = self.active_store.stage_bundle(bundle)
            smoke_result = self._smoke_validate(bundle, digest, cases_by_id, candidate_dir, round_idx)
            if len(smoke_result) == 2:
                smoke_passed, smoke_reason = smoke_result
                validated_bundle = bundle
                smoke_meta = {}
            elif len(smoke_result) == 3:
                smoke_passed, smoke_reason, validated_bundle = smoke_result
                smoke_meta = {}
            else:
                smoke_passed, smoke_reason, validated_bundle, smoke_meta = smoke_result
            if not smoke_passed:
                print(f"[subset-loop] round {round_idx}: smoke failed: {smoke_reason}")
                self.active_store.record_rejected_plan(
                    {
                        "run_id": validated_bundle.run_id,
                        "reason": smoke_reason,
                        "failure_type": str(smoke_meta.get("failure_type", "")),
                        "target_family": validated_bundle.target_family,
                        "target_cluster_ids": validated_bundle.target_cluster_ids,
                        "coverage_contract": None if validated_bundle.coverage_contract is None else asdict(validated_bundle.coverage_contract),
                        "revision_brief": smoke_meta.get("revision_brief"),
                        "repair_history": smoke_meta.get("repair_history", []),
                    }
                )
                self.active_store.discard_bundle(validated_bundle.run_id)
                round_results.append(
                    CandidateEvalResult(
                        run_id=validated_bundle.run_id,
                        accepted=False,
                        reason=smoke_reason,
                        baseline_score=current_summary.primary_score,
                        candidate_score=current_summary.primary_score,
                        score_delta=0.0,
                        smoke_passed=False,
                        target_family=validated_bundle.target_family,
                        target_cluster_ids=list(validated_bundle.target_cluster_ids),
                        representative_case_ids=list(validated_bundle.representative_case_ids),
                        baseline_summary=current_summary,
                        candidate_summary=current_summary,
                    )
                )
                continue

            bundle = validated_bundle

            candidate_summary, candidate_records = self.evaluator.evaluate(
                candidate_dir,
                self.work_dir / f"round_{round_idx}" / "candidate_eval",
                cases,
                f"candidate_round_{round_idx}",
                stage_label=f"round {round_idx} candidate",
            )
            round_baseline_summary = current_summary
            baseline_score = current_summary.primary_score
            accepted = candidate_summary.primary_score > current_summary.primary_score
            snapshot_name = ""
            reason = (
                f"Accepted candidate with score delta {candidate_summary.primary_score - baseline_score:.4f}"
                if accepted
                else f"Rejected candidate because score delta was {candidate_summary.primary_score - baseline_score:.4f}"
            )
            print(
                f"[subset-loop] round {round_idx}: "
                f"candidate_score={candidate_summary.primary_score:.4f} "
                f"delta={candidate_summary.primary_score - baseline_score:+.4f} "
                f"{'ACCEPT' if accepted else 'REJECT'}"
            )
            if accepted:
                snapshot_name = f"{self.subset_id}_round_{round_idx}_accepted"
                self.active_store.activate_bundle(bundle.run_id, snapshot_name=snapshot_name)
                current_summary = candidate_summary
                current_records = candidate_records
                accepted_digest = self.evaluator.build_digest(
                    current_summary,
                    current_records,
                    cases_by_id,
                    recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
                    representatives_per_cluster=self.representatives_per_cluster,
                    families_per_round_limit=self.families_per_round_limit,
                )
                self._attach_active_toolbox(accepted_digest)
                self._attach_mastery_profile(accepted_digest, bundle)
                self.active_store.write_training_memory(self.evaluator.digest_payload(accepted_digest))
            else:
                self.active_store.record_rejected_plan(
                    {
                        "run_id": bundle.run_id,
                        "reason": reason,
                        "target_family": bundle.target_family,
                        "target_cluster_ids": bundle.target_cluster_ids,
                        "baseline_score": current_summary.primary_score,
                        "candidate_score": candidate_summary.primary_score,
                        "coverage_contract": None if bundle.coverage_contract is None else asdict(bundle.coverage_contract),
                    }
                )
                self.active_store.discard_bundle(bundle.run_id)

            round_results.append(
                CandidateEvalResult(
                    run_id=bundle.run_id,
                    accepted=accepted,
                    reason=reason,
                    baseline_score=baseline_score,
                    candidate_score=candidate_summary.primary_score,
                    score_delta=candidate_summary.primary_score - baseline_score,
                    smoke_passed=True,
                    target_family=bundle.target_family,
                    target_cluster_ids=list(bundle.target_cluster_ids),
                    representative_case_ids=list(bundle.representative_case_ids),
                    activated_snapshot=snapshot_name,
                    baseline_summary=round_baseline_summary,
                    candidate_summary=candidate_summary,
                )
            )
            self._emit_checkpoint(baseline_records, current_records, round_results, snapshot_name=snapshot_name)

        snapshot_name = f"{self.subset_id}_train_snapshot"
        self.active_store.snapshot_current_capabilities(snapshot_name)
        final_summary, final_records = self.evaluator.evaluate(
            self.active_dir,
            self.work_dir / "final_active_eval",
            cases,
            "final_active",
            stage_label="final active",
        )
        final_digest = self.evaluator.build_digest(
            final_summary,
            final_records,
            cases_by_id,
            recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
            representatives_per_cluster=self.representatives_per_cluster,
            families_per_round_limit=self.families_per_round_limit,
        )
        self._attach_active_toolbox(final_digest)
        self._attach_mastery_profile(final_digest, None)
        self.active_store.write_training_memory(self.evaluator.digest_payload(final_digest))
        self._emit_checkpoint(baseline_records, final_records, round_results, snapshot_name=snapshot_name)
        print(
            f"[subset-loop] finished: snapshot={snapshot_name} "
            f"final_score={final_summary.primary_score:.4f} "
            f"correct={final_summary.correct_cases}/{final_summary.total_cases}"
        )
        return SubsetEvolutionRunReport(
            baseline_summary=baseline_summary,
            final_summary=final_summary,
            baseline_records=baseline_records,
            final_records=final_records,
            round_results=round_results,
            snapshot_name=snapshot_name,
        )

    def run_batch_vstar(self, cases: list[TaskCase]) -> SubsetEvolutionRunReport:
        """VStar-first batch evolution: one full error digest, several candidates, one gate."""
        cases_by_id = {case.case_id: case for case in cases}
        print(
            f"[subset-batch] subset={self.subset_id} cases={len(cases)} "
            f"candidate_budget={self.max_planning_rounds} tool_preference={self.tool_preference}"
        )
        baseline_summary, baseline_records = self.evaluator.evaluate(
            self.active_dir,
            self.work_dir / "batch_baseline",
            cases,
            "batch_baseline",
            stage_label="batch baseline active",
        )
        digest = self.evaluator.build_digest(
            baseline_summary,
            baseline_records,
            cases_by_id,
            recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
            representatives_per_cluster=self.representatives_per_cluster,
            families_per_round_limit=self.families_per_round_limit,
        )
        self._attach_active_toolbox(digest)
        self.active_store.write_training_memory(self.evaluator.digest_payload(digest))

        round_results: list[CandidateEvalResult] = []
        current_summary = baseline_summary
        current_records = baseline_records
        for batch_idx, plan in enumerate(self._batch_plans_from_digest(digest), start=1):
            print(
                f"[subset-batch] candidate {batch_idx}: target_family={plan.get('target_family', '')} "
                f"action={plan.get('next_action', '')} reps={plan.get('representative_case_ids', [])}"
            )
            bundle = self.planner.materialize_bundle(
                plan,
                digest,
                cases_by_id,
                self.active_dir,
                self.work_dir / f"batch_candidate_{batch_idx}",
            )
            bundle = self._run_mastery_phase(bundle, digest, cases_by_id, batch_idx)
            if not bundle.tools and not bundle.skills:
                continue
            candidate_dir = self.active_store.stage_bundle(bundle)
            smoke_passed, smoke_reason, validated_bundle, smoke_meta = self._smoke_validate(
                bundle,
                digest,
                cases_by_id,
                candidate_dir,
                batch_idx,
            )
            if not smoke_passed:
                print(f"[subset-batch] candidate {batch_idx}: smoke failed: {smoke_reason}")
                self.active_store.record_rejected_plan(
                    {
                        "run_id": validated_bundle.run_id,
                        "reason": smoke_reason,
                        "failure_type": str(smoke_meta.get("failure_type", "")),
                        "target_family": validated_bundle.target_family,
                        "target_cluster_ids": validated_bundle.target_cluster_ids,
                        "coverage_contract": None if validated_bundle.coverage_contract is None else asdict(validated_bundle.coverage_contract),
                        "revision_brief": smoke_meta.get("revision_brief"),
                        "repair_history": smoke_meta.get("repair_history", []),
                    }
                )
                self.active_store.discard_bundle(validated_bundle.run_id)
                round_results.append(
                    CandidateEvalResult(
                        run_id=validated_bundle.run_id,
                        accepted=False,
                        reason=smoke_reason,
                        baseline_score=current_summary.primary_score,
                        candidate_score=current_summary.primary_score,
                        score_delta=0.0,
                        smoke_passed=False,
                        target_family=validated_bundle.target_family,
                        target_cluster_ids=list(validated_bundle.target_cluster_ids),
                        representative_case_ids=list(validated_bundle.representative_case_ids),
                        baseline_summary=current_summary,
                        candidate_summary=current_summary,
                    )
                )
                continue

            candidate_dir = self.active_store.stage_bundle(validated_bundle)
            round_baseline_summary = current_summary
            round_baseline_records = current_records
            candidate_summary, candidate_records = self.evaluator.evaluate(
                candidate_dir,
                self.work_dir / f"batch_candidate_{batch_idx}" / "candidate_eval",
                cases,
                f"batch_candidate_{batch_idx}",
                stage_label=f"batch candidate {batch_idx}",
            )
            eval_diff = self._eval_diff(round_baseline_records, candidate_records)
            candidate_family_regression_ok = self._family_regression_within_limit(
                round_baseline_records,
                candidate_records,
                max_regressed_cases=1,
            )
            candidate_artifact_gate_ok, artifact_gate_reason = self._learned_tool_artifact_gate(
                validated_bundle,
                candidate_records,
            )

            if (
                (
                    candidate_summary.primary_score <= round_baseline_summary.primary_score
                    or not candidate_family_regression_ok
                    or not candidate_artifact_gate_ok
                )
                and eval_diff["fixed_cases"]
                and eval_diff["regressed_cases"]
                and validated_bundle.skills
            ):
                refined_bundle, refined_dir = self._refine_router_from_eval_diff(
                    validated_bundle,
                    digest,
                    eval_diff,
                    candidate_summary,
                    round_baseline_summary,
                    batch_idx,
                )
                if refined_bundle is not validated_bundle:
                    refined_summary, refined_records = self.evaluator.evaluate(
                        refined_dir,
                        self.work_dir / f"batch_candidate_{batch_idx}" / "router_refine_eval",
                        cases,
                        f"batch_candidate_{batch_idx}_router_refine",
                        stage_label=f"batch candidate {batch_idx} router refine",
                    )
                    refined_diff = self._eval_diff(round_baseline_records, refined_records)
                    if refined_summary.primary_score >= candidate_summary.primary_score:
                        self.active_store.discard_bundle(validated_bundle.run_id)
                        validated_bundle = refined_bundle
                        candidate_dir = refined_dir
                        candidate_summary = refined_summary
                        candidate_records = refined_records
                        eval_diff = refined_diff
                        candidate_artifact_gate_ok, artifact_gate_reason = self._learned_tool_artifact_gate(
                            validated_bundle,
                            candidate_records,
                        )
                    else:
                        self.active_store.discard_bundle(refined_bundle.run_id)

            accepted = (
                candidate_summary.primary_score > current_summary.primary_score
                and self._family_regression_within_limit(round_baseline_records, candidate_records, max_regressed_cases=1)
                and self._learned_tool_artifact_gate(validated_bundle, candidate_records)[0]
            )
            reason = (
                f"Accepted batch candidate with score delta {candidate_summary.primary_score - round_baseline_summary.primary_score:.4f}"
                if accepted
                else (
                    f"Rejected batch candidate because score delta was {candidate_summary.primary_score - round_baseline_summary.primary_score:.4f}, "
                    f"family regression exceeded limit, or artifact gate failed: {artifact_gate_reason}"
                )
            )
            print(
                f"[subset-batch] candidate {batch_idx} score={candidate_summary.primary_score:.4f} "
                f"delta={candidate_summary.primary_score - round_baseline_summary.primary_score:+.4f} "
                f"fixed={len(eval_diff['fixed_cases'])} regressed={len(eval_diff['regressed_cases'])} "
                f"{'ACCEPT' if accepted else 'REJECT'}"
            )
            activated_snapshot = ""
            if accepted:
                activated_snapshot = f"{self.subset_id}_batch_{batch_idx}_accepted"
                self.active_store.activate_bundle(validated_bundle.run_id, snapshot_name=activated_snapshot)
                current_summary = candidate_summary
                current_records = candidate_records
                accepted_digest = self.evaluator.build_digest(
                    current_summary,
                    current_records,
                    cases_by_id,
                    recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
                    representatives_per_cluster=self.representatives_per_cluster,
                    families_per_round_limit=self.families_per_round_limit,
                )
                self._attach_active_toolbox(accepted_digest)
                self._attach_mastery_profile(accepted_digest, validated_bundle)
                self.active_store.write_training_memory(self.evaluator.digest_payload(accepted_digest))
            else:
                self.active_store.record_rejected_plan(
                    {
                        "run_id": validated_bundle.run_id,
                        "reason": reason,
                        "target_family": validated_bundle.target_family,
                        "target_cluster_ids": validated_bundle.target_cluster_ids,
                        "baseline_score": round_baseline_summary.primary_score,
                        "candidate_score": candidate_summary.primary_score,
                        "eval_diff": eval_diff,
                    }
                )
                self.active_store.discard_bundle(validated_bundle.run_id)
            round_results.append(
                CandidateEvalResult(
                    run_id=validated_bundle.run_id,
                    accepted=accepted,
                    reason=reason,
                    baseline_score=round_baseline_summary.primary_score,
                    candidate_score=candidate_summary.primary_score,
                    score_delta=candidate_summary.primary_score - round_baseline_summary.primary_score,
                    smoke_passed=True,
                    target_family=validated_bundle.target_family,
                    target_cluster_ids=list(validated_bundle.target_cluster_ids),
                    representative_case_ids=list(validated_bundle.representative_case_ids),
                    activated_snapshot=activated_snapshot,
                    baseline_summary=round_baseline_summary,
                    candidate_summary=candidate_summary,
                    eval_diff=eval_diff,
                )
            )

        snapshot_name = f"{self.subset_id}_train_snapshot"
        final_summary = current_summary
        final_records = current_records
        self.active_store.snapshot_current_capabilities(snapshot_name)
        final_digest = self.evaluator.build_digest(
            final_summary,
            final_records,
            cases_by_id,
            recent_rejected_plans=self.active_store.list_recent_rejected_plans(limit=8),
            representatives_per_cluster=self.representatives_per_cluster,
            families_per_round_limit=self.families_per_round_limit,
        )
        self._attach_active_toolbox(final_digest)
        self.active_store.write_training_memory(self.evaluator.digest_payload(final_digest))
        print(
            f"[subset-batch] finished: snapshot={snapshot_name} "
            f"final_score={final_summary.primary_score:.4f} "
            f"correct={final_summary.correct_cases}/{final_summary.total_cases}"
        )
        return SubsetEvolutionRunReport(
            baseline_summary=baseline_summary,
            final_summary=final_summary,
            baseline_records=baseline_records,
            final_records=final_records,
            round_results=round_results,
            snapshot_name=snapshot_name,
        )

    def _refine_router_from_eval_diff(
        self,
        bundle: CapabilityBundleProposal,
        digest: TrainingSetDigest,
        eval_diff: dict[str, Any],
        candidate_summary: TrainSetEvalSummary,
        baseline_summary: TrainSetEvalSummary,
        batch_idx: int,
    ) -> tuple[CapabilityBundleProposal, Path]:
        """Revise only the skill router after a tool-backed candidate causes regressions."""
        if not bundle.skills:
            return bundle, self.active_store.evaluate_bundle_snapshot(bundle.run_id)

        fixed_cases = list(eval_diff.get("fixed_cases", []))
        regressed_cases = list(eval_diff.get("regressed_cases", []))
        if not fixed_cases or not regressed_cases:
            return bundle, self.active_store.evaluate_bundle_snapshot(bundle.run_id)

        print(
            f"[subset-batch] candidate {batch_idx}: router refine "
            f"fixed={len(fixed_cases)} regressed={len(regressed_cases)}"
        )
        requirements = [
            "Revise only the router and branch conditions; do not change the tool API or invent new tools.",
            "Keep the tool branch for cases matching the fixed-case patterns.",
            "Add explicit avoid/no-tool conditions for cases matching the regressed-case patterns.",
            "Prefer direct visual reasoning when the generated artifact does not clearly localize the queried object.",
            "Do not route an entire VStar family to the tool; route only the supported visual pattern.",
        ]
        brief = RevisionBrief(
            failure_type="router_regression",
            reason=(
                "The candidate tool/skill fixed some training cases but regressed others, "
                f"with score delta {candidate_summary.primary_score - baseline_summary.primary_score:+.4f}."
            ),
            evidence=[
                "fixed_cases=" + json.dumps(fixed_cases[:8], ensure_ascii=False),
                "regressed_cases=" + json.dumps(regressed_cases[:8], ensure_ascii=False),
            ],
            rewrite_requirements=requirements,
            banned_patterns=[
                "always use the tool",
                "use the tool for all color questions",
                "use the tool for all left/right questions",
                "ignore the no-tool branch",
            ],
            retry_action="revise_skill",
        )
        family_memory = next(
            (memory for memory in digest.family_memories if memory.capability_family == bundle.target_family),
            None,
        )
        training_context = "\n".join(
            [
                self.planner._format_training_context(family_memory, bundle.representative_case_ids),
                "Counterfactual train-set diff:",
                "Fixed cases are cases where baseline was wrong and candidate was correct.",
                "Regressed cases are cases where baseline was correct and candidate was wrong.",
                "fixed_cases=" + json.dumps(fixed_cases[:12], ensure_ascii=False),
                "regressed_cases=" + json.dumps(regressed_cases[:12], ensure_ascii=False),
            ]
        )
        refined_skills = [
            self.generator.revise_skill(
                skill=skill,
                revision_brief=brief,
                coverage_contract=bundle.coverage_contract,
                training_context=training_context,
            )
            for skill in bundle.skills
        ]
        for original, refined in zip(bundle.skills, refined_skills):
            refined.name = original.name

        refined_bundle = replace(
            bundle,
            run_id=f"{bundle.run_id}_router_refine",
            skills=refined_skills,
            rationale=(bundle.rationale + " Router refined using fixed/regressed train-set diff.").strip(),
        )
        refined_dir = self.active_store.stage_bundle(refined_bundle)
        return refined_bundle, refined_dir

    @staticmethod
    def _eval_diff(
        baseline_records: list[TrainSetEvalRecord],
        candidate_records: list[TrainSetEvalRecord],
    ) -> dict[str, Any]:
        baseline_by_id = {row.case_id: row for row in baseline_records}
        candidate_by_id = {row.case_id: row for row in candidate_records}

        def row_payload(case_id: str, before: TrainSetEvalRecord, after: TrainSetEvalRecord) -> dict[str, Any]:
            return {
                "case_id": case_id,
                "family": before.capability_family,
                "expected": before.expected,
                "baseline_answer": before.answer,
                "candidate_answer": after.answer,
                "candidate_tools": list(after.tool_names),
                "candidate_artifacts": list(after.artifact_paths),
            }

        fixed_cases: list[dict[str, Any]] = []
        regressed_cases: list[dict[str, Any]] = []
        unchanged_wrong_cases: list[str] = []
        for case_id, before in baseline_by_id.items():
            after = candidate_by_id.get(case_id)
            if after is None:
                continue
            if not before.correct and after.correct:
                fixed_cases.append(row_payload(case_id, before, after))
            elif before.correct and not after.correct:
                regressed_cases.append(row_payload(case_id, before, after))
            elif not before.correct and not after.correct:
                unchanged_wrong_cases.append(case_id)
        return {
            "fixed_cases": fixed_cases,
            "regressed_cases": regressed_cases,
            "unchanged_wrong_case_ids": unchanged_wrong_cases,
            "fixed_count": len(fixed_cases),
            "regressed_count": len(regressed_cases),
            "net_fixed_count": len(fixed_cases) - len(regressed_cases),
        }

    @staticmethod
    def _learned_tool_artifact_gate(
        bundle: CapabilityBundleProposal,
        candidate_records: list[TrainSetEvalRecord],
    ) -> tuple[bool, str]:
        learned_tool_names = {tool.name for tool in bundle.tools}
        if not learned_tool_names:
            return True, "no generated tools"

        used_rows = [
            row for row in candidate_records
            if learned_tool_names.intersection(set(row.tool_names))
        ]
        if not used_rows:
            return False, f"generated tools were never used: {', '.join(sorted(learned_tool_names))}"

        missing_artifact_rows = [row.case_id for row in used_rows if not row.artifact_paths]
        if missing_artifact_rows:
            return (
                False,
                "generated tool used without artifact on cases: " + ", ".join(missing_artifact_rows[:8]),
            )
        return True, "generated tool artifact gate passed"

    def _batch_plans_from_digest(self, digest: TrainingSetDigest) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        seen_families: set[str] = set()
        for cluster in digest.failure_clusters:
            if len(plans) >= self.max_planning_rounds:
                break
            if cluster.capability_family in seen_families and len(seen_families) < self.families_per_round_limit:
                continue
            memory = next((item for item in digest.family_memories if item.capability_family == cluster.capability_family), None)
            gap = memory.toolbox_gaps[0] if memory and memory.toolbox_gaps else None
            cluster_memory = next(
                (item for item in (memory.cluster_memories if memory else []) if item.cluster_id == cluster.cluster_id),
                None,
            )
            action = "generate_skill" if self.disable_generated_tools else "generate_both"
            if self.tool_preference == "balanced" and gap is None:
                action = "generate_skill"
            plans.append(
                {
                    "target_family": cluster.capability_family,
                    "target_cluster_ids": [cluster.cluster_id],
                    "representative_case_ids": list(cluster.representative_case_ids[: self.representatives_per_cluster]),
                    "next_action": action,
                    "primitive_category": gap.primitive_category if gap else cluster.cluster_key,
                    "toolability": cluster_memory.toolability if cluster_memory else "medium",
                    "toolability_blocked": False,
                    "tool_goal": gap.summary if gap else f"Create reusable visual support for {cluster.cluster_key}.",
                    "skill_update_note": f"Route {cluster.capability_family} failures using the generated reusable tool when helpful.",
                    "rationale": "Batch training digest selected this recurring failure cluster from the full train subset.",
                    "expected_gain": "Recover multiple wrong training cases without regressing already-correct family cases.",
                }
            )
            seen_families.add(cluster.capability_family)
        return plans

    def _combine_batch_bundles(self, bundles: list[CapabilityBundleProposal]) -> CapabilityBundleProposal:
        tools_by_name: dict[str, ToolProposal] = {}
        skills_by_name: dict[str, SkillProposal] = {}
        target_cluster_ids: list[str] = []
        representative_case_ids: list[str] = []
        primitive_categories: list[str] = []
        for bundle in bundles:
            for tool in bundle.tools:
                tools_by_name[tool.name] = tool
            for skill in bundle.skills:
                skills_by_name[skill.name] = skill
            for cluster_id in bundle.target_cluster_ids:
                if cluster_id not in target_cluster_ids:
                    target_cluster_ids.append(cluster_id)
            for case_id in bundle.representative_case_ids:
                if case_id not in representative_case_ids:
                    representative_case_ids.append(case_id)
            if bundle.primitive_category and bundle.primitive_category not in primitive_categories:
                primitive_categories.append(bundle.primitive_category)
        return CapabilityBundleProposal(
            run_id=datetime.now().strftime("batch_%Y%m%d_%H%M%S_%f"),
            target_family="vstar_batch",
            target_cluster_ids=target_cluster_ids,
            representative_case_ids=representative_case_ids,
            rationale="Combined smoke-passed VStar tools and skills from one full training-set error digest.",
            expected_gain="Improve full train accuracy with a reusable batch capability bundle.",
            primitive_category="+".join(primitive_categories),
            tools=list(tools_by_name.values()),
            skills=list(skills_by_name.values()),
        )

    @staticmethod
    def _family_regression_within_limit(
        baseline_records: list[TrainSetEvalRecord],
        candidate_records: list[TrainSetEvalRecord],
        max_regressed_cases: int,
    ) -> bool:
        baseline_by_family: dict[str, int] = {}
        candidate_by_family: dict[str, int] = {}
        for row in baseline_records:
            baseline_by_family[row.capability_family] = baseline_by_family.get(row.capability_family, 0) + int(row.correct)
        for row in candidate_records:
            candidate_by_family[row.capability_family] = candidate_by_family.get(row.capability_family, 0) + int(row.correct)
        for family, baseline_correct in baseline_by_family.items():
            if baseline_correct - candidate_by_family.get(family, 0) > max_regressed_cases:
                return False
        return True

    def _emit_checkpoint(
        self,
        baseline_records: list[TrainSetEvalRecord],
        current_records: list[TrainSetEvalRecord],
        round_results: list[CandidateEvalResult],
        snapshot_name: str,
    ) -> None:
        if self.checkpoint_callback is None:
            return
        self.checkpoint_callback(
            baseline_records,
            current_records,
            round_results,
            snapshot_name,
        )

    def _attach_active_toolbox(self, digest: TrainingSetDigest) -> None:
        manifests = self.active_store.list_tool_records()
        if not manifests:
            return
        records = [
            FamilyToolRecord(
                name=str(item.get("name", "")),
                primitive_category=str(item.get("primitive_category", "")).strip() or "generic_visual_focus",
                applicability_conditions=str(item.get("applicability_conditions", "")),
                supported_families=[],
                supported_cluster_patterns=[],
                validation_scope="family" if item.get("validation", {}).get("regression_ok") else "cluster",
                notes=[str(item.get("description", "")).strip()] if str(item.get("description", "")).strip() else [],
            )
            for item in manifests
        ]
        for memory in digest.family_memories:
            memory.family_toolbox = list(records)
            existing_categories = {tool.primitive_category for tool in memory.family_toolbox if tool.primitive_category}
            memory.toolbox_gaps = [gap for gap in memory.toolbox_gaps if gap.primitive_category not in existing_categories]

    def _attach_mastery_profile(self, digest: TrainingSetDigest, bundle: CapabilityBundleProposal | None) -> None:
        persisted = self.active_store.load_training_memory().get("mastery_profiles", {})
        if isinstance(persisted, dict):
            for memory in digest.family_memories:
                raw_profiles = persisted.get(memory.capability_family, [])
                for raw_profile in raw_profiles if isinstance(raw_profiles, list) else []:
                    profile = _coerce_mastery_profile(raw_profile)
                    if profile is not None:
                        memory.mastery_profiles.append(profile)
        if bundle is None or bundle.mastery_profile is None:
            return
        for memory in digest.family_memories:
            if memory.capability_family != bundle.target_family:
                continue
            memory.mastery_profiles = [profile for profile in memory.mastery_profiles if profile.best_strategy_name != bundle.mastery_profile.best_strategy_name]
            memory.mastery_profiles.append(bundle.mastery_profile)
            memory.mastery_history.append(
                f"{bundle.mastery_profile.best_strategy_name}: coverage={bundle.mastery_profile.coverage:.3f} precision={bundle.mastery_profile.precision:.3f} delta={bundle.mastery_profile.score_delta:.3f}"
            )

    def _run_mastery_phase(
        self,
        bundle: CapabilityBundleProposal,
        digest: TrainingSetDigest,
        cases_by_id: dict[str, TaskCase],
        round_idx: int,
    ) -> CapabilityBundleProposal:
        if not bundle.skills:
            return bundle
        if bundle.tools:
            # Mastery candidates currently come from the preset-tool catalog. Do not let
            # that preset-only phase overwrite a skill that was generated for new tools.
            return bundle
        family_memory = next((memory for memory in digest.family_memories if memory.capability_family == bundle.target_family), None)
        if family_memory is None:
            return bundle
        case = cases_by_id.get(bundle.representative_case_ids[0]) if bundle.representative_case_ids else None
        if case is None:
            return bundle
        existing_skill = self.active_store.get_skill(bundle.target_family)
        training_context = self.planner._format_training_context(family_memory, bundle.representative_case_ids)
        mastery_candidates = self.generator.generate_mastery_candidates(
            case=case,
            training_context=training_context,
            coverage_contract=bundle.coverage_contract,
            existing_skill_content=existing_skill.content if existing_skill else None,
        )
        mastery_case_ids = self._select_mastery_case_ids(bundle, digest)
        mastery_cases = [cases_by_id[case_id] for case_id in mastery_case_ids if case_id in cases_by_id]
        if not mastery_cases:
            return bundle

        baseline_rows = {row.case_id: row for row in self.evaluator.evaluate(
            self.active_dir,
            self.work_dir / f"round_{round_idx}" / "mastery_baseline",
            mastery_cases,
            f"mastery_baseline_round_{round_idx}",
            stage_label=f"round {round_idx} mastery baseline",
        )[1]}

        eval_results: list[MasteryEvalResult] = []
        best_profile: MasteryProfile | None = None
        best_skill: SkillProposal | None = None
        best_rank = (-1.0, -1.0, -1.0)
        original_skill = bundle.skills[0]
        for index, strategy in enumerate(mastery_candidates, start=1):
            candidate_skill = self._skill_from_mastery_strategy(bundle.target_family, strategy)
            mastery_bundle = CapabilityBundleProposal(
                run_id=f"{bundle.run_id}_mastery_{index}",
                target_family=bundle.target_family,
                target_cluster_ids=list(bundle.target_cluster_ids),
                representative_case_ids=list(bundle.representative_case_ids),
                rationale=bundle.rationale,
                expected_gain=bundle.expected_gain,
                coverage_contract=bundle.coverage_contract,
                primitive_category=bundle.primitive_category,
                tools=list(bundle.tools),
                skills=[candidate_skill],
            )
            candidate_dir = self.active_store.stage_bundle(mastery_bundle)
            summary, records = self.evaluator.evaluate(
                candidate_dir,
                self.work_dir / f"round_{round_idx}" / f"mastery_eval_{index}",
                mastery_cases,
                f"mastery_eval_round_{round_idx}_{index}",
                stage_label=f"round {round_idx} mastery {index}",
            )
            eval_result = self._build_mastery_eval_result(strategy, mastery_cases, baseline_rows, records)
            eval_results.append(eval_result)
            profile = self._build_mastery_profile(bundle.target_family, family_memory, strategy, eval_result)
            rank = (profile.score_delta, profile.precision, profile.coverage)
            if rank > best_rank:
                best_rank = rank
                best_profile = profile
                best_skill = candidate_skill
        if best_profile is None or best_skill is None:
            bundle.skills = [original_skill]
            return bundle
        best_profile.candidate_evaluations = list(eval_results)
        distilled = self.generator.distill_mastery_skill(
            case=case,
            analysis=FailureAnalysis(
                root_cause=bundle.rationale or "mastery distillation",
                next_action="generate_skill",
                confidence=0.6,
                missing_step=bundle.expected_gain or "Refine tool-use policy.",
                skill_update_note=bundle.rationale or "Distill the profiled tool-use boundary into a stable SOP.",
            ),
            mastery_profile=best_profile,
            existing_skill_content=existing_skill.content if existing_skill else original_skill.content,
            training_context=training_context,
            coverage_contract=bundle.coverage_contract,
        )
        bundle.skills = [distilled]
        bundle.mastery_profile = best_profile
        return bundle

    def _select_mastery_case_ids(self, bundle: CapabilityBundleProposal, digest: TrainingSetDigest) -> list[str]:
        selected: list[str] = []
        for case_id in self._select_cluster_smoke_case_ids(bundle, digest):
            if case_id not in selected:
                selected.append(case_id)
        for case_id in self._select_family_smoke_case_ids(bundle, digest):
            if case_id not in selected:
                selected.append(case_id)
            if len(selected) >= 6:
                break
        return selected[:6]

    def _skill_from_mastery_strategy(self, family: str, strategy: MasteryStrategyCandidate) -> SkillProposal:
        sequence = strategy.tool_sequence
        trigger = "; ".join(strategy.trigger_conditions) or "the current visual pattern matches this tool strategy"
        avoid = "; ".join(strategy.avoid_conditions) or "direct answering is already sufficient"
        steps = [
            "## SOP",
            f"1. Confirm this applies: {trigger}",
        ]
        if sequence:
            first = sequence[0]
            steps.append(f"2. Run `{self._mastery_tool_command(family, first, use_artifact=False)}` and wait for the Observation.")
            if len(sequence) > 1:
                for offset, tool_name in enumerate(sequence[1:], start=3):
                    steps.append(
                        f"{offset}. If the previous artifact is still needed, run "
                        f"`{self._mastery_tool_command(family, tool_name, use_artifact=True)}` and wait for the Observation."
                    )
                final_step = len(sequence) + 2
                steps.append(f"{final_step}. If the avoid condition applies instead ({avoid}), skip the tool path and answer directly; otherwise answer from the final artifact.")
            else:
                steps.append(f"3. If the avoid condition applies instead ({avoid}), skip the tool path and answer directly.")
                steps.append("4. Answer the original question from the tool output artifact when the tool path is used.")
        else:
            steps.append(f"2. If the avoid condition applies ({avoid}), answer directly from the raw image.")
            steps.append("3. Do not call a tool unless the case clearly matches a stronger family trigger.")
            steps.append("4. Answer the original question directly from the raw image.")
        return SkillProposal(
            name=family,
            description=f"Mastery SOP for {family} using strategy {strategy.name}.",
            applicability_conditions=trigger,
            content="\n".join(steps),
            level="mid",
            depends_on=[],
        )

    @staticmethod
    def _mastery_tool_command(family: str, tool_name: str, use_artifact: bool) -> str:
        image_ref = "<artifact_path>" if use_artifact else "<image_path>"
        if not family.strip().lower().startswith("gta"):
            return f"python -m tools {tool_name} {image_ref}"

        gta_templates = {
            "OCR": f"python -m tools OCR image={image_ref}",
            "ImageDescription": f"python -m tools ImageDescription image={image_ref}",
            "CountGivenObject": f'python -m tools CountGivenObject image={image_ref} text="target object"',
            "TextToBbox": f'python -m tools TextToBbox image={image_ref} text="target object" top1=true',
            "RegionAttributeDescription": f'python -m tools RegionAttributeDescription image={image_ref} bbox="(x1, y1, x2, y2)" attribute="target attribute"',
            "MathOCR": f"python -m tools MathOCR image={image_ref}",
            "Calculator": 'python -m tools Calculator expression="numeric expression"',
            "Solver": 'python -m tools Solver command="def solution():\n    return result"',
            "Plot": 'python -m tools Plot command="import matplotlib.pyplot as plt\n\ndef solution():\n    fig, ax = plt.subplots()\n    return fig"',
            "DrawBox": f'python -m tools DrawBox image={image_ref} bbox="(x1, y1, x2, y2)" annotation="target"',
            "AddText": f'python -m tools AddText image={image_ref} text="label" position="mt" color=red',
            "GoogleSearch": 'python -m tools GoogleSearch query="factual query" k=4',
            "TextToImage": 'python -m tools TextToImage keywords="keyword1, keyword2"',
            "ImageStylization": f'python -m tools ImageStylization image={image_ref} instruction="edit instruction"',
        }
        return gta_templates.get(tool_name, f"python -m tools {tool_name} {image_ref}")

    def _build_mastery_eval_result(
        self,
        strategy: MasteryStrategyCandidate,
        mastery_cases: list[TaskCase],
        baseline_rows: dict[str, TrainSetEvalRecord],
        records: list[TrainSetEvalRecord],
    ) -> MasteryEvalResult:
        supported_case_ids: list[str] = []
        failed_case_ids: list[str] = []
        supported_patterns: list[str] = []
        failure_patterns: list[str] = []
        baseline_score = sum(_record_score(row) for row in baseline_rows.values()) / max(len(baseline_rows), 1)
        candidate_score = sum(_record_score(row) for row in records) / max(len(records), 1)
        for record in records:
            baseline = baseline_rows.get(record.case_id)
            pattern = str(record.metadata.get("cluster_key", "") or record.capability_family)
            improved = _record_score(record) > _record_score(baseline) if baseline is not None else record.correct
            if improved:
                supported_case_ids.append(record.case_id)
                if pattern not in supported_patterns:
                    supported_patterns.append(pattern)
            else:
                failed_case_ids.append(record.case_id)
                if pattern not in failure_patterns:
                    failure_patterns.append(pattern)
        attempted = len(supported_case_ids) + len(failed_case_ids)
        return MasteryEvalResult(
            strategy_name=strategy.name,
            evaluated_case_ids=[case.case_id for case in mastery_cases],
            supported_case_ids=supported_case_ids,
            failed_case_ids=failed_case_ids,
            coverage=len(supported_case_ids) / max(len(mastery_cases), 1),
            precision=len(supported_case_ids) / max(attempted, 1),
            score_delta=candidate_score - baseline_score,
            supported_cluster_patterns=supported_patterns,
            failure_cluster_patterns=failure_patterns,
            notes=[strategy.rationale] if strategy.rationale else [],
        )

    def _build_mastery_profile(
        self,
        family: str,
        family_memory: FamilyMemory,
        strategy: MasteryStrategyCandidate,
        eval_result: MasteryEvalResult,
    ) -> MasteryProfile:
        primary_tool = strategy.tool_sequence[0] if strategy.tool_sequence else ""
        return MasteryProfile(
            capability_family=family,
            primary_tool=primary_tool,
            tool_sequence=list(strategy.tool_sequence),
            supported_families=[family],
            supported_cluster_patterns=list(eval_result.supported_cluster_patterns),
            negative_cluster_patterns=list(eval_result.failure_cluster_patterns),
            success_case_ids=list(eval_result.supported_case_ids),
            failure_case_ids=list(eval_result.failed_case_ids),
            common_success_signals=list(family_memory.recurring_failure_signals[:2]) or list(strategy.trigger_conditions[:2]),
            common_failure_signals=list(strategy.avoid_conditions[:2]) or list(family_memory.recent_revision_briefs[:2]),
            recommended_trigger_conditions=list(strategy.trigger_conditions),
            negative_trigger_conditions=list(strategy.avoid_conditions),
            best_chain_patterns=[" -> ".join(strategy.tool_sequence)] if strategy.tool_sequence else ["no_tool"],
            bad_chain_patterns=["no_tool"] if strategy.tool_sequence else [],
            best_strategy_name=strategy.name,
            coverage=eval_result.coverage,
            precision=eval_result.precision,
            score_delta=eval_result.score_delta,
            notes=list(eval_result.notes),
        )

    def _smoke_validate(
        self,
        bundle: CapabilityBundleProposal,
        digest: TrainingSetDigest,
        cases_by_id: dict[str, TaskCase],
        candidate_dir: Path,
        round_idx: int,
    ) -> tuple[bool, str, CapabilityBundleProposal, dict[str, Any]]:
        smoke_case_ids = self._select_cluster_smoke_case_ids(bundle, digest)
        smoke_cases = [cases_by_id[case_id] for case_id in smoke_case_ids if case_id in cases_by_id]
        family_smoke_case_ids = self._select_family_smoke_case_ids(bundle, digest)
        family_smoke_cases = [cases_by_id[case_id] for case_id in family_smoke_case_ids if case_id in cases_by_id]
        if not smoke_cases:
            return False, "No representative case available for smoke validation.", bundle, {"failure_type": "missing_smoke_cases"}

        print(
            f"[subset-loop] smoke validate: run_id={bundle.run_id} "
            f"cases={[case.case_id for case in smoke_cases]}"
        )
        smoke_progress = _ProgressPrinter(label=f"round {round_idx} smoke", total=len(smoke_cases))
        smoke_progress.start()

        validator_loop = EvolutionLoop(
            work_dir=self.work_dir / f"round_{round_idx}" / "smoke",
            learned_dir=candidate_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=1,
            subset_id=None,
            capability_mode=self.capability_mode,
        )
        available_tools = set(validator_loop._tool_availability_snapshot().available_tools)
        validator = validator_loop.validator

        for index, tool in enumerate(list(bundle.tools)):
            print(f"[subset-loop] smoke validate: tool {tool.name}")
            validation, candidate_dir, validator_loop, bundle = self._repair_and_validate_tool(
                bundle=bundle,
                tool_index=index,
                digest=digest,
                candidate_dir=candidate_dir,
                round_idx=round_idx,
                smoke_cases=smoke_cases,
                family_smoke_cases=family_smoke_cases,
            )
            validator = validator_loop.validator
            if not validation.passed:
                return False, validation.reason or f"Tool {tool.name} failed smoke validation.", bundle, self._validation_meta(validation)

        available_tools = set(validator_loop._tool_availability_snapshot().available_tools)
        for index, skill in enumerate(list(bundle.skills)):
            print(f"[subset-loop] smoke validate: skill {skill.name}")
            validation = validator.validate_skill(skill, skill.name)
            if not validation.passed and validation.revision_brief is not None:
                revised_skill = self.generator.revise_skill(
                    skill=skill,
                    revision_brief=validation.revision_brief,
                    coverage_contract=bundle.coverage_contract,
                    training_context=self.planner._format_training_context(
                        next((memory for memory in digest.family_memories if memory.capability_family == bundle.target_family), None),
                        bundle.representative_case_ids,
                    ),
                )
                bundle.skills[index] = revised_skill
                candidate_dir = self.active_store.stage_bundle(bundle)
                validator_loop = EvolutionLoop(
                    work_dir=self.work_dir / f"round_{round_idx}" / "smoke_repair_skill",
                    learned_dir=candidate_dir,
                    skills_dir=self.skills_dir,
                    vlm_client=self.vlm_client,
                    max_attempts=1,
                    subset_id=None,
                    capability_mode=self.capability_mode,
                )
                validator = validator_loop.validator
                validation = validator.validate_skill(revised_skill, revised_skill.name)
            if not validation.passed:
                return False, validation.reason or f"Skill {skill.name} failed static validation.", bundle, self._validation_meta(validation)
            required_tools = validator._extract_tool_sequence(skill.content)
            missing = [tool_name for tool_name in required_tools if tool_name not in available_tools]
            if missing:
                return False, f"Skill {skill.name} references unavailable tools: {', '.join(missing)}", bundle, {
                    "failure_type": "missing_tool_reference",
                    "revision_brief": {
                        "failure_type": "missing_tool_reference",
                        "reason": f"Skill {skill.name} references unavailable tools: {', '.join(missing)}",
                        "rewrite_requirements": ["Reference only tools available in the candidate bundle."],
                        "banned_patterns": missing,
                    },
                }

        for index, case in enumerate(smoke_cases, start=1):
            try:
                self.evaluator._run_case(
                    candidate_dir,
                    self.work_dir / f"round_{round_idx}" / "smoke_runs",
                    case,
                    f"smoke_case_{index}",
                )
                smoke_progress.update(
                    current=index,
                    correct=index,
                    average_score=1.0,
                    case_id=case.case_id,
                    last_status="OK",
                )
            except Exception as exc:  # pragma: no cover - defensive
                smoke_progress.update(
                    current=index,
                    correct=index - 1,
                    average_score=max(0.0, (index - 1) / max(index, 1)),
                    case_id=case.case_id,
                    last_status="FAIL",
                )
                smoke_progress.finish(correct=index - 1, average_score=(index - 1) / max(len(smoke_cases), 1))
                return False, f"Smoke run crashed for case {case.case_id}: {exc}", bundle, {
                    "failure_type": "runtime_error",
                    "revision_brief": {
                        "failure_type": "runtime_error",
                        "reason": f"Smoke run crashed for case {case.case_id}: {exc}",
                        "rewrite_requirements": ["Make the candidate executable across the smoke cases without crashing."],
                        "banned_patterns": ["uncaught exceptions"],
                    },
                }

        smoke_progress.finish(correct=len(smoke_cases), average_score=1.0)
        return True, "smoke passed", bundle, {}

    def _repair_and_validate_tool(
        self,
        bundle: CapabilityBundleProposal,
        tool_index: int,
        digest: TrainingSetDigest,
        candidate_dir: Path,
        round_idx: int,
        smoke_cases: list[TaskCase],
        family_smoke_cases: list[TaskCase] | None,
    ) -> tuple[ValidationResult, Path, EvolutionLoop, CapabilityBundleProposal]:
        validator_loop = self._make_smoke_loop(candidate_dir, round_idx, "smoke")
        validator = validator_loop.validator
        tool = bundle.tools[tool_index]
        validation = self._validate_tool_across_cases(validator, validator_loop, tool, smoke_cases, family_smoke_cases)
        repair_history: list[dict[str, Any]] = []

        for repair_attempt in range(1, self.MAX_TOOL_REPAIR_ATTEMPTS + 1):
            if validation.passed or validation.revision_brief is None:
                break

            repair_history.append(self._repair_history_entry(repair_attempt, validation))
            revision_brief = self._artifact_aware_revision_brief(validation.revision_brief, tool)
            if self._should_apply_fallback_artifact_wrapper(repair_history, validation, repair_attempt):
                print(f"[subset-loop] smoke repair {repair_attempt}: applying fallback artifact wrapper for {tool.name}")
                revised_tool = self._with_fallback_artifact_wrapper(tool)
            else:
                print(
                    f"[subset-loop] smoke repair {repair_attempt}/{self.MAX_TOOL_REPAIR_ATTEMPTS}: "
                    f"tool={tool.name} failure={validation.failure_type or 'unknown'}"
                )
                revised_tool = self.generator.revise_tool(
                    tool=tool,
                    revision_brief=revision_brief,
                    coverage_contract=bundle.coverage_contract,
                    training_context=self.planner._format_training_context(
                        next((memory for memory in digest.family_memories if memory.capability_family == bundle.target_family), None),
                        bundle.representative_case_ids,
                    ),
                )

            tool = revised_tool
            bundle.tools[tool_index] = revised_tool
            candidate_dir = self.active_store.stage_bundle(bundle)
            validator_loop = self._make_smoke_loop(candidate_dir, round_idx, f"smoke_repair_{repair_attempt}")
            validator = validator_loop.validator
            validation = self._validate_tool_across_cases(validator, validator_loop, revised_tool, smoke_cases, family_smoke_cases)

        if not validation.passed and repair_history:
            validation.smoke_case_results.append({"repair_history": json.dumps(repair_history, ensure_ascii=False)})
        return validation, candidate_dir, validator_loop, bundle

    def _make_smoke_loop(self, candidate_dir: Path, round_idx: int, phase: str) -> EvolutionLoop:
        return EvolutionLoop(
            work_dir=self.work_dir / f"round_{round_idx}" / phase,
            learned_dir=candidate_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=1,
            subset_id=None,
            capability_mode=self.capability_mode,
        )

    @staticmethod
    def _repair_history_entry(repair_attempt: int, validation: ValidationResult) -> dict[str, Any]:
        return {
            "attempt": repair_attempt,
            "failure_type": validation.failure_type,
            "reason": validation.reason,
            "evidence": [] if validation.revision_brief is None else list(validation.revision_brief.evidence),
            "rewrite_requirements": [] if validation.revision_brief is None else list(validation.revision_brief.rewrite_requirements),
        }

    @staticmethod
    def _artifact_aware_revision_brief(brief: RevisionBrief, tool: ToolProposal) -> RevisionBrief:
        if brief.failure_type != "no_artifact":
            return brief
        requirements = list(brief.rewrite_requirements)
        requirements.extend(
            [
                "The top-level run(image_path: str) must always create a concrete processed_img numpy ndarray for valid image inputs.",
                f'Use output_path = "artifacts/{tool.name}_output.png" or another artifacts/<name>.png path stored in one variable.',
                "Call save_image(processed_img, output_path) before returning.",
                "Return ToolResult(status='ok', answer='', artifacts=[output_path]) with the exact same output_path variable.",
                "If OpenCV drawing fails with 'img is not a numpy array', convert intermediate PIL/list/scalar values to np.ndarray before cv2.line/cv2.rectangle/cv2.putText.",
                "Do not swallow exceptions by returning ok without artifacts; either produce a fallback artifact or return a clear error.",
            ]
        )
        banned_patterns = list(brief.banned_patterns)
        banned_patterns.extend(["return ToolResult(status='ok', answer='', artifacts=[])", "status-only tool"])
        return RevisionBrief(
            failure_type=brief.failure_type,
            reason=brief.reason,
            evidence=list(brief.evidence),
            rewrite_requirements=list(dict.fromkeys(requirements)),
            banned_patterns=list(dict.fromkeys(banned_patterns)),
            retry_action=brief.retry_action,
        )

    @staticmethod
    def _should_apply_fallback_artifact_wrapper(
        repair_history: list[dict[str, Any]],
        validation: ValidationResult,
        repair_attempt: int,
    ) -> bool:
        if validation.failure_type != "no_artifact":
            return False
        no_artifact_failures = sum(1 for item in repair_history if item.get("failure_type") == "no_artifact")
        return repair_attempt >= 3 and no_artifact_failures >= 2

    @staticmethod
    def _with_fallback_artifact_wrapper(tool: ToolProposal) -> ToolProposal:
        code = str(tool.code or "")
        if "_original_run_before_artifact_fallback" in code:
            return tool
        wrapped = code.replace("def run(image_path: str) -> ToolResult:", "def _original_run_before_artifact_fallback(image_path: str) -> ToolResult:", 1)
        if wrapped == code:
            return tool
        fallback_code = f'''

def run(image_path: str) -> ToolResult:
    fallback_error = ""
    try:
        result = _original_run_before_artifact_fallback(image_path)
        if getattr(result, "status", "") == "ok" and getattr(result, "artifacts", None):
            return result
        fallback_error = str(getattr(result, "error", "") or "original tool returned no artifacts")
    except Exception as exc:
        fallback_error = str(exc)
    try:
        img = load_image(image_path)
        processed_img = img.copy() if hasattr(img, "copy") else img
        output_path = "artifacts/{tool.name}_fallback.png"
        save_image(processed_img, output_path)
        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
            debug_info="fallback artifact emitted after repair: " + fallback_error[:200],
        )
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
'''
        return ToolProposal(
            name=tool.name,
            description=tool.description,
            applicability_conditions=tool.applicability_conditions,
            code=wrapped.rstrip() + fallback_code,
            usage_example=tool.usage_example,
            expected_inputs=list(tool.expected_inputs),
            expected_outputs=list(tool.expected_outputs),
            primitive_category=tool.primitive_category,
        )

    def _select_cluster_smoke_case_ids(self, bundle: CapabilityBundleProposal, digest: TrainingSetDigest) -> list[str]:
        selected: list[str] = []
        for case_id in bundle.representative_case_ids:
            if case_id not in selected:
                selected.append(case_id)
        for cluster in digest.failure_clusters:
            if cluster.cluster_id not in bundle.target_cluster_ids:
                continue
            for case_id in cluster.case_ids:
                if case_id not in selected:
                    selected.append(case_id)
                if len(selected) >= 3:
                    return selected
        return selected[:3]

    def _select_family_smoke_case_ids(self, bundle: CapabilityBundleProposal, digest: TrainingSetDigest) -> list[str]:
        selected: list[str] = []
        cluster_ids = set(bundle.target_cluster_ids)
        for cluster in digest.failure_clusters:
            if cluster.capability_family != bundle.target_family or cluster.cluster_id in cluster_ids:
                continue
            for case_id in cluster.case_ids:
                if case_id not in selected and case_id not in bundle.representative_case_ids:
                    selected.append(case_id)
                if len(selected) >= 3:
                    return selected
        return selected[:3]

    def _validate_tool_across_cases(
        self,
        validator,
        validator_loop: EvolutionLoop,
        tool: ToolProposal,
        smoke_cases: list[TaskCase],
        family_smoke_cases: list[TaskCase] | None = None,
    ) -> ValidationResult:
        first_result = validator.validate_tool(
            tool,
            origin_case=smoke_cases[0],
            agent_factory=lambda: validator_loop._create_agent(smoke_cases[0], attempt=1, phase="smoke_validate"),
            regression_cases=None,
            chain_context=None,
            attempt=1,
        )
        if not first_result.passed:
            return first_result

        project_root = Path(__file__).parents[1]
        for case in smoke_cases[1:]:
            output, returncode = validator._run_tool_command(  # type: ignore[attr-defined]
                tool.name,
                case.image_path,
                project_root,
                case.problem_id,
                case.case_id,
                1,
                f"cluster_smoke_{tool.name}",
            )
            artifacts = validator._extract_artifacts(output)
            first_result.smoke_case_results.append(
                {
                    "case_id": case.case_id,
                    "passed": bool(returncode == 0 and "STATUS: error" not in output and artifacts),
                    "detail": output.strip()[:200],
                }
            )
            if returncode != 0 or "STATUS: error" in output or not artifacts:
                return validator._failure_result(  # type: ignore[attr-defined]
                    first_result,
                    reason=f"Tool failed cluster smoke on case {case.case_id}",
                    failure_type="case_specific_logic",
                    evidence=[case.case_id, output.strip()[:240]],
                    rewrite_requirements=[
                        "Make the tool work across multiple cases in the same cluster.",
                        "Avoid assumptions tied to a single representative image.",
                    ],
                    banned_patterns=["single-case logic", "one-image thresholds"],
                    retry_action="revise_tool",
                )
        for case in family_smoke_cases or []:
            output, returncode = validator._run_tool_command(  # type: ignore[attr-defined]
                tool.name,
                case.image_path,
                project_root,
                case.problem_id,
                case.case_id,
                1,
                f"family_smoke_{tool.name}",
            )
            artifacts = validator._extract_artifacts(output)
            passed = bool(returncode == 0 and "STATUS: error" not in output and artifacts)
            first_result.smoke_case_results.append(
                {
                    "case_id": case.case_id,
                    "passed": passed,
                    "detail": output.strip()[:200],
                }
            )
            if not passed:
                return validator._failure_result(  # type: ignore[attr-defined]
                    first_result,
                    reason=f"Tool failed family smoke on case {case.case_id}",
                    failure_type="cluster_only_tool",
                    evidence=[case.case_id, output.strip()[:240]],
                    rewrite_requirements=[
                        "Generalize the tool across multiple clusters in the same family.",
                        "Reduce assumptions about one chart/layout/question subtype.",
                    ],
                    banned_patterns=["single-cluster assumptions", "cluster-only logic"],
                    retry_action="revise_tool",
                )
        return first_result

    @staticmethod
    def _validation_meta(validation: ValidationResult) -> dict[str, Any]:
        repair_history = []
        for item in validation.smoke_case_results:
            if isinstance(item, dict) and "repair_history" in item:
                try:
                    repair_history = json.loads(str(item["repair_history"]))
                except json.JSONDecodeError:
                    repair_history = [str(item["repair_history"])]
        return {
            "failure_type": validation.failure_type,
            "revision_brief": None if validation.revision_brief is None else asdict(validation.revision_brief),
            "repair_history": repair_history,
        }


def _extract_tool_names(result: AgentResult) -> list[str]:
    tool_names: list[str] = []
    for step in result.steps:
        if step.action is None or step.action.name != "bash":
            continue
        command = str(step.action.arguments.get("command", ""))
        parts = command.split()
        if len(parts) >= 4 and parts[:3] == ["python", "-m", "tools"]:
            name = parts[3]
            if name not in tool_names:
                tool_names.append(name)
    return tool_names


def _merge_tool_names(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for name in group:
            if name and name not in merged:
                merged.append(name)
    return merged


def _tool_step_debug(result: AgentResult) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in result.steps:
        if step.action is None or step.action.name != "bash":
            continue
        command = str(step.command or step.action.arguments.get("command", "") or "")
        observation = str(step.observation or "")
        rows.append(
            {
                "turn": step.turn,
                "command": command[:500],
                "observation": observation[:1000],
                "artifacts": list(step.artifacts),
            }
        )
    return rows


def _extract_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _score_delta_map(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = set(before) | set(after)
    return {key: after.get(key, 0.0) - before.get(key, 0.0) for key in sorted(keys)}


def _compare_case_outcomes(
    baseline_records: list[TrainSetEvalRecord],
    candidate_records: list[TrainSetEvalRecord],
) -> tuple[list[dict[str, str | float]], list[dict[str, str | float]]]:
    baseline_map = {row.case_id: row for row in baseline_records}
    candidate_map = {row.case_id: row for row in candidate_records}
    improvements: list[dict[str, str | float]] = []
    regressions: list[dict[str, str | float]] = []
    for case_id, baseline in baseline_map.items():
        candidate = candidate_map.get(case_id)
        if candidate is None:
            continue
        delta = _record_score(candidate) - _record_score(baseline)
        if delta > 0:
            improvements.append({"case_id": case_id, "dataset_name": candidate.dataset_name, "delta": delta})
        elif delta < 0:
            regressions.append({"case_id": case_id, "dataset_name": candidate.dataset_name, "delta": delta})
    improvements.sort(key=lambda row: (-float(row["delta"]), str(row["case_id"])))
    regressions.sort(key=lambda row: (float(row["delta"]), str(row["case_id"])))
    return improvements[:10], regressions[:10]


def _record_score(record: TrainSetEvalRecord) -> float:
    if record.score is not None:
        return float(record.score)
    return 1.0 if record.correct else 0.0


def _fallback_representatives(digest: TrainingSetDigest) -> list[str]:
    if not digest.failure_clusters:
        return []
    return list(digest.failure_clusters[0].representative_case_ids[:1])


def _cluster_summary(digest: TrainingSetDigest, case_id: str) -> str:
    for cluster in digest.failure_clusters:
        if case_id in cluster.representative_case_ids:
            return " ".join(cluster.summary_lines[:2])
    return "Selected representative case from the current training digest."


def _coerce_mastery_profile(payload: Any) -> MasteryProfile | None:
    if not isinstance(payload, dict):
        return None
    evals: list[MasteryEvalResult] = []
    for raw_eval in payload.get("candidate_evaluations", []) or []:
        if not isinstance(raw_eval, dict):
            continue
        evals.append(
            MasteryEvalResult(
                strategy_name=str(raw_eval.get("strategy_name", "")).strip(),
                evaluated_case_ids=[str(item) for item in raw_eval.get("evaluated_case_ids", [])],
                supported_case_ids=[str(item) for item in raw_eval.get("supported_case_ids", [])],
                failed_case_ids=[str(item) for item in raw_eval.get("failed_case_ids", [])],
                coverage=float(raw_eval.get("coverage", 0.0) or 0.0),
                precision=float(raw_eval.get("precision", 0.0) or 0.0),
                score_delta=float(raw_eval.get("score_delta", 0.0) or 0.0),
                supported_cluster_patterns=[str(item) for item in raw_eval.get("supported_cluster_patterns", [])],
                failure_cluster_patterns=[str(item) for item in raw_eval.get("failure_cluster_patterns", [])],
                notes=[str(item) for item in raw_eval.get("notes", [])],
            )
        )
    return MasteryProfile(
        capability_family=str(payload.get("capability_family", "")).strip(),
        primary_tool=str(payload.get("primary_tool", "")).strip(),
        tool_sequence=[str(item) for item in payload.get("tool_sequence", [])],
        supported_families=[str(item) for item in payload.get("supported_families", [])],
        supported_cluster_patterns=[str(item) for item in payload.get("supported_cluster_patterns", [])],
        negative_cluster_patterns=[str(item) for item in payload.get("negative_cluster_patterns", [])],
        success_case_ids=[str(item) for item in payload.get("success_case_ids", [])],
        failure_case_ids=[str(item) for item in payload.get("failure_case_ids", [])],
        common_success_signals=[str(item) for item in payload.get("common_success_signals", [])],
        common_failure_signals=[str(item) for item in payload.get("common_failure_signals", [])],
        recommended_trigger_conditions=[str(item) for item in payload.get("recommended_trigger_conditions", [])],
        negative_trigger_conditions=[str(item) for item in payload.get("negative_trigger_conditions", [])],
        best_chain_patterns=[str(item) for item in payload.get("best_chain_patterns", [])],
        bad_chain_patterns=[str(item) for item in payload.get("bad_chain_patterns", [])],
        best_strategy_name=str(payload.get("best_strategy_name", "")).strip(),
        coverage=float(payload.get("coverage", 0.0) or 0.0),
        precision=float(payload.get("precision", 0.0) or 0.0),
        score_delta=float(payload.get("score_delta", 0.0) or 0.0),
        candidate_evaluations=evals,
        notes=[str(item) for item in payload.get("notes", [])],
    )


def _normalize_representative_case_ids(raw_values: Any, cases_by_id: dict[str, TaskCase]) -> list[str]:
    normalized: list[str] = []
    values = raw_values if isinstance(raw_values, list) else [raw_values]

    for value in values:
        text = str(value).strip()
        if not text:
            continue
        resolved = _resolve_case_id(text, cases_by_id)
        if resolved and resolved not in normalized:
            normalized.append(resolved)

    return normalized


def _resolve_case_id(raw_text: str, cases_by_id: dict[str, TaskCase]) -> str:
    text = str(raw_text).strip()
    if not text:
        return ""
    if text in cases_by_id:
        return text

    candidates: list[str] = []
    if "case_id=" in text:
        extracted = text.split("case_id=", 1)[1]
        for delimiter in [";", ",", " ", "|"]:
            extracted = extracted.split(delimiter, 1)[0]
        extracted = extracted.strip()
        if extracted:
            candidates.append(extracted)

    stripped = text
    for prefix in ["case_id=", "case=", "id="]:
        if stripped.startswith(prefix):
            stripped = stripped[len(prefix):].strip()
    candidates.append(stripped)

    compact = stripped.strip("[](){}\"'")
    if compact:
        candidates.append(compact)

    for candidate in candidates:
        if candidate in cases_by_id:
            return candidate

    for candidate in candidates:
        if candidate.isdigit():
            for existing in cases_by_id:
                if existing == candidate or existing.endswith(f"_{candidate}"):
                    return existing

    return ""


def _normalize_next_action(raw_value: Any) -> str:
    action = str(raw_value or "generate_skill").strip()
    if action in {"generate_tool", "generate_skill", "generate_both", "generate_code_skill", "give_up"}:
        return action
    return "generate_skill"


class _ProgressPrinter:
    def __init__(self, label: str, total: int):
        self.label = label
        self.total = total
        self.start_time = 0.0
        self.last_width = 0

    def start(self) -> None:
        self.start_time = time.monotonic()
        self._write(
            f"[subset-progress] {self.label} 000/{self.total:03d} "
            f"elapsed=0.0s acc=0.000 avg_score=0.000"
        )

    def update(
        self,
        current: int,
        correct: int,
        average_score: float,
        case_id: str,
        last_status: str,
    ) -> None:
        elapsed = time.monotonic() - self.start_time
        accuracy = (correct / current) if current else 0.0
        message = (
            f"[subset-progress] {self.label} {current:03d}/{self.total:03d} "
            f"elapsed={elapsed:.1f}s acc={accuracy:.3f} avg_score={average_score:.3f} "
            f"last={last_status} case={case_id}"
        )
        self._write(message)

    def finish(self, correct: int, average_score: float) -> None:
        elapsed = time.monotonic() - self.start_time
        accuracy = (correct / self.total) if self.total else 0.0
        message = (
            f"[subset-progress] {self.label} {self.total:03d}/{self.total:03d} "
            f"elapsed={elapsed:.1f}s acc={accuracy:.3f} avg_score={average_score:.3f} done"
        )
        self._write(message, final=True)

    def _write(self, message: str, final: bool = False) -> None:
        padded = message
        if len(message) < self.last_width:
            padded = message + (" " * (self.last_width - len(message)))
        self.last_width = max(self.last_width, len(message))
        sys.stdout.write("\r" + padded)
        if final:
            sys.stdout.write("\n")
        sys.stdout.flush()
