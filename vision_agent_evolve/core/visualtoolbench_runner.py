"""Dedicated runner and rubric evaluator for VisualToolBench."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.structured_data import load_visualtoolbench_cases
from core.types import MultiTurnTaskCase, MultiTurnTaskTurn
from core.vlm_client import ModelSettings, VLMClient
from core.types import ToolResult
from tools.visualtoolbench_tools import (
    execute_visualtoolbench_tool,
    get_visualtoolbench_tool_descriptions,
)


SYSTEM_PROMPT = """You are evaluating VisualToolBench-style tasks.

You may solve the task by iterating with tools. Available tools:
{tool_descriptions}

Reply in exactly one of these formats:

Action:
{{"name":"<tool_name>","arguments":{{...}}}}

or

Final Answer: <answer>
ACTION: TASK_COMPLETE

Rules:
- Use tools when image transformation, external lookup, or calculation is needed.
- Keep tool arguments valid JSON.
- For python_image_processing and python_interpreter, put the full Python source in the "code" field.
- Wait for the observation after each tool call.
"""


@dataclass
class VisualToolCall:
    name: str
    arguments: dict[str, Any]
    status: str
    observation: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class VisualTurnResult:
    turn_index: int
    prompt: str
    final_answer: str
    gold_answer: str
    weighted_score: float
    passed: bool
    rubric_results: dict[str, Any]
    failure_label: str | None = None
    tool_calls: list[VisualToolCall] = field(default_factory=list)
    error: str | None = None


@dataclass
class VisualCaseResult:
    case_id: str
    turncase: str
    prompt_category: str
    eval_focus: str
    num_turns: int
    passed: bool
    average_score: float
    failure_label: str | None = None
    turn_results: list[VisualTurnResult] = field(default_factory=list)
    error: str | None = None


class VisualToolBenchRubricJudge:
    """LLM-as-judge rubric scorer for VisualToolBench."""

    def __init__(self, client: VLMClient):
        self.client = client

    def evaluate_turn(
        self,
        turn: MultiTurnTaskTurn,
        response: str,
    ) -> tuple[float, bool, dict[str, Any]]:
        rubrics = self._parse_rubrics(turn.rubric_payload)
        if not rubrics:
            fallback_correct = self._normalize(response) == self._normalize(turn.gold_answer)
            return float(fallback_correct), fallback_correct, {
                "fallback": True,
                "exact_match": fallback_correct,
            }

        prompt = (
            "You are a strict VisualToolBench rubric judge.\n"
            "Given a task prompt, a reference answer, a model response, and the rubric dictionary, "
            "judge each rubric independently as YES or NO.\n"
            "Return JSON only with keys:\n"
            "{"
            '"per_rubric":{"rubric_id":{"satisfied":"yes|no","reason":"short"}}'
            "}\n"
            "Do not add any extra text."
        )
        payload = {
            "task_prompt": turn.prompt,
            "gold_answer": turn.gold_answer,
            "model_response": response,
            "rubrics": rubrics,
        }
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        raw, _ = self.client.chat(messages, ModelSettings(temperature=0.0, max_tokens=2000))
        parsed = _extract_json_object(raw) or {}
        per_rubric = parsed.get("per_rubric") if isinstance(parsed, dict) else {}
        result_payload: dict[str, Any] = {"per_rubric": {}, "raw_judge": raw}

        total_weight = 0.0
        earned_weight = 0.0
        passed = True
        for rubric_id, rubric in rubrics.items():
            weight = float(rubric.get("weight", 1) or 1)
            total_weight += weight
            decision = per_rubric.get(rubric_id, {}) if isinstance(per_rubric, dict) else {}
            satisfied = str(decision.get("satisfied", "")).strip().lower() == "yes"
            if satisfied:
                earned_weight += weight
            if _is_critical_rubric(rubric) and not satisfied:
                passed = False
            result_payload["per_rubric"][rubric_id] = {
                "description": str(rubric.get("description", "")),
                "weight": weight,
                "critical": _is_critical_rubric(rubric),
                "satisfied": satisfied,
                "reason": str(decision.get("reason", "")).strip(),
            }
        if total_weight <= 0:
            return 0.0, False, result_payload
        return earned_weight / total_weight, passed, result_payload

    @staticmethod
    def _parse_rubrics(raw_payload: str) -> dict[str, dict[str, Any]]:
        text = str(raw_payload).strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(key): value
            for key, value in parsed.items()
            if isinstance(value, dict)
        }

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text).strip().lower())


class VisualToolBenchRunner:
    """Prompt-driven VisualToolBench runner with tool execution and rubric scoring."""

    def __init__(
        self,
        normalized_data_root: Path,
        output_dir: Path,
        client: VLMClient | None = None,
        max_tool_calls_per_turn: int = 8,
    ):
        self.normalized_data_root = normalized_data_root
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or VLMClient()
        self.max_tool_calls_per_turn = max_tool_calls_per_turn
        self.judge = VisualToolBenchRubricJudge(self.client)

    def run(self, split: str = "test", limit: int = 0) -> dict[str, Any]:
        cases = load_visualtoolbench_cases(self.normalized_data_root, split=split, limit=limit)
        results: list[VisualCaseResult] = []
        for case in cases:
            try:
                results.append(self._run_case(case))
            except Exception as exc:
                results.append(
                    VisualCaseResult(
                        case_id=case.case_id,
                        turncase=case.turncase,
                        prompt_category=case.prompt_category,
                        eval_focus=case.eval_focus,
                        num_turns=case.num_turns,
                        passed=False,
                        average_score=0.0,
                        failure_label="runner_exception",
                        error=str(exc),
                    )
                )

        output_path = self.output_dir / "visualtoolbench_results.json"
        output_path.write_text(
            json.dumps([_case_result_to_dict(item) for item in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        total_turns = sum(item.num_turns for item in results)
        passed_turns = sum(1 for item in results for turn in item.turn_results if turn.passed)
        avg_score = (
            sum(turn.weighted_score for item in results for turn in item.turn_results) / total_turns
            if total_turns else 0.0
        )
        diagnostics = self._build_diagnostics(results)
        summary = {
            "cases": len(results),
            "turns": total_turns,
            "case_pass_rate": sum(1 for item in results if item.passed) / len(results) if results else 0.0,
            "turn_pass_rate": passed_turns / total_turns if total_turns else 0.0,
            "average_rubric_score": avg_score,
            "diagnostics_path": str(self.output_dir / "diagnostics.json"),
            "results_path": str(output_path),
        }
        summary_path = self.output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        diagnostics_path = self.output_dir / "diagnostics.json"
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def _run_case(self, case: MultiTurnTaskCase) -> VisualCaseResult:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    tool_descriptions=get_visualtoolbench_tool_descriptions(),
                ),
            }
        ]
        turn_results: list[VisualTurnResult] = []
        case_workspace = self.output_dir / case.case_id
        case_workspace.mkdir(parents=True, exist_ok=True)

        for turn_index, turn in enumerate(case.turns):
            prompt_content = self._turn_content(case, turn_index, turn)
            messages.append({"role": "user", "content": prompt_content})
            tool_calls: list[VisualToolCall] = []
            final_answer = ""
            turn_error: str | None = None

            for _ in range(self.max_tool_calls_per_turn + 1):
                raw_response, _ = self.client.chat(messages, ModelSettings(temperature=0.0, max_tokens=4000))
                action = _extract_action(raw_response)
                if action is None:
                    final_answer = _extract_final_answer(raw_response)
                    messages.append({"role": "assistant", "content": raw_response})
                    break

                tool_name = str(action.get("name", "")).strip()
                arguments = action.get("arguments", {})
                if not isinstance(arguments, dict):
                    arguments = {}
                messages.append({"role": "assistant", "content": raw_response})
                turn_workspace = case_workspace / f"turn_{turn_index + 1}"
                result = execute_visualtoolbench_tool(
                    tool_name,
                    arguments,
                    workspace_dir=turn_workspace,
                    image_paths=turn.image_paths,
                )
                observation = str(result)
                tool_calls.append(
                    VisualToolCall(
                        name=tool_name,
                        arguments=arguments,
                        status=result.status,
                        observation=observation,
                        artifacts=list(result.artifacts),
                        error=result.error,
                    )
                )
                messages.append({"role": "user", "content": self._observation_content(observation, result.artifacts)})
                if result.status != "ok":
                    turn_error = result.error or observation

            if not final_answer:
                final_answer = ""

            weighted_score, passed, rubric_results = self.judge.evaluate_turn(turn, final_answer)
            failure_label = _classify_turn_failure(
                passed=passed,
                final_answer=final_answer,
                gold_answer=turn.gold_answer,
                tool_calls=tool_calls,
                turn_error=turn_error,
                max_tool_calls=self.max_tool_calls_per_turn,
            )
            turn_results.append(
                VisualTurnResult(
                    turn_index=turn_index + 1,
                    prompt=turn.prompt,
                    final_answer=final_answer,
                    gold_answer=turn.gold_answer,
                    weighted_score=weighted_score,
                    passed=passed,
                    rubric_results=rubric_results,
                    failure_label=failure_label,
                    tool_calls=tool_calls,
                    error=turn_error,
                )
            )

        average_score = (
            sum(item.weighted_score for item in turn_results) / len(turn_results)
            if turn_results else 0.0
        )
        passed = all(item.passed for item in turn_results) if turn_results else False
        failure_label = None if passed else _classify_case_failure(turn_results)
        return VisualCaseResult(
            case_id=case.case_id,
            turncase=case.turncase,
            prompt_category=case.prompt_category,
            eval_focus=case.eval_focus,
            num_turns=case.num_turns,
            passed=passed,
            average_score=average_score,
            failure_label=failure_label,
            turn_results=turn_results,
        )

    def _turn_content(self, case: MultiTurnTaskCase, turn_index: int, turn: MultiTurnTaskTurn) -> list[dict[str, Any]]:
        intro = (
            f"Case ID: {case.case_id}\n"
            f"Turn {turn_index + 1} of {case.num_turns}\n"
            f"Category: {case.prompt_category}\n"
            f"Eval focus: {case.eval_focus}\n\n"
            f"Task:\n{turn.prompt}"
        )
        parts: list[dict[str, Any]] = [{"type": "text", "text": intro}]
        for image_path in turn.image_paths[:5]:
            parts.append({"type": "text", "text": f"\n[Turn image: {Path(image_path).name}]"})
            parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(image_path)}})
        return parts

    def _observation_content(self, observation: str, artifacts: list[str]) -> Any:
        parts: list[dict[str, Any]] = [{"type": "text", "text": f"Observation:\n{observation}"}]
        for artifact in artifacts[:5]:
            path = Path(artifact)
            if path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                parts.append({"type": "text", "text": f"\n[Tool artifact: {path.name}]"})
                parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(path)}})
        return parts

    def _build_diagnostics(self, results: list[VisualCaseResult]) -> dict[str, Any]:
        tool_counts: dict[str, int] = {}
        tool_error_counts: dict[str, int] = {}
        failure_counts: dict[str, int] = {}
        eval_focus_failures: dict[str, int] = {}
        prompt_category_failures: dict[str, int] = {}
        total_tool_calls = 0
        cases_without_tools = 0
        total_cases = len(results)

        for case in results:
            if case.failure_label:
                failure_counts[case.failure_label] = failure_counts.get(case.failure_label, 0) + 1
                eval_focus_failures[case.eval_focus] = eval_focus_failures.get(case.eval_focus, 0) + 1
                prompt_category_failures[case.prompt_category] = prompt_category_failures.get(case.prompt_category, 0) + 1

            case_tool_calls = 0
            for turn in case.turn_results:
                for tool_call in turn.tool_calls:
                    total_tool_calls += 1
                    case_tool_calls += 1
                    tool_counts[tool_call.name] = tool_counts.get(tool_call.name, 0) + 1
                    if tool_call.status != "ok":
                        tool_error_counts[tool_call.name] = tool_error_counts.get(tool_call.name, 0) + 1
            if case_tool_calls == 0:
                cases_without_tools += 1

        tool_success_rates = {}
        for tool_name, count in tool_counts.items():
            errors = tool_error_counts.get(tool_name, 0)
            tool_success_rates[tool_name] = (count - errors) / count if count else 0.0

        return {
            "total_cases": total_cases,
            "total_tool_calls": total_tool_calls,
            "avg_tool_calls_per_case": total_tool_calls / total_cases if total_cases else 0.0,
            "no_tool_case_ratio": cases_without_tools / total_cases if total_cases else 0.0,
            "tool_counts": dict(sorted(tool_counts.items())),
            "tool_error_counts": dict(sorted(tool_error_counts.items())),
            "tool_success_rates": dict(sorted(tool_success_rates.items())),
            "failure_counts": dict(sorted(failure_counts.items())),
            "failed_eval_focus_counts": dict(sorted(eval_focus_failures.items())),
            "failed_prompt_category_counts": dict(sorted(prompt_category_failures.items())),
            "failed_cases": [
                {
                    "case_id": case.case_id,
                    "turncase": case.turncase,
                    "prompt_category": case.prompt_category,
                    "eval_focus": case.eval_focus,
                    "failure_label": case.failure_label,
                    "error": case.error,
                }
                for case in results
                if not case.passed
            ],
        }


def _extract_action(response: str) -> dict[str, Any] | None:
    match = re.search(r"Action:\s*", response, re.IGNORECASE)
    if not match:
        return None
    tail = response[match.end():].lstrip()
    json_start = tail.find("{")
    if json_start < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(tail[json_start:])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "name" not in payload or "arguments" not in payload:
        return None
    return payload


def _extract_final_answer(response: str) -> str:
    match = re.search(
        r"Final Answer:\s*(.+?)(?:\nACTION:\s*TASK_COMPLETE|\Z)",
        response,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()
    return response.strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    if start < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _is_critical_rubric(rubric: dict[str, Any]) -> bool:
    critical = str(rubric.get("critical", "")).strip().lower()
    if critical in {"yes", "true", "1"}:
        return True
    try:
        return float(rubric.get("weight", 0) or 0) >= 4.0
    except (TypeError, ValueError):
        return False


def _case_result_to_dict(result: VisualCaseResult) -> dict[str, Any]:
    payload = asdict(result)
    return payload


def _classify_case_failure(turn_results: list[VisualTurnResult]) -> str:
    labels = [turn.failure_label for turn in turn_results if turn.failure_label]
    if not labels:
        return "judge_misalignment_suspected"
    priority = [
        "runner_exception",
        "tool_schema_error",
        "tool_runtime_error",
        "max_tool_calls_or_no_completion",
        "vision_extraction_failure",
        "reasoning_failure",
        "judge_misalignment_suspected",
    ]
    for label in priority:
        if label in labels:
            return label
    return labels[0]


def _classify_turn_failure(
    passed: bool,
    final_answer: str,
    gold_answer: str,
    tool_calls: list[VisualToolCall],
    turn_error: str | None,
    max_tool_calls: int,
) -> str | None:
    if passed:
        return None
    if tool_calls and len(tool_calls) >= max_tool_calls and not final_answer.strip():
        return "max_tool_calls_or_no_completion"
    if turn_error:
        error_text = turn_error.lower()
        if "missing" in error_text or "unknown" in error_text or "argument" in error_text or "json" in error_text:
            return "tool_schema_error"
        return "tool_runtime_error"
    if not tool_calls:
        return "reasoning_failure"
    if any(call.name == "python_image_processing" for call in tool_calls):
        if not final_answer.strip():
            return "vision_extraction_failure"
        normalized_answer = _normalize_text(final_answer)
        normalized_gold = _normalize_text(gold_answer)
        if normalized_gold and normalized_gold not in normalized_answer:
            return "vision_extraction_failure"
    if final_answer.strip():
        return "judge_misalignment_suspected"
    return "reasoning_failure"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())
