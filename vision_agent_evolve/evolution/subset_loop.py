"""Subset-level evolution loop with active/candidate capability gating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from core.types import AgentResult, TaskCase
from core.vlm_client import ModelSettings, VLMClient
from evolution.benchmark_adapters import BenchmarkAdapter, get_benchmark_adapter
from evolution.loop import EvolutionLoop
from evolution.roles import Generator
from evolution.store import CapabilityStore
from evolution.types import (
    CandidateEvalResult,
    CapabilityBundleProposal,
    FailureAnalysis,
    FailureCluster,
    SkillProposal,
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
    ):
        self.adapters = adapters
        self.skills_dir = skills_dir
        self.vlm_client = vlm_client
        self.capability_mode = capability_mode

    def evaluate(
        self,
        capability_dir: Path,
        work_dir: Path,
        cases: list[TaskCase],
        phase_prefix: str,
        stage_label: str = "",
    ) -> tuple[TrainSetEvalSummary, list[TrainSetEvalRecord]]:
        records: list[TrainSetEvalRecord] = []
        if stage_label:
            print(f"[subset-eval] {stage_label}: starting {len(cases)} cases")
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
                },
            )
            records.append(record)
            label = stage_label or phase_prefix
            print(
                f"[subset-eval] {label} [{index:03d}/{len(cases):03d}] "
                f"{'OK' if correct else 'FAIL'} case={case.case_id} score={score:.3f}"
            )

        summary = self._summarize(records)
        if stage_label:
            print(
                f"[subset-eval] {stage_label}: done "
                f"score={summary.primary_score:.4f} correct={summary.correct_cases}/{summary.total_cases}"
            )
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
        for record in baseline_records:
            if record.correct:
                continue
            cluster_key = str(record.metadata.get("cluster_key", "")).strip() or record.capability_family
            cluster_map.setdefault(cluster_key, []).append(record)

        failure_clusters: list[FailureCluster] = []
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
            failure_clusters.append(
                FailureCluster(
                    cluster_id=f"cluster_{len(failure_clusters) + 1}",
                    dataset_name=first.dataset_name,
                    capability_family=first.capability_family,
                    cluster_key=cluster_key,
                    total_cases=len(rows),
                    representative_case_ids=[row.case_id for row in reps],
                    summary_lines=summary_lines,
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

        digest = TrainingSetDigest(
            baseline_summary=baseline_summary,
            failure_clusters=failure_clusters,
            representative_cases=representative_cases,
            recent_rejected_plans=recent_rejected_plans,
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
        )
        skill = loop.store.get_skill(case.capability_family())
        capability_snapshot = loop._tool_availability_snapshot()
        skill_content = loop._usable_skill_content(skill, capability_snapshot) if skill else None
        chain_context = loop.validator.build_chain_context(case, skill_content, attempt=1)
        agent = loop._create_agent(case, attempt=1, phase=phase)
        result = agent.run(
            case.prompt,
            case.image_path,
            initial_observations=loop._chain_observations_for_agent(chain_context),
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


class SubsetPlanner:
    """Planner that proposes one candidate capability bundle from a digest."""

    def __init__(
        self,
        client: VLMClient,
        generator: Generator,
        skills_dir: Path,
        tool_preference: str = "balanced",
    ):
        self.client = client
        self.generator = generator
        self.skills_dir = skills_dir
        self.tool_preference = tool_preference

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
            return self._apply_tool_preference(proposal)

        cluster = digest.failure_clusters[0]
        return self._apply_tool_preference({
            "target_family": cluster.capability_family,
            "target_cluster_ids": [cluster.cluster_id],
            "representative_case_ids": list(cluster.representative_case_ids[:1]),
            "next_action": "generate_skill",
            "tool_goal": "",
            "skill_update_note": f"Improve the solver SOP for {cluster.capability_family} on this failure cluster.",
            "rationale": "Fallback heuristic selected the largest remaining failure cluster.",
            "expected_gain": "Raise full training-subset accuracy on the selected failure cluster.",
        })

    def materialize_bundle(
        self,
        proposal: dict[str, Any],
        digest: TrainingSetDigest,
        cases_by_id: dict[str, TaskCase],
        active_dir: Path,
        work_dir: Path,
    ) -> CapabilityBundleProposal:
        run_id = datetime.now().strftime("round_%Y%m%d_%H%M%S_%f")
        representative_ids = [str(value) for value in proposal.get("representative_case_ids", []) if str(value).strip()]
        if not representative_ids:
            representative_ids = _fallback_representatives(digest)
        case = cases_by_id[representative_ids[0]]
        active_store = CapabilityStore(active_dir)
        existing_skill = active_store.get_skill(case.capability_family())
        temp_loop = EvolutionLoop(
            work_dir=work_dir,
            learned_dir=active_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.client,
            max_attempts=1,
            subset_id=None,
        )
        chain_context = temp_loop.validator.build_chain_context(
            case,
            existing_skill.content if existing_skill else None,
            attempt=1,
        )
        analysis = FailureAnalysis(
            root_cause=str(proposal.get("rationale", "")) or _cluster_summary(digest, representative_ids[0]),
            next_action=str(proposal.get("next_action", "generate_skill")),
            confidence=0.6,
            missing_step=str(proposal.get("expected_gain", "")) or "Improve the selected failure cluster.",
            tool_goal=str(proposal.get("tool_goal", "")),
            skill_update_note=str(proposal.get("skill_update_note", "")),
            rationale=str(proposal.get("rationale", "")),
            differentiation_note="Subset-level planner selected this cluster from the training digest.",
        )

        tools: list[ToolProposal] = []
        skills: list[SkillProposal] = []
        staged_tool: ToolProposal | None = None
        if analysis.next_action in {"generate_tool", "generate_both"}:
            staged_tool = self.generator.generate_tool(case, analysis, chain_context=chain_context)
            tools.append(staged_tool)
        if analysis.next_action in {"generate_skill", "generate_both", "generate_code_skill"} or staged_tool is not None:
            if analysis.next_action == "generate_code_skill" and hasattr(self.generator, "generate_code_writing_skill"):
                skill = self.generator.generate_code_writing_skill(
                    case,
                    analysis,
                    existing_skill_content=existing_skill.content if existing_skill else None,
                    chain_context=chain_context,
                )
            else:
                skill = self.generator.generate_skill(
                    case,
                    analysis,
                    staged_tool,
                    existing_skill_content=existing_skill.content if existing_skill else None,
                    chain_context=chain_context,
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
            tools=tools,
            skills=skills,
        )

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

Recent rejected plans:
{json.dumps(digest.recent_rejected_plans, ensure_ascii=False)}

Rules:
- Choose exactly one target cluster.
- Use only representative_case_ids that already appear above.
- Prefer the smallest candidate that could raise overall train accuracy.
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
  "tool_goal": "short tool goal if any",
  "skill_update_note": "short SOP update note if any",
  "rationale": "why this is the best next candidate",
  "expected_gain": "what score gain or failure-cluster gain is expected"
}}
"""

    def _apply_tool_preference(self, proposal: dict[str, Any]) -> dict[str, Any]:
        adjusted = dict(proposal)
        next_action = str(adjusted.get("next_action", "")).strip() or "generate_skill"

        if self.tool_preference == "prefer_tools" and next_action == "generate_skill":
            adjusted["next_action"] = "generate_both"
        elif self.tool_preference == "require_tools" and next_action in {"generate_skill", "generate_code_skill"}:
            adjusted["next_action"] = "generate_tool"

        return adjusted


class SubsetEvolutionLoop:
    """Training-subset evolution loop with active/candidate gating."""

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

        self.subset_root = learned_root / subset_id
        self.active_dir = self.subset_root / "active"
        self.active_store = CapabilityStore(self.active_dir)
        self.generator = Generator(vlm_client)
        self.evaluator = SubsetEvaluator(adapters, skills_dir, vlm_client, capability_mode=capability_mode)
        self.planner = SubsetPlanner(
            vlm_client,
            self.generator,
            skills_dir,
            tool_preference=tool_preference,
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
            if not bundle.tools and not bundle.skills:
                print(f"[subset-loop] round {round_idx}: planner produced no tool/skill artifacts, stopping")
                break

            candidate_dir = self.active_store.stage_bundle(bundle)
            smoke_passed, smoke_reason = self._smoke_validate(bundle, cases_by_id, candidate_dir, round_idx)
            if not smoke_passed:
                print(f"[subset-loop] round {round_idx}: smoke failed: {smoke_reason}")
                self.active_store.record_rejected_plan(
                    {
                        "run_id": bundle.run_id,
                        "reason": smoke_reason,
                        "target_family": bundle.target_family,
                        "target_cluster_ids": bundle.target_cluster_ids,
                    }
                )
                self.active_store.discard_bundle(bundle.run_id)
                round_results.append(
                    CandidateEvalResult(
                        run_id=bundle.run_id,
                        accepted=False,
                        reason=smoke_reason,
                        baseline_score=current_summary.primary_score,
                        candidate_score=current_summary.primary_score,
                        score_delta=0.0,
                        smoke_passed=False,
                        target_family=bundle.target_family,
                        target_cluster_ids=list(bundle.target_cluster_ids),
                        representative_case_ids=list(bundle.representative_case_ids),
                        baseline_summary=current_summary,
                        candidate_summary=current_summary,
                    )
                )
                continue

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
            else:
                self.active_store.record_rejected_plan(
                    {
                        "run_id": bundle.run_id,
                        "reason": reason,
                        "target_family": bundle.target_family,
                        "target_cluster_ids": bundle.target_cluster_ids,
                        "baseline_score": current_summary.primary_score,
                        "candidate_score": candidate_summary.primary_score,
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

        snapshot_name = f"{self.subset_id}_train_snapshot"
        self.active_store.snapshot_current_capabilities(snapshot_name)
        final_summary, final_records = self.evaluator.evaluate(
            self.active_dir,
            self.work_dir / "final_active_eval",
            cases,
            "final_active",
            stage_label="final active",
        )
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

    def _smoke_validate(
        self,
        bundle: CapabilityBundleProposal,
        cases_by_id: dict[str, TaskCase],
        candidate_dir: Path,
        round_idx: int,
    ) -> tuple[bool, str]:
        smoke_cases = [cases_by_id[case_id] for case_id in bundle.representative_case_ids if case_id in cases_by_id]
        if not smoke_cases:
            return False, "No representative case available for smoke validation."

        print(
            f"[subset-loop] smoke validate: run_id={bundle.run_id} "
            f"cases={[case.case_id for case in smoke_cases]}"
        )

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

        for tool in bundle.tools:
            print(f"[subset-loop] smoke validate: tool {tool.name}")
            validation = validator.validate_tool(
                tool,
                origin_case=smoke_cases[0],
                agent_factory=lambda: validator_loop._create_agent(smoke_cases[0], attempt=1, phase="smoke_validate"),
                regression_cases=None,
                chain_context=None,
                attempt=1,
            )
            if not validation.passed:
                return False, validation.reason or f"Tool {tool.name} failed smoke validation."

        for skill in bundle.skills:
            print(f"[subset-loop] smoke validate: skill {skill.name}")
            validation = validator.validate_skill(skill, skill.name)
            if not validation.passed:
                return False, validation.reason or f"Skill {skill.name} failed static validation."
            required_tools = validator._extract_tool_sequence(skill.content)
            missing = [tool_name for tool_name in required_tools if tool_name not in available_tools]
            if missing:
                return False, f"Skill {skill.name} references unavailable tools: {', '.join(missing)}"

        for index, case in enumerate(smoke_cases, start=1):
            try:
                print(f"[subset-loop] smoke run [{index:02d}/{len(smoke_cases):02d}] case={case.case_id}")
                self.evaluator._run_case(
                    candidate_dir,
                    self.work_dir / f"round_{round_idx}" / "smoke_runs",
                    case,
                    f"smoke_case_{index}",
                )
            except Exception as exc:  # pragma: no cover - defensive
                return False, f"Smoke run crashed for case {case.case_id}: {exc}"

        return True, "smoke passed"


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
