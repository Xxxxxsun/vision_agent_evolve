"""Benchmark adapter registry for subset-level evolution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.structured_data import check_chartqa_case_answer, load_json_objects, load_normalized_cases
from core.types import AgentResult, TaskCase


class BenchmarkAdapter(Protocol):
    """Interface implemented by dataset-specific adapters."""

    dataset_name: str

    def load_cases(
        self,
        normalized_data_root: Path,
        split: str,
        limit: int = 0,
    ) -> list[TaskCase]:
        """Load normalized benchmark cases."""

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        """Return whether the answer is correct for the given case."""

    def score_records(self, records: list[dict]) -> float:
        """Compute the primary score for a full evaluation pass."""

    def summarize_case(self, case: TaskCase, result: AgentResult, correct: bool) -> dict[str, str]:
        """Return a compact planner-facing case summary."""

    def build_family_id(self, case: TaskCase) -> str:
        """Return the capability family identifier for this case."""

    def cluster_key(self, case: TaskCase, result: AgentResult, correct: bool) -> str:
        """Return the failure-cluster key for this case/result pair."""


@dataclass
class GenericJsonlAdapter:
    """Generic adapter for normalized JSONL datasets using TaskCase schema."""

    dataset_name: str

    def load_cases(
        self,
        normalized_data_root: Path,
        split: str,
        limit: int = 0,
    ) -> list[TaskCase]:
        dataset_root = normalized_data_root / self.dataset_name
        split_file = dataset_root / f"{split}.jsonl"
        if split_file.exists():
            cases = load_normalized_cases(normalized_data_root, self.dataset_name, split, limit=limit)
            return [self._ensure_metadata(case, split) for case in cases]

        raw_file = dataset_root / f"{split}.json"
        if not raw_file.exists():
            raise FileNotFoundError(f"Normalized split not found for dataset '{self.dataset_name}': {split_file}")

        cases: list[TaskCase] = []
        for index, item in enumerate(load_json_objects(raw_file), start=1):
            metadata = dict(item.get("metadata") or {})
            metadata.setdefault("dataset_name", self.dataset_name)
            metadata.setdefault("split", split)
            metadata.setdefault("source_id", str(item.get("id", index)))
            metadata.setdefault("capability_family", str(item.get("capability_family", self.dataset_name)))
            cases.append(
                TaskCase(
                    case_id=str(item.get("id", f"{self.dataset_name}_{split}_{index}")),
                    problem_id=str(item.get("problem_id", self.dataset_name)),
                    prompt=str(item.get("prompt", item.get("question", ""))),
                    gold_answer=str(item.get("answer", item.get("gold_answer", ""))),
                    image_path=str(item.get("image_path", "")),
                    metadata=metadata,
                )
            )
            if limit and len(cases) >= limit:
                break
        return cases

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        actual = _normalize_text(answer)
        expected = _normalize_text(case.gold_answer)
        if not actual or not expected:
            return False
        if actual == expected:
            return True

        actual_number = _parse_number(actual)
        expected_number = _parse_number(expected)
        if actual_number is not None and expected_number is not None:
            return abs(actual_number - expected_number) <= 1e-6

        return bool(re.search(rf"(?<![a-z0-9]){re.escape(expected)}(?![a-z0-9])", actual))

    def score_records(self, records: list[dict]) -> float:
        if not records:
            return 0.0
        correct = sum(1 for row in records if row.get("correct"))
        return correct / len(records)

    def summarize_case(self, case: TaskCase, result: AgentResult, correct: bool) -> dict[str, str]:
        return {
            "case_id": case.case_id,
            "dataset_name": case.dataset_name(),
            "capability_family": case.capability_family(),
            "prompt": case.prompt[:220],
            "answer": result.final_answer[:120],
            "expected": case.gold_answer[:120],
            "correct": "yes" if correct else "no",
        }

    def build_family_id(self, case: TaskCase) -> str:
        return case.capability_family()

    def cluster_key(self, case: TaskCase, result: AgentResult, correct: bool) -> str:
        if correct:
            return "correct"
        answer_type = str(case.metadata.get("answer_type", "")).strip() or "generic"
        question_type = str(case.metadata.get("question_type", "")).strip() or "generic"
        return f"{case.capability_family()}::{question_type}::{answer_type}"

    def _ensure_metadata(self, case: TaskCase, split: str) -> TaskCase:
        metadata = dict(case.metadata)
        metadata.setdefault("dataset_name", self.dataset_name)
        metadata.setdefault("split", split)
        metadata.setdefault("source_id", case.case_id)
        metadata.setdefault("capability_family", metadata.get("dataset_name", self.dataset_name))
        case.metadata = metadata
        return case


class ChartQAAdapter(GenericJsonlAdapter):
    """ChartQA-specific scoring and answer checking."""

    def __init__(self) -> None:
        super().__init__(dataset_name="chartqa")

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        return check_chartqa_case_answer(answer, case)

    def cluster_key(self, case: TaskCase, result: AgentResult, correct: bool) -> str:
        if correct:
            return "correct"
        question_type = str(case.metadata.get("question_type", "")).strip() or "generic"
        answer_type = str(case.metadata.get("answer_type", "")).strip() or "string"
        tool_count = sum(1 for step in result.steps if step.action is not None and step.action.name == "bash")
        tool_bucket = "tool" if tool_count else "no_tool"
        return f"{case.capability_family()}::{question_type}::{answer_type}::{tool_bucket}"


class VStarAdapter(GenericJsonlAdapter):
    """Registration point for V* style datasets."""

    def __init__(self) -> None:
        super().__init__(dataset_name="vstar")


class HRBenchAdapter(GenericJsonlAdapter):
    """Registration point for HRBench."""

    def __init__(self) -> None:
        super().__init__(dataset_name="hrbench")


def get_benchmark_adapter(dataset_name: str) -> BenchmarkAdapter:
    """Return the adapter registered for the given dataset."""
    normalized = dataset_name.strip().lower()
    registry: dict[str, BenchmarkAdapter] = {
        "chartqa": ChartQAAdapter(),
        "vstar": VStarAdapter(),
        "v*": VStarAdapter(),
        "hrbench": HRBenchAdapter(),
    }
    if normalized in registry:
        return registry[normalized]
    return GenericJsonlAdapter(dataset_name=normalized)


def available_benchmark_datasets() -> list[str]:
    """Return the known dataset names for CLI choices/help."""
    return ["chartqa", "hrbench", "vstar"]


def _normalize_text(value: str) -> str:
    cleaned = str(value).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _parse_number(value: str) -> float | None:
    text = value.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None
