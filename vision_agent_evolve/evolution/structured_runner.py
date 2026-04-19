"""Structured benchmark runner for ChartQA-style experiments."""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import os

from core.agent import AgentConfig, ReActAgent
from core.structured_data import check_chartqa_case_answer, load_normalized_cases
from core.tool_calling_runtime import ToolCallingRuntimeConfig, run_function_calling_vqa_case
from core.types import AgentResult, AgentStep, TaskCase
from core.vlm_client import ModelSettings, VLMClient
from evolution.benchmark_adapters import BenchmarkAdapter, get_benchmark_adapter
from evolution.loop import EvolutionLoop
from evolution.subset_loop import SubsetEvolutionLoop
from tools.builtin_tools import list_builtin_tools


@dataclass
class StructuredExperimentConfig:
    """Configuration for the structured benchmark experiment."""

    dataset: str
    raw_data_root: Path
    normalized_data_root: Path
    subset_id: str
    datasets: list[str] | str | None = None
    evolve_split: str = "train"
    held_out_split: str = "val"
    k: int = 200
    train_subset_size: int = 0
    held_out_limit: int = 0
    max_attempts: int = 10
    max_planning_rounds: int = 5
    families_per_round_limit: int = 3
    representatives_per_cluster: int = 3
    tool_preference: str = "balanced"
    readability_judge_enabled: bool = False
    settings: list[str] = field(default_factory=lambda: ["reasoned_vlm", "pure_react", "agent_train_adaptive", "preset_tools_only", "frozen_inference"])
    save_first_n_evolves: int = 10
    forced_skill_name: str | None = None
    fixed_tool_names: list[str] = field(default_factory=list)
    disable_generated_tools: bool = False
    capability_root: Path | None = None
    use_skills: bool = True
    num_workers: int = 1


@dataclass
class StructuredCaseRecord:
    """Per-case structured benchmark output."""

    setting: str
    split: str
    case_id: str
    problem_id: str
    expected: str
    answer: str
    correct: bool
    turns: int
    tool_count: int
    score: float | None = None
    tool_names: list[str] = field(default_factory=list)
    used_tool: bool = False
    artifact_paths: list[str] = field(default_factory=list)
    chain_trace: list[str] = field(default_factory=list)
    image_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    readability_improved: str | None = None
    target_region_clearer: int | None = None
    text_or_marks_more_legible: int | None = None
    overall_usefulness: int | None = None
    readability_notes: str | None = None
    initial_answer: str | None = None
    initial_correct: bool | None = None
    evolve_triggered: bool | None = None
    evolve_success: bool | None = None
    full_agent_answer: str | None = None
    full_agent_correct: bool | None = None
    post_evolve_answer: str | None = None
    post_evolve_correct: bool | None = None
    forced_skill_name: str | None = None
    forced_skill_enforced: bool | None = None
    scratch_code_triggered: bool | None = None
    scratch_code_success: bool | None = None
    scratch_script_summary: str | None = None
    scratch_artifact_paths: list[str] = field(default_factory=list)
    code_writing_skill_used: bool | None = None
    edited_artifact_judged_useful: bool | None = None


class ReadabilityJudge:
    """Automatic judge for tool-generated artifact readability."""

    def __init__(self, client: VLMClient, project_root: Path):
        self.client = client
        self.project_root = project_root

    def judge(self, case: TaskCase, artifact_path: str) -> dict[str, Any] | None:
        original = self._resolve_path(case.image_path)
        artifact = self._resolve_path(artifact_path)
        if original is None or artifact is None:
            return None

        prompt = (
            "Compare the original chart image and the processed artifact.\n"
            "Judge whether the artifact makes the target chart region easier to read.\n"
            "Return compact JSON only with keys:\n"
            "{"
            "\"readability_improved\":\"yes|no\","
            "\"target_region_clearer\":1-5,"
            "\"text_or_marks_more_legible\":1-5,"
            "\"overall_usefulness\":1-5,"
            "\"notes\":\"short note\""
            "}"
        )
        messages = [
            {"role": "system", "content": "You are a strict evaluator of chart readability improvements."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "text", "text": "\nOriginal image"},
                    {"type": "image_url", "image_url": {"url": self._image_data_url(original)}},
                    {"type": "text", "text": "\nProcessed artifact"},
                    {"type": "image_url", "image_url": {"url": self._image_data_url(artifact)}},
                ],
            },
        ]
        response, _ = self.client.chat(messages, ModelSettings(temperature=0.0, max_tokens=400))
        payload = _extract_json(response)
        if not payload:
            return None

        return {
            "readability_improved": _normalize_yes_no(payload.get("readability_improved")),
            "target_region_clearer": _clamp_score(payload.get("target_region_clearer")),
            "text_or_marks_more_legible": _clamp_score(payload.get("text_or_marks_more_legible")),
            "overall_usefulness": _clamp_score(payload.get("overall_usefulness")),
            "readability_notes": str(payload.get("notes", "")).strip() or None,
        }

    def _resolve_path(self, path_str: str) -> Path | None:
        if not path_str:
            return None
        path = Path(path_str)
        if path.is_absolute():
            return path if path.exists() else None

        for candidate in [self.project_root / path, Path.cwd() / path]:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _image_data_url(path: Path) -> str:
        return VLMClient.image_data_url(path)


class StructuredBenchmarkRunner:
    """Runs the four-setting ChartQA experiment."""

    def __init__(
        self,
        config: StructuredExperimentConfig,
        project_root: Path,
        vlm_client: VLMClient | None = None,
    ):
        self.config = config
        self.project_root = project_root
        self.skills_dir = project_root / "skills"
        self.learned_root = project_root / "learned"
        self.output_dir = project_root / "artifacts" / "structured_benchmarks" / config.subset_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.records_path = self.output_dir / "per_case.jsonl"
        self.summary_path = self.output_dir / "summary.json"
        self.evolve_reports_path = self.output_dir / "first_10_evolves.json"
        self.vlm_client = vlm_client or VLMClient()
        self.last_subset_rounds: list[dict[str, Any]] = []
        self.readability_judge = (
            ReadabilityJudge(self.vlm_client, project_root)
            if config.readability_judge_enabled
            else None
        )
        self.adapters = {
            dataset_name: get_benchmark_adapter(dataset_name, client=self.vlm_client)
            for dataset_name in self._configured_datasets()
        }

    def _configured_datasets(self) -> list[str]:
        datasets = self.config.datasets if self.config.datasets is not None else self.config.dataset
        if isinstance(datasets, str):
            items = [datasets]
        else:
            items = list(datasets)
        normalized: list[str] = []
        for item in items:
            value = str(item).strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        return normalized or [self.config.dataset]

    def _load_cases(self, split: str, limit: int) -> list[TaskCase]:
        cases: list[TaskCase] = []
        for dataset_name in self._configured_datasets():
            adapter = self.adapters[dataset_name]
            cases.extend(adapter.load_cases(self.config.normalized_data_root, split, limit=0))
        cases.sort(key=lambda case: (case.dataset_name(), case.case_id))
        if limit:
            cases = cases[:limit]
        return cases

    def _write_train_subset_manifest(self, cases: list[TaskCase]) -> None:
        manifest_path = self.output_dir / "train_subset_manifest.json"
        payload = {
            "subset_id": self.config.subset_id,
            "split": self.config.evolve_split,
            "total_cases": len(cases),
            "datasets": self._configured_datasets(),
            "cases": [
                {
                    "case_id": case.case_id,
                    "dataset_name": case.dataset_name(),
                    "capability_family": case.capability_family(),
                    "source_id": case.source_id(),
                }
                for case in cases
            ],
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def run_experiment(self) -> dict[str, Any]:
        """Run direct baseline, adaptive train, and frozen inference settings."""
        evolve_cases = self._load_cases(
            split=self.config.evolve_split,
            limit=self.config.train_subset_size or self.config.k,
        )
        held_out_cases = self._load_cases(split=self.config.held_out_split, limit=self.config.held_out_limit)
        self._write_train_subset_manifest(evolve_cases)

        self.records_path.write_text("", encoding="utf-8")
        if {"agent_train_adaptive", "scratch_skill_train_adaptive"} & set(self.config.settings):
            self._reset_evolve_reports_file()
        records: list[StructuredCaseRecord] = []
        snapshot_name = ""
        train_limit = self.config.train_subset_size or self.config.k

        if "direct_vlm" in self.config.settings:
            print(f"=== Direct VLM baseline on {self.config.evolve_split}[:{train_limit}] ===")
            records.extend(self._run_direct_vlm(evolve_cases))

        if "reasoned_vlm" in self.config.settings:
            print(f"\n=== Reasoned VLM baseline on {self.config.evolve_split}[:{train_limit}] ===")
            records.extend(self._run_reasoned_vlm(evolve_cases))

        if "pure_react" in self.config.settings:
            print(f"\n=== Pure ReAct baseline on {self.config.evolve_split}[:{train_limit}] ===")
            records.extend(self._run_pure_react(evolve_cases))

        if "function_calling_vqa" in self.config.settings:
            print(f"\n=== Function-calling VQA baseline on {self.config.evolve_split}[:{train_limit}] ===")
            records.extend(self._run_function_calling_vqa(evolve_cases))

        if "toolpool_prompt_baseline" in self.config.settings:
            print(f"\n=== Same-tool prompt baseline on {self.config.evolve_split}[:{train_limit}] ===")
            records.extend(self._run_toolpool_prompt_baseline(evolve_cases))

        if "agent_train_adaptive" in self.config.settings:
            print(f"\n=== Agent adaptive train on {self.config.evolve_split}[:{train_limit}] ===")
            train_records, snapshot_name = self._run_agent_train_adaptive(evolve_cases)
            records.extend(train_records)

        if "skill_only_train_adaptive" in self.config.settings:
            print(f"\n=== Skill-only same-tool train on {self.config.evolve_split}[:{train_limit}] ===")
            train_records, snapshot_name = self._run_skill_only_train_adaptive(evolve_cases)
            records.extend(train_records)

        if "scratch_skill_train_adaptive" in self.config.settings:
            print(f"\n=== Scratch-skill adaptive train on {self.config.evolve_split}[:{train_limit}] ===")
            scratch_records, snapshot_name = self._run_scratch_skill_train_adaptive(evolve_cases)
            records.extend(scratch_records)

        if "frozen_inference" in self.config.settings:
            print(f"\n=== Frozen inference on {self.config.held_out_split} ===")
            fi_snapshot = snapshot_name
            if not fi_snapshot and not self.config.capability_root:
                fi_snapshot = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(self.run_frozen_inference(snapshot_name=fi_snapshot or None, cases=held_out_cases))

        if "preset_tools_only" in self.config.settings:
            print(f"\n=== Preset-tools-only inference on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=snapshot_name,
                    cases=held_out_cases,
                    use_skill=False,
                )
            )

        if "same_tool_preset_tools_only" in self.config.settings:
            print(f"\n=== Same-tool preset-only inference on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=snapshot_name,
                    cases=held_out_cases,
                    capability_mode="skill_only_same_tools",
                    use_skill=False,
                )
            )

        if "frozen_inference_forced_skill" in self.config.settings:
            print(f"\n=== Frozen inference with forced skill on {self.config.held_out_split} ===")
            forced_snapshot = snapshot_name
            if not forced_snapshot and not self.config.capability_root:
                forced_snapshot = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=forced_snapshot or None,
                    cases=held_out_cases,
                    force_skill=True,
                )
            )

        if "skill_only_frozen_inference" in self.config.settings:
            print(f"\n=== Skill-only same-tool frozen inference on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=snapshot_name,
                    cases=held_out_cases,
                    capability_mode="skill_only_same_tools",
                )
            )

        if "scratch_skill_frozen_inference" in self.config.settings:
            print(f"\n=== Scratch-skill frozen inference on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=snapshot_name,
                    cases=held_out_cases,
                    capability_mode="scratch_code_skill",
                )
            )

        if "scratch_skill_frozen_forced" in self.config.settings:
            print(f"\n=== Scratch-skill frozen forced inference on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(
                self.run_frozen_inference(
                    snapshot_name=snapshot_name,
                    cases=held_out_cases,
                    force_skill=True,
                    capability_mode="scratch_code_skill",
                )
            )

        if "frozen_inference_fc_forced_skill" in self.config.settings:
            print(f"\n=== Frozen inference FC with forced skill on {self.config.held_out_split} ===")
            records.extend(self._run_frozen_inference_fc(held_out_cases))

        summary = self._write_summary(records, snapshot_name=snapshot_name)
        return summary

    def run_frozen_inference(
        self,
        snapshot_name: str | None = None,
        subset_id: str | None = None,
        cases: list[TaskCase] | None = None,
        force_skill: bool = False,
        capability_mode: str = "persistent_tools",
        use_skill: bool = True,
    ) -> list[StructuredCaseRecord]:
        """Evaluate a frozen subset or snapshot without further mutations."""
        held_out_cases = cases or self._load_cases(split=self.config.held_out_split, limit=self.config.held_out_limit)
        loop = self._make_frozen_loop(snapshot_name=snapshot_name, subset_id=subset_id, capability_mode=capability_mode)
        setting_name = self._frozen_setting_name(capability_mode, force_skill, use_skill)
        existing_by_case = self._existing_records_by_case(setting=setting_name, split=self.config.held_out_split)

        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(held_out_cases, start=1):
            existing = existing_by_case.get(case.case_id)
            if existing is not None:
                records.append(existing)
                print(
                    f"[{index:03d}/{len(held_out_cases):03d}] "
                    f"SKIP case={case.case_id} answer={existing.answer!r} (resume)"
                )
                continue
            result, chain_trace = self._run_with_learned_capabilities(
                loop,
                case,
                phase=f"{'forced_skill_' if force_skill else ''}frozen_inference_{index}",
                force_skill=force_skill,
                capability_mode=capability_mode,
                use_skill=use_skill,
            )
            record = self._record_from_agent_result(
                setting=setting_name,
                split=self.config.held_out_split,
                case=case,
                result=result,
                correct=self._check_answer(result.final_answer, case),
                chain_trace=chain_trace,
            )
            record.full_agent_answer = result.final_answer
            record.full_agent_correct = record.correct
            record.forced_skill_name = self._forced_skill_name(case) if force_skill else None
            record.forced_skill_enforced = force_skill and bool(record.forced_skill_name)
            self._annotate_scratch_record(record, result, capability_mode)
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(held_out_cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def run_frozen_transfer(
        self,
        snapshot_name: str | None = None,
        subset_id: str | None = None,
        cases: list[TaskCase] | None = None,
    ) -> list[StructuredCaseRecord]:
        """Backward-compatible alias for frozen inference."""
        return self.run_frozen_inference(snapshot_name=snapshot_name, subset_id=subset_id, cases=cases)

    def _run_direct_vlm(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        def _process(index_case: tuple[int, TaskCase]) -> StructuredCaseRecord:
            index, case = index_case
            answer = ""
            direct_error = ""
            try:
                answer = self._direct_answer(case)
            except Exception as exc:
                direct_error = str(exc)
            score = self._score_answer(answer, case)
            record = StructuredCaseRecord(
                setting="direct_vlm",
                split=self.config.evolve_split,
                case_id=case.case_id,
                problem_id=case.problem_id,
                expected=case.gold_answer,
                answer=answer,
                correct=self._check_answer(answer, case),
                score=score,
                turns=1,
                tool_count=0,
                tool_names=[],
                used_tool=False,
                artifact_paths=[],
                image_path=case.image_path,
                metadata=dict(case.metadata),
            )
            if direct_error:
                record.metadata["runtime_error"] = direct_error
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={answer!r}"
            )
            return record

        num_workers = self.config.num_workers
        indexed = list(enumerate(cases, start=1))
        if num_workers > 1:
            result_map: dict[int, StructuredCaseRecord] = {}
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {executor.submit(_process, item): item[0] for item in indexed}
                for future in as_completed(futures):
                    idx = futures[future]
                    result_map[idx] = future.result()
            records = [result_map[i] for i in range(1, len(cases) + 1)]
        else:
            records = [_process(item) for item in indexed]

        for record in records:
            self._append_record(record)
        return records

    def _run_reasoned_vlm(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            answer = ""
            reasoned_error = ""
            try:
                answer = self._reasoned_answer(case)
            except Exception as exc:
                reasoned_error = str(exc)
            score = self._score_answer(answer, case)
            record = StructuredCaseRecord(
                setting="reasoned_vlm",
                split=self.config.evolve_split,
                case_id=case.case_id,
                problem_id=case.problem_id,
                expected=case.gold_answer,
                answer=answer,
                correct=self._check_answer(answer, case),
                score=score,
                turns=1,
                tool_count=0,
                tool_names=[],
                used_tool=False,
                artifact_paths=[],
                image_path=case.image_path,
                metadata=dict(case.metadata),
            )
            if reasoned_error:
                record.metadata["runtime_error"] = reasoned_error
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={answer!r}"
            )
        return records

    def _run_pure_react(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            agent = self._create_plain_react_agent(case, phase=f"pure_react_{index}")
            try:
                result = agent.run(case.prompt, case.image_path, initial_observations=[])
            except Exception as exc:
                result = self._runtime_failure_result(case, exc)
            record = self._record_from_agent_result(
                setting="pure_react",
                split=self.config.evolve_split,
                case=case,
                result=result,
                correct=self._check_answer(result.final_answer, case),
                chain_trace=[],
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_function_calling_vqa(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        configured = set(self._configured_datasets())
        if configured != {"vstar"}:
            raise ValueError(
                "The function_calling_vqa setting is currently supported only for dataset='vstar'."
            )

        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            work_dir = self.output_dir / "function_calling_vqa" / f"case_{case.case_id}"
            try:
                result = run_function_calling_vqa_case(
                    self.vlm_client,
                    case,
                    benchmark_name=case.dataset_name(),
                    config=ToolCallingRuntimeConfig(
                        work_dir=work_dir,
                        capability_root=self.config.capability_root,
                        static_skills_dir=self.project_root / "skills",
                        use_skills=self.config.use_skills,
                    ),
                )
            except Exception as exc:
                result = self._runtime_failure_result(case, exc)
            record = self._record_from_agent_result(
                setting="function_calling_vqa",
                split=self.config.evolve_split,
                case=case,
                result=result,
                correct=self._check_answer(result.final_answer, case),
                chain_trace=[],
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_frozen_inference_fc(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        """Run function-calling VQA with a forced skill loaded from capability_root."""
        forced_skill_content = ""
        if self.config.capability_root:
            skill_name = (self.config.forced_skill_name or "").strip()
            if skill_name:
                candidates = [Path(self.config.capability_root) / "skills" / skill_name / "SKILL.md"]
            else:
                skills_dir = Path(self.config.capability_root) / "skills"
                candidates = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
            for candidate in candidates:
                if candidate.exists():
                    forced_skill_content = candidate.read_text(encoding="utf-8")
                    break

        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            work_dir = self.output_dir / "frozen_inference_fc" / f"case_{case.case_id}"
            chart_bbox = {
                "x_values_bbox": case.metadata.get("x_values_bbox") or {},
                "y_values_bbox": case.metadata.get("y_values_bbox") or {},
                "columns_bbox": case.metadata.get("columns_bbox") or {},
                "rows_bbox": case.metadata.get("row_starters") or {},
            }
            try:
                result = run_function_calling_vqa_case(
                    self.vlm_client,
                    case,
                    benchmark_name=case.dataset_name(),
                    config=ToolCallingRuntimeConfig(
                        work_dir=work_dir,
                        chart_bbox=chart_bbox,
                        forced_skill_content=forced_skill_content,
                    ),
                )
            except Exception as exc:
                result = self._runtime_failure_result(case, exc)
            record = self._record_from_agent_result(
                setting="frozen_inference_fc_forced_skill",
                split=self.config.held_out_split,
                case=case,
                result=result,
                correct=self._check_answer(result.final_answer, case),
                chain_trace=[],
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_agent_train_adaptive(self, cases: list[TaskCase]) -> tuple[list[StructuredCaseRecord], str]:
        subset_loop = self._make_subset_loop(cases)
        report = subset_loop.run(cases)
        self.last_subset_rounds = [asdict(item) for item in report.round_results]
        round_payload = [
            {
                "ordinal": index,
                "case_id": result.representative_case_ids[0] if result.representative_case_ids else "",
                "target_family": result.target_family,
                "target_cluster_ids": list(result.target_cluster_ids),
                "attempts": [
                    {
                        "attempt": 1,
                        "decision": "keep" if result.accepted else "discard",
                        "smoke_passed": result.smoke_passed,
                        "baseline_score": result.baseline_score,
                        "candidate_score": result.candidate_score,
                        "score_delta": result.score_delta,
                        "reason": result.reason,
                    }
                ],
            }
            for index, result in enumerate(report.round_results[: self.config.save_first_n_evolves], start=1)
        ]
        self._save_evolve_reports(round_payload)
        records = self._materialize_agent_train_records(
            cases,
            report.baseline_records,
            report.final_records,
            report.round_results,
        )
        self._replace_records_for_setting("agent_train_adaptive", self.config.evolve_split, records)
        for index, record in enumerate(records, start=1):

            status = "OK" if record.correct else "FAIL"
            extra = " evolved" if record.evolve_triggered else " no-evolve"
            print(
                f"[{index:03d}/{len(cases):03d}] {status}{extra} "
                f"case={record.case_id} answer={record.answer!r}"
            )

        return records, report.snapshot_name

    def _run_skill_only_train_adaptive(self, cases: list[TaskCase]) -> tuple[list[StructuredCaseRecord], str]:
        subset_loop = self._make_subset_loop(cases, capability_mode="skill_only_same_tools")
        report = subset_loop.run(cases)
        self.last_subset_rounds = [asdict(item) for item in report.round_results]
        records = self._materialize_agent_train_records(
            cases,
            report.baseline_records,
            report.final_records,
            report.round_results,
            setting="skill_only_train_adaptive",
        )
        self._replace_records_for_setting("skill_only_train_adaptive", self.config.evolve_split, records)
        for index, record in enumerate(records, start=1):
            status = "OK" if record.correct else "FAIL"
            extra = " evolved" if record.evolve_triggered else " no-evolve"
            print(
                f"[{index:03d}/{len(cases):03d}] {status}{extra} "
                f"case={record.case_id} answer={record.answer!r}"
            )
        return records, report.snapshot_name

    def _make_subset_loop(
        self,
        cases: list[TaskCase] | None = None,
        capability_mode: str = "persistent_tools",
    ) -> SubsetEvolutionLoop:
        train_cases = list(cases or [])
        return SubsetEvolutionLoop(
            subset_id=self.config.subset_id,
            learned_root=self.learned_root,
            skills_dir=self.skills_dir,
            work_dir=self.output_dir / "agent_train_adaptive",
            vlm_client=self.vlm_client,
            adapters=self.adapters,
            max_planning_rounds=self.config.max_planning_rounds,
            representatives_per_cluster=self.config.representatives_per_cluster,
            families_per_round_limit=self.config.families_per_round_limit,
            tool_preference=self.config.tool_preference,
            capability_mode=capability_mode,
            fixed_builtin_tools=self.config.fixed_tool_names,
            disable_generated_tools=self.config.disable_generated_tools,
            checkpoint_callback=lambda baseline_records, current_records, round_results, snapshot_name: self._checkpoint_agent_train_adaptive(
                cases=train_cases,
                baseline_records=baseline_records,
                current_records=current_records,
                round_results=round_results,
                snapshot_name=snapshot_name,
            ),
        )

    def _run_scratch_skill_train_adaptive(self, cases: list[TaskCase]) -> tuple[list[StructuredCaseRecord], str]:
        loop = self._make_online_loop(capability_mode="scratch_code_skill")
        records: list[StructuredCaseRecord] = []
        saved_evolve_reports = 0
        collected_reports: list[dict[str, Any]] = []

        for index, case in enumerate(cases, start=1):
            full_agent_result, full_agent_chain = self._run_with_learned_capabilities(
                loop,
                case,
                phase=f"scratch_skill_train_{index}",
                capability_mode="scratch_code_skill",
            )
            full_agent_correct = self._check_answer(full_agent_result.final_answer, case)

            if full_agent_correct:
                final_result = full_agent_result
                final_chain = full_agent_chain
                evolve_triggered = False
                evolve_success = True
                post_evolve_result = None
            else:
                evolve_triggered = True
                evolve_success = loop.run_single_case(case)
                if saved_evolve_reports < self.config.save_first_n_evolves:
                    report = dict(loop.last_case_report or {})
                    report["ordinal"] = saved_evolve_reports + 1
                    collected_reports.append(report)
                    self._save_evolve_reports(collected_reports)
                    saved_evolve_reports += 1
                post_evolve_result, final_chain = self._run_with_learned_capabilities(
                    loop,
                    case,
                    phase=f"scratch_skill_train_post_{index}",
                    capability_mode="scratch_code_skill",
                )
                final_result = post_evolve_result

            record = self._record_from_agent_result(
                setting="scratch_skill_train_adaptive",
                split=self.config.evolve_split,
                case=case,
                result=final_result,
                correct=self._check_answer(final_result.final_answer, case),
                chain_trace=final_chain,
            )
            record.initial_answer = full_agent_result.final_answer
            record.initial_correct = full_agent_correct
            record.full_agent_answer = full_agent_result.final_answer
            record.full_agent_correct = full_agent_correct
            record.post_evolve_answer = None if post_evolve_result is None else post_evolve_result.final_answer
            record.post_evolve_correct = (
                None
                if post_evolve_result is None
                else self._check_answer(post_evolve_result.final_answer, case)
            )
            record.evolve_triggered = evolve_triggered
            record.evolve_success = evolve_success
            self._annotate_scratch_record(record, final_result, "scratch_code_skill")
            self._append_record(record)
            records.append(record)

            status = "OK" if record.correct else "FAIL"
            extra = " no-evolve" if not evolve_triggered else " evolved"
            print(
                f"[{index:03d}/{len(cases):03d}] {status}{extra} "
                f"case={case.case_id} answer={record.answer!r}"
            )

        snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
        loop.store.snapshot_current_capabilities(snapshot_name)
        return records, snapshot_name

    def _run_online_evolve(self, cases: list[TaskCase]) -> tuple[list[StructuredCaseRecord], str]:
        """Backward-compatible alias for the renamed adaptive train setting."""
        return self._run_agent_train_adaptive(cases)

    def _record_from_agent_result(
        self,
        setting: str,
        split: str,
        case: TaskCase,
        result: AgentResult,
        correct: bool,
        chain_trace: list[str],
    ) -> StructuredCaseRecord:
        tool_names = _merge_tool_names(_extract_tool_names(result), chain_trace)
        artifacts = result.get_image_artifacts()
        readability = None
        if self.readability_judge is not None and artifacts:
            readability = self.readability_judge.judge(case, artifacts[-1])
        score = self._score_answer(result.final_answer, case)

        return StructuredCaseRecord(
            setting=setting,
            split=split,
            case_id=case.case_id,
            problem_id=case.problem_id,
            expected=case.gold_answer,
            answer=result.final_answer,
            correct=correct,
            score=score,
            turns=result.total_turns,
            tool_count=len(tool_names),
            tool_names=tool_names,
            used_tool=bool(tool_names),
            artifact_paths=artifacts,
            chain_trace=chain_trace,
            image_path=case.image_path,
            metadata=_merge_record_metadata(case.metadata, result.error),
            readability_improved=None if readability is None else readability.get("readability_improved"),
            target_region_clearer=None if readability is None else readability.get("target_region_clearer"),
            text_or_marks_more_legible=None if readability is None else readability.get("text_or_marks_more_legible"),
            overall_usefulness=None if readability is None else readability.get("overall_usefulness"),
            readability_notes=None if readability is None else readability.get("readability_notes"),
        )

    def _direct_answer(self, case: TaskCase) -> str:
        return self._reasoned_answer(case)

    def _reasoned_answer(self, case: TaskCase) -> str:
        choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
        choice_block = ""
        if choices and "choices:" not in case.prompt.lower():
            choice_lines = "\n".join(f"{label}. {text}" for label, text in sorted(choices.items()))
            choice_block = f"\nChoices:\n{choice_lines}"
        family = str(case.metadata.get("capability_family", "")).strip().lower()
        dataset_name = str(case.metadata.get("dataset_name", "")).strip().lower()
        instruction_lines = [
            "Analyze the image and question briefly before answering.",
            "Keep the reasoning concise and grounded in visible evidence.",
            "End with a final line exactly in the format: Final answer: <answer>",
        ]
        if dataset_name == "vstar":
            instruction_lines.append("If the question provides labeled options, return only the matching option letter in Final answer.")
        if family == "vstar_relative_position":
            instruction_lines.extend(
                [
                    "For left/right questions, first determine the semantic conclusion from the viewer's perspective.",
                    "Then map that conclusion to the matching option in the question.",
                ]
            )
        elif dataset_name != "vstar" and "(a)" in case.prompt.lower() and "(b)" in case.prompt.lower():
            instruction_lines.append("If the question provides labeled options, return only the matching option letter in Final answer.")
        elif dataset_name != "vstar":
            instruction_lines.append("In Final answer, give the final answer itself rather than an explanation.")
        prompt = "\n".join(instruction_lines) + f"\n\nQuestion: {case.prompt}{choice_block}"
        # Append bbox label info to match VTool-R1 eval protocol
        if dataset_name == "refocus_chart":
            x_values_bbox = case.metadata.get("x_values_bbox", {})
            y_values_bbox = case.metadata.get("y_values_bbox", {})
            x_keys = list(x_values_bbox.keys()) if isinstance(x_values_bbox, dict) else []
            y_keys = list(y_values_bbox.keys()) if isinstance(y_values_bbox, dict) else []
            bbox_info_lines = []
            if x_keys:
                bbox_info_lines.append(f"The x values in the image are: {x_keys}.")
            if y_keys:
                bbox_info_lines.append(f"The y values in the image are: {y_keys}.")
            if bbox_info_lines:
                prompt += "\n\nChart axis info: " + " ".join(bbox_info_lines)
        elif dataset_name == "refocus_tablevqa":
            columns_bbox = case.metadata.get("columns_bbox", {})
            row_starters = case.metadata.get("row_starters", {})
            col_keys = list(columns_bbox.keys()) if isinstance(columns_bbox, dict) else []
            row_keys = list(row_starters.keys()) if isinstance(row_starters, dict) else []
            bbox_info_lines = []
            if col_keys:
                bbox_info_lines.append(f"The columns in the image are: {col_keys}.")
            if row_keys:
                bbox_info_lines.append(f"The rows in the image start with: {row_keys}.")
            if bbox_info_lines:
                prompt += "\n\nTable structure info: " + " ".join(bbox_info_lines)
        max_tokens = 1024 if dataset_name in ("refocus_chart", "refocus_tablevqa") else 200
        messages = [
            {
                "role": "user",
                "content": VLMClient.image_message_parts(case.image_path, prompt),
            }
        ]
        response, _ = self.vlm_client.chat(messages, ModelSettings(temperature=0.0, max_tokens=max_tokens))
        return _extract_final_answer_text(response)

    def _create_plain_react_agent(self, case: TaskCase, phase: str) -> ReActAgent:
        work_dir = self.output_dir / "pure_react" / phase / f"case_{case.case_id}"
        fixed_tools = set(self.config.fixed_tool_names)
        available_specs = [
            tool for tool in list_builtin_tools()
            if not fixed_tools or tool.name in fixed_tools
        ]
        if available_specs:
            tool_lines = [
                f"  - {tool.name}: {tool.description} | applies when: {tool.applicability} | usage: {tool.usage_example}"
                for tool in available_specs
            ]
            tool_definitions = "Use: python -m tools <tool_name> [args]\n\nAvailable tools:\n" + "\n".join(tool_lines)
        else:
            tool_definitions = "Use: python -m tools <tool_name> [args]\n\nNo learned tools available yet."
        return ReActAgent(
            client=self.vlm_client,
            config=AgentConfig(max_turns=20, work_dir=work_dir),
            tool_definitions=tool_definitions,
            extra_instructions="",
        )

    def _run_toolpool_prompt_baseline(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            loop = self._make_online_loop(capability_mode="skill_only_same_tools")
            try:
                result, chain_trace = self._run_with_learned_capabilities(
                    loop,
                    case,
                    phase=f"toolpool_prompt_baseline_{index}",
                    capability_mode="skill_only_same_tools",
                    use_skill=False,
                )
            except Exception as exc:
                result = self._runtime_failure_result(case, exc)
                chain_trace = []
            record = self._record_from_agent_result(
                setting="toolpool_prompt_baseline",
                split=self.config.evolve_split,
                case=case,
                result=result,
                correct=self._check_answer(result.final_answer, case),
                chain_trace=chain_trace,
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_with_learned_capabilities(
        self,
        loop: EvolutionLoop,
        case: TaskCase,
        phase: str,
        force_skill: bool = False,
        capability_mode: str = "persistent_tools",
        use_skill: bool = True,
    ) -> tuple[AgentResult, list[str]]:
        skill = loop.store.get_skill(case.capability_family()) if use_skill else None
        required_skill_name = self._forced_skill_name(case) if force_skill and skill is not None else None
        create_agent_kwargs = {"attempt": 1, "phase": phase}
        create_agent_signature = inspect.signature(loop._create_agent)
        if "include_learned_skills" in create_agent_signature.parameters:
            create_agent_kwargs["include_learned_skills"] = use_skill
        if "include_learned_tools" in create_agent_signature.parameters:
            create_agent_kwargs["include_learned_tools"] = bool(use_skill and capability_mode != "skill_only_same_tools")
        if "required_skill_name" in create_agent_signature.parameters:
            # When using a manually-specified capability_root (baseline mode), don't inject the
            # blocking "don't complete before SOP steps" enforcement text. The skill SOP is still
            # visible via include_learned_skills; we just don't force it.
            skill_name_for_enforcement = required_skill_name if self.config.capability_root is None else None
            create_agent_kwargs["required_skill_name"] = skill_name_for_enforcement
        if "require_bash_action_before_complete" in create_agent_signature.parameters:
            enforce_bash = bool(required_skill_name) and self.config.capability_root is None
            create_agent_kwargs["require_bash_action_before_complete"] = enforce_bash
        if "required_image_artifact_before_complete" in create_agent_signature.parameters:
            create_agent_kwargs["required_image_artifact_before_complete"] = bool(required_skill_name and capability_mode == "scratch_code_skill")
        agent = loop._create_agent(case, **create_agent_kwargs)
        if hasattr(loop, "_tool_availability_snapshot") and hasattr(loop, "_usable_skill_content"):
            capability_snapshot = loop._tool_availability_snapshot()
            skill_content = loop._usable_skill_content(skill, capability_snapshot)
        else:
            skill_content = skill.content if skill else None
        chain_context = loop.validator.build_chain_context(
            case,
            skill_content,
            attempt=1,
        )
        try:
            result = agent.run(
                case.prompt,
                case.image_path,
                initial_observations=loop._chain_observations_for_agent(chain_context),
            )
        except Exception as exc:
            result = self._runtime_failure_result(case, exc)
        return result, list(chain_context.tool_sequence)

    @staticmethod
    def _runtime_failure_result(case: TaskCase, exc: Exception) -> AgentResult:
        return AgentResult(
            task=case.prompt,
            final_answer="",
            steps=[AgentStep(turn=1, observation=f"RUNTIME_ERROR: {exc}", is_format_error=True)],
            total_turns=1,
            success=False,
            error=str(exc),
            all_artifacts=[],
        )

    def _make_online_loop(self, capability_mode: str = "persistent_tools") -> EvolutionLoop:
        return EvolutionLoop(
            work_dir=self.output_dir / ("scratch_skill_train_adaptive" if capability_mode == "scratch_code_skill" else "agent_train_adaptive"),
            learned_dir=self.learned_root,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=self.config.max_attempts,
            subset_id=self.config.subset_id,
            answer_checker=self._check_answer,
            capability_mode=capability_mode,
            fixed_builtin_tools=self.config.fixed_tool_names,
            disable_generated_tools=self.config.disable_generated_tools,
        )

    def _make_frozen_loop(
        self,
        snapshot_name: str | None = None,
        subset_id: str | None = None,
        capability_mode: str = "persistent_tools",
    ) -> EvolutionLoop:
        if snapshot_name:
            snapshot_root = self.learned_root / (subset_id or self.config.subset_id) / "snapshots"
            snapshot_dir = snapshot_root / snapshot_name
            if not snapshot_dir.exists():
                legacy_root = self.learned_root / "snapshots"
                legacy_dir = legacy_root / snapshot_name
                if not legacy_dir.exists():
                    # Fall back to capability_root when snapshot doesn't exist and root is specified.
                    if self.config.capability_root is not None:
                        snapshot_dir = self.config.capability_root
                    else:
                        raise FileNotFoundError(f"Frozen snapshot not found: {snapshot_dir}")
                else:
                    snapshot_root = legacy_root
                    snapshot_dir = legacy_dir
            return EvolutionLoop(
                work_dir=self.output_dir / ("scratch_skill_frozen_inference" if capability_mode == "scratch_code_skill" else "frozen_inference"),
                learned_dir=snapshot_dir,
                skills_dir=self.skills_dir,
                vlm_client=self.vlm_client,
                max_attempts=1,
                subset_id=None,
                answer_checker=self._check_answer,
                capability_mode=capability_mode,
                fixed_builtin_tools=self.config.fixed_tool_names,
                disable_generated_tools=self.config.disable_generated_tools,
            )

        # If capability_root is explicitly specified, use it directly.
        if self.config.capability_root is not None:
            return EvolutionLoop(
                work_dir=self.output_dir / ("scratch_skill_frozen_inference" if capability_mode == "scratch_code_skill" else "frozen_inference"),
                learned_dir=self.config.capability_root,
                skills_dir=self.skills_dir,
                vlm_client=self.vlm_client,
                max_attempts=1,
                subset_id=None,
                answer_checker=self._check_answer,
                capability_mode=capability_mode,
                fixed_builtin_tools=self.config.fixed_tool_names,
                disable_generated_tools=self.config.disable_generated_tools,
            )

        active_dir = self.learned_root / (subset_id or self.config.subset_id) / "active"
        learned_dir = active_dir if active_dir.exists() else self.learned_root
        resolved_subset_id = None if active_dir.exists() else (subset_id or self.config.subset_id)
        return EvolutionLoop(
            work_dir=self.output_dir / ("scratch_skill_frozen_inference" if capability_mode == "scratch_code_skill" else "frozen_inference"),
            learned_dir=learned_dir,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=1,
            subset_id=resolved_subset_id,
            answer_checker=self._check_answer,
            capability_mode=capability_mode,
            fixed_builtin_tools=self.config.fixed_tool_names,
            disable_generated_tools=self.config.disable_generated_tools,
        )

    def _forced_skill_name(self, case: TaskCase) -> str | None:
        configured = (self.config.forced_skill_name or "").strip()
        return configured or case.capability_family()

    def _check_answer(self, answer: str, case: TaskCase) -> bool:
        adapter = self.adapters.get(case.dataset_name()) or get_benchmark_adapter(case.dataset_name(), client=self.vlm_client)
        return adapter.check_answer(answer, case)

    def _score_answer(self, answer: str, case: TaskCase) -> float:
        adapter = self.adapters.get(case.dataset_name()) or get_benchmark_adapter(case.dataset_name(), client=self.vlm_client)
        return adapter.score_answer(answer, case)

    @staticmethod
    def _frozen_setting_name(capability_mode: str, force_skill: bool, use_skill: bool = True) -> str:
        if capability_mode == "skill_only_same_tools":
            return "same_tool_preset_tools_only" if not use_skill else "skill_only_frozen_inference"
        if capability_mode == "scratch_code_skill":
            return "scratch_skill_frozen_forced" if force_skill else "scratch_skill_frozen_inference"
        if not use_skill:
            return "preset_tools_only"
        return "frozen_inference_forced_skill" if force_skill else "frozen_inference"

    def _annotate_scratch_record(self, record: StructuredCaseRecord, result: AgentResult, capability_mode: str) -> None:
        if capability_mode != "scratch_code_skill":
            return
        record.scratch_code_triggered = any(step.action is not None and step.action.name == "bash" for step in result.steps)
        record.scratch_artifact_paths = result.get_image_artifacts()
        record.scratch_code_success = bool(record.scratch_artifact_paths)
        record.code_writing_skill_used = True
        record.edited_artifact_judged_useful = bool(record.correct and record.scratch_artifact_paths)
        record.scratch_script_summary = _extract_scratch_script_summary(result)

    def _append_record(self, record: StructuredCaseRecord) -> None:
        with self.records_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _replace_records_for_setting(self, setting: str, split: str, records: list[StructuredCaseRecord]) -> None:
        existing = self._load_existing_records()
        kept = [row for row in existing if not (row.setting == setting and row.split == split)]
        rows = kept + records
        self.records_path.parent.mkdir(parents=True, exist_ok=True)
        self.records_path.write_text(
            "".join(json.dumps(asdict(row), ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def _checkpoint_agent_train_adaptive(
        self,
        cases: list[TaskCase],
        baseline_records: list[TrainSetEvalRecord],
        current_records: list[TrainSetEvalRecord],
        round_results: list[CandidateEvalResult],
        snapshot_name: str,
    ) -> None:
        records = self._materialize_agent_train_records(cases, baseline_records, current_records, round_results)
        self.last_subset_rounds = [asdict(item) for item in round_results]
        self._replace_records_for_setting("agent_train_adaptive", self.config.evolve_split, records)
        self._write_summary(self._load_existing_records(), snapshot_name=snapshot_name or self._existing_snapshot_name())

    def _materialize_agent_train_records(
        self,
        cases: list[TaskCase],
        baseline_records: list[TrainSetEvalRecord],
        final_records: list[TrainSetEvalRecord],
        round_results: list[CandidateEvalResult],
        setting: str = "agent_train_adaptive",
    ) -> list[StructuredCaseRecord]:
        baseline_map = {row.case_id: row for row in baseline_records}
        final_map = {row.case_id: row for row in final_records}
        evolved = bool(round_results)
        records: list[StructuredCaseRecord] = []
        for case in cases:
            baseline = baseline_map[case.case_id]
            final = final_map[case.case_id]
            tool_names = _merge_tool_names(list(final.tool_names), list(final.chain_trace))
            record = StructuredCaseRecord(
                setting=setting,
                split=self.config.evolve_split,
                case_id=case.case_id,
                problem_id=case.problem_id,
                expected=case.gold_answer,
                answer=final.answer,
                correct=final.correct,
                score=final.score,
                turns=final.turns,
                tool_count=len(tool_names),
                tool_names=tool_names,
                used_tool=bool(tool_names),
                artifact_paths=list(final.artifact_paths),
                chain_trace=list(final.chain_trace),
                image_path=case.image_path,
                metadata=dict(case.metadata),
            )
            record.initial_answer = baseline.answer
            record.initial_correct = baseline.correct
            record.full_agent_answer = baseline.answer
            record.full_agent_correct = baseline.correct
            record.post_evolve_answer = final.answer
            record.post_evolve_correct = final.correct
            record.evolve_triggered = evolved and not baseline.correct
            record.evolve_success = final.correct if record.evolve_triggered else True
            records.append(record)
        return records

    def rebuild_summary(self, snapshot_name: str | None = None) -> dict[str, Any]:
        records = self._load_existing_records()
        if snapshot_name is None:
            snapshot_name = self._existing_snapshot_name()
        return self._write_summary(records, snapshot_name=snapshot_name or "")

    def _write_summary(self, records: list[StructuredCaseRecord], snapshot_name: str) -> dict[str, Any]:
        settings_summary = _aggregate_records(records)
        vlm_base_url = os.environ.get("VLM_BASE_URL", "").strip() or os.environ.get("OPENAI_BASE_URL", "").strip()
        vlm_model = os.environ.get("VLM_MODEL", "").strip() or os.environ.get("OPENAI_MODEL", "").strip()
        vlm_api_style = os.environ.get("VLM_API_STYLE", "").strip()
        summary = {
            "config": {
                "dataset": self.config.dataset,
                "datasets": self._configured_datasets(),
                "raw_data_root": str(self.config.raw_data_root),
                "normalized_data_root": str(self.config.normalized_data_root),
                "subset_id": self.config.subset_id,
                "evolve_split": self.config.evolve_split,
                "held_out_split": self.config.held_out_split,
                "k": self.config.k,
                "train_subset_size": self.config.train_subset_size,
                "held_out_limit": self.config.held_out_limit,
                "max_attempts": self.config.max_attempts,
                "max_planning_rounds": self.config.max_planning_rounds,
                "families_per_round_limit": self.config.families_per_round_limit,
                "representatives_per_cluster": self.config.representatives_per_cluster,
                "tool_preference": self.config.tool_preference,
                "readability_judge_enabled": self.config.readability_judge_enabled,
                "forced_skill_name": self.config.forced_skill_name,
                "fixed_tool_names": list(self.config.fixed_tool_names),
                "disable_generated_tools": self.config.disable_generated_tools,
                "vlm_base_url": vlm_base_url,
                "vlm_model": vlm_model,
                "vlm_api_style": vlm_api_style,
                "vlm_api_key_present": bool(os.environ.get("VLM_API_KEY") or os.environ.get("OPENAI_API_KEY")),
                "vlm_user_id_present": bool(os.environ.get("VLM_USER_ID")),
                "vlm_access_key_present": bool(os.environ.get("VLM_ACCESS_KEY")),
                "vlm_quota_id_present": bool(os.environ.get("VLM_QUOTA_ID")),
                "uses_alibaba_chat_api": (
                    vlm_api_style.lower() == "alibaba_chat"
                    or "llm-chat-api.alibaba-inc.com" in vlm_base_url.lower()
                ),
                "gta_tool_mode": os.environ.get("VISION_AGENT_GTA_TOOL_MODE", ""),
                "gta_tool_server": os.environ.get("VISION_AGENT_GTA_TOOL_SERVER", ""),
                "gta_official_repo": os.environ.get("VISION_AGENT_GTA_OFFICIAL_REPO", ""),
                "gta_device": os.environ.get("VISION_AGENT_GTA_DEVICE", ""),
                "serper_api_key_present": bool(os.environ.get("SERPER_API_KEY")),
                "mathpix_app_id_present": bool(os.environ.get("MATHPIX_APP_ID")),
                "mathpix_app_key_present": bool(os.environ.get("MATHPIX_APP_KEY")),
            },
            "snapshot_name": snapshot_name,
            "records_path": str(self.records_path),
            "subset_evolution_rounds": self.last_subset_rounds,
            "settings": settings_summary,
            "full_agent_accuracy": settings_summary.get("agent_train_adaptive", {}).get("full_agent_accuracy", 0.0),
            "post_evolve_recovery_accuracy": settings_summary.get("agent_train_adaptive", {}).get("post_evolve_recovery_accuracy", 0.0),
            "skill_only_full_agent_accuracy": settings_summary.get("skill_only_train_adaptive", {}).get("full_agent_accuracy", 0.0),
            "skill_only_post_evolve_recovery_accuracy": settings_summary.get("skill_only_train_adaptive", {}).get("post_evolve_recovery_accuracy", 0.0),
            "preset_tools_only_accuracy": settings_summary.get("preset_tools_only", {}).get("accuracy", 0.0),
            "same_tool_preset_tools_only_accuracy": settings_summary.get("same_tool_preset_tools_only", {}).get("accuracy", 0.0),
            "reasoned_vlm_accuracy": settings_summary.get("reasoned_vlm", {}).get("accuracy", 0.0),
            "function_calling_vqa_accuracy": settings_summary.get("function_calling_vqa", {}).get("accuracy", 0.0),
            "frozen_inference_accuracy": settings_summary.get("frozen_inference", {}).get("accuracy", 0.0),
            "skill_only_frozen_inference_accuracy": settings_summary.get("skill_only_frozen_inference", {}).get("accuracy", 0.0),
            "forced_skill_frozen_accuracy": settings_summary.get("frozen_inference_forced_skill", {}).get("accuracy", 0.0),
            "scratch_skill_full_agent_accuracy": settings_summary.get("scratch_skill_train_adaptive", {}).get("full_agent_accuracy", 0.0),
            "scratch_skill_post_evolve_recovery_accuracy": settings_summary.get("scratch_skill_train_adaptive", {}).get("post_evolve_recovery_accuracy", 0.0),
            "scratch_skill_frozen_accuracy": settings_summary.get("scratch_skill_frozen_inference", {}).get("accuracy", 0.0),
            "scratch_skill_forced_accuracy": settings_summary.get("scratch_skill_frozen_forced", {}).get("accuracy", 0.0),
            "forced_skill_fc_accuracy": settings_summary.get("frozen_inference_fc_forced_skill", {}).get("accuracy", 0.0),
        }
        self.summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def _reset_evolve_reports_file(self) -> None:
        """Reset the single-file evolve report artifact for a fresh run."""
        self.evolve_reports_path.write_text("[]\n", encoding="utf-8")

    def _save_evolve_reports(self, reports: list[dict[str, Any]]) -> None:
        """Persist detailed evolve reports for the first N evolved cases into one file."""
        self.evolve_reports_path.write_text(
            json.dumps(reports, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_existing_records(self) -> list[StructuredCaseRecord]:
        if not self.records_path.exists():
            return []
        rows: list[StructuredCaseRecord] = []
        for line in self.records_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            rows.append(StructuredCaseRecord(**payload))
        return rows

    def _existing_records_by_case(self, setting: str, split: str) -> dict[str, StructuredCaseRecord]:
        rows = self._load_existing_records()
        by_case: dict[str, StructuredCaseRecord] = {}
        for row in rows:
            if row.setting != setting or row.split != split:
                continue
            if not _record_is_resume_eligible(row):
                continue
            by_case[row.case_id] = row
        return by_case

    def _existing_snapshot_name(self) -> str:
        if not self.summary_path.exists():
            return ""
        try:
            payload = json.loads(self.summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        return str(payload.get("snapshot_name", "") or "")


def _extract_tool_names(result: AgentResult) -> list[str]:
    tool_names: list[str] = []
    pattern = re.compile(r"\bpython(?:3)?\s+-m\s+tools\s+([a-zA-Z0-9_]+)\b")
    for step in result.steps:
        if step.action is None:
            continue
        if step.action.name == "bash":
            command = str(step.action.arguments.get("command", ""))
            match = pattern.search(command)
            if not match:
                continue
            tool_name = match.group(1)
        else:
            tool_name = str(step.action.name or "").strip()
            if not tool_name:
                continue
        if tool_name not in tool_names:
            tool_names.append(tool_name)
    return tool_names


def _merge_tool_names(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for name in group:
            if name and name not in merged:
                merged.append(name)
    return merged


def _extract_scratch_script_summary(result: AgentResult) -> str | None:
    commands: list[str] = []
    for step in result.steps:
        if step.action is None or step.action.name != "bash":
            continue
        command = str(step.action.arguments.get("command", "")).strip()
        if not command or "python -m tools" in command:
            continue
        compact = " ".join(command.split())
        commands.append(compact[:240])
    if not commands:
        return None
    return " | ".join(commands[:2])


def _merge_record_metadata(metadata: dict[str, Any], runtime_error: str | None) -> dict[str, Any]:
    payload = dict(metadata)
    if runtime_error:
        payload["runtime_error"] = runtime_error
    return payload


def _record_is_resume_eligible(record: StructuredCaseRecord) -> bool:
    runtime_error = str(record.metadata.get("runtime_error", "") or "").strip()
    if runtime_error:
        return False
    if not str(record.answer or "").strip():
        return False
    return True


def _aggregate_records(records: list[StructuredCaseRecord]) -> dict[str, Any]:
    grouped: dict[str, list[StructuredCaseRecord]] = {}
    for record in records:
        grouped.setdefault(record.setting, []).append(record)

    summary: dict[str, Any] = {}
    for setting, rows in grouped.items():
        correct = sum(1 for row in rows if row.correct)
        total_score = sum(_record_score(row) for row in rows)
        tool_used = sum(1 for row in rows if row.used_tool)
        artifact_rows = [row for row in rows if row.artifact_paths]
        judged = [row for row in rows if row.overall_usefulness is not None]
        full_agent_rows = [row for row in rows if row.full_agent_correct is not None]
        post_evolve_rows = [row for row in rows if row.post_evolve_correct is not None]
        scratch_rows = [row for row in rows if row.scratch_code_triggered is not None]
        per_dataset_accuracy = _group_accuracy(rows, key_name="dataset_name")
        per_family_accuracy = _group_accuracy(rows, key_name="capability_family")
        summary[setting] = {
            "split": rows[0].split if rows else "",
            "total": len(rows),
            "correct": correct,
            "accuracy": (total_score / len(rows)) if rows else 0.0,
            "per_dataset_accuracy": per_dataset_accuracy,
            "per_family_accuracy": per_family_accuracy,
            "full_agent_accuracy": (
                sum(1 for row in full_agent_rows if row.full_agent_correct) / len(full_agent_rows)
                if full_agent_rows else 0.0
            ),
            "post_evolve_recovery_accuracy": (
                sum(1 for row in post_evolve_rows if row.post_evolve_correct) / len(post_evolve_rows)
                if post_evolve_rows else 0.0
            ),
            "scratch_code_rate": (
                sum(1 for row in scratch_rows if row.scratch_code_triggered) / len(scratch_rows)
                if scratch_rows else 0.0
            ),
            "scratch_code_success_rate": (
                sum(1 for row in scratch_rows if row.scratch_code_success) / len(scratch_rows)
                if scratch_rows else 0.0
            ),
            "tool_usage_rate": (tool_used / len(rows)) if rows else 0.0,
            "avg_tool_calls_per_case": (
                sum(row.tool_count for row in rows) / len(rows)
                if rows else 0.0
            ),
            "artifact_production_rate": (len(artifact_rows) / len(rows)) if rows else 0.0,
            "readability_summary": {
                "judged_cases": len(judged),
                "readability_improved_rate": (
                    sum(1 for row in judged if row.readability_improved == "yes") / len(judged)
                    if judged else 0.0
                ),
                "avg_target_region_clearer": _avg(
                    [row.target_region_clearer for row in judged if row.target_region_clearer is not None]
                ),
                "avg_text_or_marks_more_legible": _avg(
                    [
                        row.text_or_marks_more_legible
                        for row in judged
                        if row.text_or_marks_more_legible is not None
                    ]
                ),
                "avg_overall_usefulness": _avg(
                    [row.overall_usefulness for row in judged if row.overall_usefulness is not None]
                ),
                "manual_spotcheck_case_ids": _spotcheck_case_ids(judged),
            },
        }
    return summary


def _avg(values: list[int]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _group_accuracy(rows: list[StructuredCaseRecord], key_name: str) -> dict[str, float]:
    grouped: dict[str, list[StructuredCaseRecord]] = {}
    for row in rows:
        value = str(row.metadata.get(key_name, row.problem_id if key_name == "capability_family" else "")).strip()
        if not value and key_name == "dataset_name":
            value = row.problem_id
        grouped.setdefault(value, []).append(row)
    return {
        key: (sum(_record_score(row) for row in group) / len(group))
        for key, group in grouped.items()
        if key
    }


def _record_score(row: StructuredCaseRecord) -> float:
    if row.score is not None:
        return float(row.score)
    return 1.0 if row.correct else 0.0


def _spotcheck_case_ids(rows: list[StructuredCaseRecord], limit: int = 10) -> list[str]:
    ordered = sorted(
        rows,
        key=lambda row: hashlib.sha1(f"{row.setting}:{row.case_id}".encode("utf-8")).hexdigest(),
    )
    return [row.case_id for row in ordered[:limit]]


def _extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _normalize_yes_no(value: Any) -> str | None:
    text = str(value).strip().lower()
    if text in {"yes", "no"}:
        return text
    return None


def _clamp_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(5, score))


def _extract_final_answer_text(text: str) -> str:
    match = re.search(r"Final answer:\s*(.+)$", text or "", re.IGNORECASE | re.MULTILINE)
    if match:
        return match.group(1).strip()
    return (text or "").strip()
