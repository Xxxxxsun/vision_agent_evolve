"""Structured benchmark runner for ChartQA-style experiments."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.agent import AgentConfig, ReActAgent
from core.structured_data import check_chartqa_case_answer, load_normalized_cases
from core.types import AgentResult, TaskCase
from core.vlm_client import ModelSettings, VLMClient
from evolution.loop import EvolutionLoop


@dataclass
class StructuredExperimentConfig:
    """Configuration for the structured benchmark experiment."""

    dataset: str
    raw_data_root: Path
    normalized_data_root: Path
    subset_id: str
    evolve_split: str = "train"
    held_out_split: str = "val"
    k: int = 200
    max_attempts: int = 10
    readability_judge_enabled: bool = False
    settings: list[str] = field(default_factory=lambda: ["direct_vlm", "pure_react", "online_evolve", "frozen_transfer"])
    save_first_n_evolves: int = 10


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
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(path.suffix.lower(), "image/png")
        image_data = base64.b64encode(path.read_bytes()).decode("utf-8")
        return f"data:{mime};base64,{image_data}"


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
        self.readability_judge = (
            ReadabilityJudge(self.vlm_client, project_root)
            if config.readability_judge_enabled
            else None
        )

    def run_experiment(self) -> dict[str, Any]:
        """Run direct, pure-react, online-evolve, and frozen-transfer settings."""
        evolve_cases = load_normalized_cases(
            self.config.normalized_data_root,
            self.config.dataset,
            self.config.evolve_split,
            limit=self.config.k,
        )
        held_out_cases = load_normalized_cases(
            self.config.normalized_data_root,
            self.config.dataset,
            self.config.held_out_split,
        )

        self.records_path.write_text("", encoding="utf-8")
        if "online_evolve" in self.config.settings:
            self._reset_evolve_reports_file()
        records: list[StructuredCaseRecord] = []
        snapshot_name = ""

        if "direct_vlm" in self.config.settings:
            print(f"=== Direct VLM baseline on {self.config.evolve_split}[:{self.config.k}] ===")
            records.extend(self._run_direct_vlm(evolve_cases))

        if "pure_react" in self.config.settings:
            print(f"\n=== Pure ReAct baseline on {self.config.evolve_split}[:{self.config.k}] ===")
            records.extend(self._run_pure_react(evolve_cases))

        if "online_evolve" in self.config.settings:
            print(f"\n=== Online evolve on {self.config.evolve_split}[:{self.config.k}] ===")
            online_records, snapshot_name = self._run_online_evolve(evolve_cases)
            records.extend(online_records)

        if "frozen_transfer" in self.config.settings:
            print(f"\n=== Frozen transfer on {self.config.held_out_split} ===")
            if not snapshot_name:
                snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
            records.extend(self.run_frozen_transfer(snapshot_name=snapshot_name, cases=held_out_cases))

        summary = self._write_summary(records, snapshot_name=snapshot_name)
        return summary

    def run_frozen_transfer(
        self,
        snapshot_name: str | None = None,
        subset_id: str | None = None,
        cases: list[TaskCase] | None = None,
    ) -> list[StructuredCaseRecord]:
        """Evaluate a frozen subset or snapshot without further mutations."""
        held_out_cases = cases or load_normalized_cases(
            self.config.normalized_data_root,
            self.config.dataset,
            self.config.held_out_split,
        )
        loop = self._make_frozen_loop(snapshot_name=snapshot_name, subset_id=subset_id)

        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(held_out_cases, start=1):
            result, chain_trace = self._run_with_learned_capabilities(
                loop,
                case,
                phase=f"frozen_transfer_{index}",
            )
            record = self._record_from_agent_result(
                setting="frozen_transfer",
                split=self.config.held_out_split,
                case=case,
                result=result,
                correct=check_chartqa_case_answer(result.final_answer, case),
                chain_trace=chain_trace,
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(held_out_cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_direct_vlm(self, cases: list[TaskCase]) -> list[StructuredCaseRecord]:
        records: list[StructuredCaseRecord] = []
        for index, case in enumerate(cases, start=1):
            answer = self._direct_answer(case)
            record = StructuredCaseRecord(
                setting="direct_vlm",
                split=self.config.evolve_split,
                case_id=case.case_id,
                problem_id=case.problem_id,
                expected=case.gold_answer,
                answer=answer,
                correct=check_chartqa_case_answer(answer, case),
                turns=1,
                tool_count=0,
                tool_names=[],
                used_tool=False,
                artifact_paths=[],
                image_path=case.image_path,
                metadata=dict(case.metadata),
            )
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
            result = agent.run(case.prompt, case.image_path, initial_observations=[])
            record = self._record_from_agent_result(
                setting="pure_react",
                split=self.config.evolve_split,
                case=case,
                result=result,
                correct=check_chartqa_case_answer(result.final_answer, case),
                chain_trace=[],
            )
            self._append_record(record)
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] "
                f"{'OK' if record.correct else 'FAIL'} case={case.case_id} answer={record.answer!r}"
            )
        return records

    def _run_online_evolve(self, cases: list[TaskCase]) -> tuple[list[StructuredCaseRecord], str]:
        loop = self._make_online_loop()
        records: list[StructuredCaseRecord] = []
        saved_evolve_reports = 0
        collected_reports: list[dict[str, Any]] = []

        for index, case in enumerate(cases, start=1):
            initial_result, initial_chain = self._run_with_learned_capabilities(
                loop,
                case,
                phase=f"online_precheck_{index}",
            )
            initial_correct = check_chartqa_case_answer(initial_result.final_answer, case)

            if initial_correct:
                final_result = initial_result
                final_chain = initial_chain
                evolve_triggered = False
                evolve_success = True
            else:
                evolve_triggered = True
                evolve_success = loop.run_single_case(case)
                if saved_evolve_reports < self.config.save_first_n_evolves:
                    report = dict(loop.last_case_report or {})
                    report["ordinal"] = saved_evolve_reports + 1
                    collected_reports.append(report)
                    self._save_evolve_reports(collected_reports)
                    saved_evolve_reports += 1
                final_result, final_chain = self._run_with_learned_capabilities(
                    loop,
                    case,
                    phase=f"online_post_{index}",
                )

            record = self._record_from_agent_result(
                setting="online_evolve",
                split=self.config.evolve_split,
                case=case,
                result=final_result,
                correct=check_chartqa_case_answer(final_result.final_answer, case),
                chain_trace=final_chain,
            )
            record.initial_answer = initial_result.final_answer
            record.initial_correct = initial_correct
            record.evolve_triggered = evolve_triggered
            record.evolve_success = evolve_success
            self._append_record(record)
            records.append(record)

            status = "OK" if record.correct else "FAIL"
            extra = " skipped-evolve" if not evolve_triggered else " evolved"
            print(
                f"[{index:03d}/{len(cases):03d}] {status}{extra} "
                f"case={case.case_id} answer={record.answer!r}"
            )

        snapshot_name = f"{self.config.subset_id}_{self.config.evolve_split}_k{self.config.k}_snapshot"
        loop.store.snapshot_current_capabilities(snapshot_name)
        return records, snapshot_name

    def _record_from_agent_result(
        self,
        setting: str,
        split: str,
        case: TaskCase,
        result: AgentResult,
        correct: bool,
        chain_trace: list[str],
    ) -> StructuredCaseRecord:
        tool_names = _extract_tool_names(result)
        artifacts = result.get_image_artifacts()
        readability = None
        if self.readability_judge is not None and artifacts:
            readability = self.readability_judge.judge(case, artifacts[-1])

        return StructuredCaseRecord(
            setting=setting,
            split=split,
            case_id=case.case_id,
            problem_id=case.problem_id,
            expected=case.gold_answer,
            answer=result.final_answer,
            correct=correct,
            turns=result.total_turns,
            tool_count=len(tool_names),
            tool_names=tool_names,
            used_tool=bool(tool_names),
            artifact_paths=artifacts,
            chain_trace=chain_trace,
            image_path=case.image_path,
            metadata=dict(case.metadata),
            readability_improved=None if readability is None else readability.get("readability_improved"),
            target_region_clearer=None if readability is None else readability.get("target_region_clearer"),
            text_or_marks_more_legible=None if readability is None else readability.get("text_or_marks_more_legible"),
            overall_usefulness=None if readability is None else readability.get("overall_usefulness"),
            readability_notes=None if readability is None else readability.get("readability_notes"),
        )

    def _direct_answer(self, case: TaskCase) -> str:
        prompt = (
            "Answer the chart question directly from the image.\n"
            "Return only the final short answer with no explanation.\n\n"
            f"Question: {case.prompt}"
        )
        messages = [
            {
                "role": "user",
                "content": VLMClient.image_message_parts(case.image_path, prompt),
            }
        ]
        response, _ = self.vlm_client.chat(messages, ModelSettings(temperature=0.0, max_tokens=200))
        return response.strip()

    def _create_plain_react_agent(self, case: TaskCase, phase: str) -> ReActAgent:
        work_dir = self.output_dir / "pure_react" / phase / f"case_{case.case_id}"
        return ReActAgent(
            client=self.vlm_client,
            config=AgentConfig(max_turns=20, work_dir=work_dir),
            tool_definitions="Use: python -m tools <tool_name> [args]\n\nNo learned tools available yet.",
            extra_instructions="",
        )

    def _run_with_learned_capabilities(
        self,
        loop: EvolutionLoop,
        case: TaskCase,
        phase: str,
    ) -> tuple[AgentResult, list[str]]:
        agent = loop._create_agent(case, attempt=1, phase=phase)
        skill = loop.store.get_skill(case.problem_id)
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
        result = agent.run(
            case.prompt,
            case.image_path,
            initial_observations=loop._chain_observations_for_agent(chain_context),
        )
        return result, list(chain_context.tool_sequence)

    def _make_online_loop(self) -> EvolutionLoop:
        return EvolutionLoop(
            work_dir=self.output_dir / "online_evolve",
            learned_dir=self.learned_root,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=self.config.max_attempts,
            subset_id=self.config.subset_id,
            answer_checker=check_chartqa_case_answer,
        )

    def _make_frozen_loop(
        self,
        snapshot_name: str | None = None,
        subset_id: str | None = None,
    ) -> EvolutionLoop:
        if snapshot_name:
            snapshot_root = self.learned_root / "snapshots"
            snapshot_dir = snapshot_root / snapshot_name
            if not snapshot_dir.exists():
                raise FileNotFoundError(f"Frozen snapshot not found: {snapshot_dir}")
            return EvolutionLoop(
                work_dir=self.output_dir / "frozen_transfer",
                learned_dir=snapshot_root,
                skills_dir=self.skills_dir,
                vlm_client=self.vlm_client,
                max_attempts=1,
                subset_id=snapshot_name,
                answer_checker=check_chartqa_case_answer,
            )

        return EvolutionLoop(
            work_dir=self.output_dir / "frozen_transfer",
            learned_dir=self.learned_root,
            skills_dir=self.skills_dir,
            vlm_client=self.vlm_client,
            max_attempts=1,
            subset_id=subset_id or self.config.subset_id,
            answer_checker=check_chartqa_case_answer,
        )

    def _append_record(self, record: StructuredCaseRecord) -> None:
        with self.records_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _write_summary(self, records: list[StructuredCaseRecord], snapshot_name: str) -> dict[str, Any]:
        summary = {
            "config": {
                "dataset": self.config.dataset,
                "raw_data_root": str(self.config.raw_data_root),
                "normalized_data_root": str(self.config.normalized_data_root),
                "subset_id": self.config.subset_id,
                "evolve_split": self.config.evolve_split,
                "held_out_split": self.config.held_out_split,
                "k": self.config.k,
                "max_attempts": self.config.max_attempts,
                "readability_judge_enabled": self.config.readability_judge_enabled,
            },
            "snapshot_name": snapshot_name,
            "records_path": str(self.records_path),
            "settings": _aggregate_records(records),
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


def _extract_tool_names(result: AgentResult) -> list[str]:
    tool_names: list[str] = []
    pattern = re.compile(r"\bpython(?:3)?\s+-m\s+tools\s+([a-zA-Z0-9_]+)\b")
    for step in result.steps:
        if step.action is None or step.action.name != "bash":
            continue
        command = str(step.action.arguments.get("command", ""))
        match = pattern.search(command)
        if not match:
            continue
        tool_name = match.group(1)
        if tool_name not in tool_names:
            tool_names.append(tool_name)
    return tool_names


def _aggregate_records(records: list[StructuredCaseRecord]) -> dict[str, Any]:
    grouped: dict[str, list[StructuredCaseRecord]] = {}
    for record in records:
        grouped.setdefault(record.setting, []).append(record)

    summary: dict[str, Any] = {}
    for setting, rows in grouped.items():
        correct = sum(1 for row in rows if row.correct)
        tool_used = sum(1 for row in rows if row.used_tool)
        artifact_rows = [row for row in rows if row.artifact_paths]
        judged = [row for row in rows if row.overall_usefulness is not None]
        summary[setting] = {
            "split": rows[0].split if rows else "",
            "total": len(rows),
            "correct": correct,
            "accuracy": (correct / len(rows)) if rows else 0.0,
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
