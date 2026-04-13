"""Benchmark adapter registry for subset-level evolution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.structured_data import (
    check_chartqa_case_answer,
    check_mathvista_answer,
    check_textvqa_case_answer,
    check_multiple_choice_answer,
    load_json_objects,
    load_normalized_cases,
    score_mathvista_answer,
    score_multiple_choice_answer,
    score_textvqa_answer,
)
from core.types import AgentResult, TaskCase
from core.vlm_client import ModelSettings, VLMClient


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

    def score_answer(self, answer: str, case: TaskCase) -> float:
        """Return the benchmark score for one answer/case pair."""

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
        return self.score_answer(answer, case) >= 1.0

    def score_answer(self, answer: str, case: TaskCase) -> float:
        actual = _normalize_text(answer)
        expected = _normalize_text(case.gold_answer)
        if not actual or not expected:
            return 0.0
        if actual == expected:
            return 1.0

        actual_number = _parse_number(actual)
        expected_number = _parse_number(expected)
        if actual_number is not None and expected_number is not None:
            return 1.0 if abs(actual_number - expected_number) <= 1e-6 else 0.0

        return 1.0 if re.search(rf"(?<![a-z0-9]){re.escape(expected)}(?![a-z0-9])", actual) else 0.0

    def score_records(self, records: list[dict]) -> float:
        if not records:
            return 0.0
        total = 0.0
        for row in records:
            if row.get("score") is not None:
                total += float(row["score"])
            else:
                total += 1.0 if row.get("correct") else 0.0
        return total / len(records)

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

    def score_answer(self, answer: str, case: TaskCase) -> float:
        return 1.0 if self.check_answer(answer, case) else 0.0

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

    def score_answer(self, answer: str, case: TaskCase) -> float:
        choices = _case_choices(case)
        if not choices:
            return super().score_answer(answer, case)
        return score_multiple_choice_answer(answer, case.gold_answer, choices)

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        choices = _case_choices(case)
        if not choices:
            return super().check_answer(answer, case)
        return check_multiple_choice_answer(answer, case.gold_answer, choices)


class HRBenchAdapter(GenericJsonlAdapter):
    """Registration point for HRBench."""

    def __init__(self) -> None:
        super().__init__(dataset_name="hrbench")

    def score_answer(self, answer: str, case: TaskCase) -> float:
        choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
        if not choices:
            return super().score_answer(answer, case)
        return score_multiple_choice_answer(answer, case.gold_answer, choices)

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
        if not choices:
            return super().check_answer(answer, case)
        return check_multiple_choice_answer(answer, case.gold_answer, choices)


class MathVistaAdapter(GenericJsonlAdapter):
    """MathVista-specific answer checking."""

    def __init__(self, client: VLMClient | None = None) -> None:
        super().__init__(dataset_name="mathvista")
        self.client = client
        self._judge_cache: dict[tuple[str, str, str], bool] = {}

    def score_answer(self, answer: str, case: TaskCase) -> float:
        choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
        precision_value = _coerce_optional_int(case.metadata.get("precision"))
        deterministic = score_mathvista_answer(
            answer,
            case.gold_answer,
            prompt=case.prompt,
            choices=choices,
            answer_type=str(case.metadata.get("answer_type", "")),
            precision=precision_value,
            unit=str(case.metadata.get("unit", "")),
        )
        if deterministic >= 1.0 or choices:
            return deterministic
        if self._judge_freeform_answer(answer, case):
            return 1.0
        return deterministic

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        return self.score_answer(answer, case) >= 1.0

    def _judge_freeform_answer(self, answer: str, case: TaskCase) -> bool:
        actual = str(answer).strip()
        expected = str(case.gold_answer).strip()
        if not actual or not expected or self.client is None:
            return False

        cache_key = (case.case_id, expected, actual)
        if cache_key in self._judge_cache:
            return self._judge_cache[cache_key]

        prompt = (
            "You are a strict MathVista answer judge.\n\n"
            f"Question: {case.prompt}\n"
            f"Expected answer: {expected}\n"
            f"Model answer: {actual}\n"
            f"Answer type: {case.metadata.get('answer_type', '')}\n"
            f"Unit: {case.metadata.get('unit', '')}\n"
            f"Precision: {case.metadata.get('precision', '')}\n\n"
            "Decide whether the model answer should receive full credit.\n"
            "Treat semantically equivalent mathematical answers as correct, including concise rewrites, "
            "equivalent units when explicitly compatible, and answers that contain extra words but clearly commit "
            "to the same final value or expression.\n"
            "Be strict: if the answer changes the mathematical meaning, leaves out required specificity, or adds "
            "unsupported content, mark it incorrect.\n\n"
            "Reply with only one word: CORRECT or INCORRECT"
        )
        response, _ = self.client.chat([{"role": "user", "content": prompt}], ModelSettings(temperature=0.0, max_tokens=200))
        upper = response.upper()
        judged_correct = "INCORRECT" not in upper and "CORRECT" in upper
        self._judge_cache[cache_key] = judged_correct
        return judged_correct


class TextVQAAdapter(GenericJsonlAdapter):
    """TextVQA-specific partial-credit scoring."""

    def __init__(self) -> None:
        super().__init__(dataset_name="textvqa")

    def score_answer(self, answer: str, case: TaskCase) -> float:
        answers = [str(value) for value in case.metadata.get("answers", [])]
        return score_textvqa_answer(answer, answers)

    def check_answer(self, answer: str, case: TaskCase) -> bool:
        return check_textvqa_case_answer(answer, case)


class ReFocusTableVQAAdapter(GenericJsonlAdapter):
    """ReFOCUS/TableVQA answer checking."""

    def __init__(self) -> None:
        super().__init__(dataset_name="refocus_tablevqa")

    def score_answer(self, answer: str, case: TaskCase) -> float:
        actual = _normalize_text(answer)
        expected = _normalize_text(case.gold_answer)
        if not actual or not expected:
            return 0.0
        if actual == expected:
            return 1.0

        actual_number = _parse_number(actual)
        expected_number = _parse_number(expected)
        if actual_number is not None and expected_number is not None:
            tolerance = 1e-6
            return 1.0 if abs(actual_number - expected_number) <= tolerance else 0.0

        return 1.0 if re.search(rf"(?<![a-z0-9]){re.escape(expected)}(?![a-z0-9])", actual) else 0.0


class GTAAdapter(GenericJsonlAdapter):
    """GTA-specific answer checking with whitelist/blacklist support."""

    def __init__(self) -> None:
        super().__init__(dataset_name="gta")

    def score_answer(self, answer: str, case: TaskCase) -> float:
        actual = _normalize_text(answer)
        if not actual:
            return 0.0

        blacklist = case.metadata.get("gt_answer_blacklist")
        if isinstance(blacklist, list):
            for group in blacklist:
                if not isinstance(group, list):
                    continue
                for blocked in group:
                    blocked_text = _normalize_text(str(blocked))
                    if blocked_text and blocked_text in actual:
                        return 0.0

        whitelist = case.metadata.get("gt_answer_whitelist")
        if isinstance(whitelist, list) and any(isinstance(group, list) and group for group in whitelist):
            for group in whitelist:
                if not isinstance(group, list) or not group:
                    continue
                if all(_gta_match(actual, _normalize_text(str(expected))) for expected in group):
                    return 1.0
            return 0.0

        return super().score_answer(answer, case)

    def build_family_id(self, case: TaskCase) -> str:
        return str(case.metadata.get("capability_family", case.metadata.get("tool_category", "gta")))

    def cluster_key(self, case: TaskCase, result: AgentResult, correct: bool) -> str:
        if correct:
            return "correct"
        tool_category = str(case.metadata.get("tool_category", "unknown"))
        num_steps = int(case.metadata.get("num_steps", 0) or 0)
        step_bucket = "single" if num_steps <= 1 else ("short" if num_steps <= 3 else "long")
        return f"gta::{tool_category}::{step_bucket}"

    def summarize_case(self, case: TaskCase, result: AgentResult, correct: bool) -> dict[str, str]:
        summary = super().summarize_case(case, result, correct)
        summary["gt_tools"] = ",".join(str(tool) for tool in case.metadata.get("gt_tools", []))
        summary["tool_category"] = str(case.metadata.get("tool_category", ""))
        summary["num_steps"] = str(case.metadata.get("num_steps", 0))
        return summary


def get_benchmark_adapter(dataset_name: str, client: VLMClient | None = None) -> BenchmarkAdapter:
    """Return the adapter registered for the given dataset."""
    normalized = dataset_name.strip().lower()
    registry: dict[str, BenchmarkAdapter] = {
        "chartqa": ChartQAAdapter(),
        "gta": GTAAdapter(),
        "vstar": VStarAdapter(),
        "v*": VStarAdapter(),
        "hrbench": HRBenchAdapter(),
        "mathvista": MathVistaAdapter(client=client),
        "refocus_tablevqa": ReFocusTableVQAAdapter(),
        "tablevqa": ReFocusTableVQAAdapter(),
        "refocus": ReFocusTableVQAAdapter(),
        "textvqa": TextVQAAdapter(),
    }
    if normalized in registry:
        return registry[normalized]
    return GenericJsonlAdapter(dataset_name=normalized)


def available_benchmark_datasets() -> list[str]:
    """Return the known dataset names for CLI choices/help."""
    return ["chartqa", "gta", "hrbench", "mathvista", "refocus_tablevqa", "textvqa", "vstar"]


def _normalize_text(value: str) -> str:
    cleaned = str(value).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _gta_match(actual: str, expected: str) -> bool:
    if not expected:
        return False
    if expected in actual:
        return True

    actual_number = _parse_number(actual)
    expected_number = _parse_number(expected)
    if actual_number is not None and expected_number is not None:
        tolerance = 0.01 * max(1.0, abs(expected_number))
        return abs(actual_number - expected_number) < tolerance

    return bool(re.search(rf"(?<![a-z0-9]){re.escape(expected)}(?![a-z0-9])", actual))


def _parse_number(value: str) -> float | None:
    text = value.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _case_choices(case: TaskCase) -> dict[str, str]:
    choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
    normalized = {
        str(label).strip().upper(): str(text).strip()
        for label, text in choices.items()
        if str(label).strip() and str(text).strip()
    }
    if normalized:
        return normalized
    return _extract_choices_from_prompt(case.prompt)


def _extract_choices_from_prompt(prompt: str) -> dict[str, str]:
    text = str(prompt or "")
    matches = re.findall(r"\(([A-D])\)\s*([^\n]+)", text, flags=re.IGNORECASE)
    choices: dict[str, str] = {}
    for label, choice_text in matches:
        cleaned = str(choice_text).strip()
        if cleaned:
            choices[str(label).upper()] = cleaned
    return choices
