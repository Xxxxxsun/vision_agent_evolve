"""TIR-Bench runner and task-specific evaluator."""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.structured_data import load_tirbench_cases
from core.types import TirBenchCase, ToolResult
from core.vlm_client import ModelSettings, VLMClient
from tools.visualtoolbench_tools import execute_visualtoolbench_tool, get_visualtoolbench_tool_descriptions


DIRECT_SYSTEM_PROMPT = """You are solving TIR-Bench visual reasoning tasks.
Answer the user's question from the provided image(s). Think carefully, then provide the final answer clearly.
"""


TOOL_SYSTEM_PROMPT = """You are solving TIR-Bench thinking-with-images tasks.

You may iteratively call tools to transform images, inspect details, compute, and reason. Available tools:
{tool_descriptions}

Reply in exactly one of these formats:

Action:
{{"name":"<tool_name>","arguments":{{...}}}}

or

Final Answer: <answer>
ACTION: TASK_COMPLETE

Rules:
- Proactively use python_image_processing for small text, grids, mazes, jigsaws, rotations, color/contrast, visual search, and object-region estimation.
- Save processed images as transformed_image_i.png and inspect the resulting observation before finalizing.
- Use python_interpreter for deterministic calculations or grid/path checks.
- Keep tool arguments valid JSON. Put Python source in the "code" field.
- Do not call tools after giving Final Answer.
"""


@dataclass
class TirBenchToolCall:
    name: str
    arguments: dict[str, Any]
    status: str
    observation: str
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class TirBenchCaseResult:
    case_id: str
    task: str
    prompt: str
    answer: str
    model_response: str
    extracted_answer: str
    score: float
    image_paths: list[str]
    mode: str
    tool_calls: list[TirBenchToolCall] = field(default_factory=list)
    error: str | None = None


class TirBenchRunner:
    """Evaluate TIR-Bench in direct or tool-enabled mode."""

    def __init__(
        self,
        normalized_data_root: Path,
        output_dir: Path,
        client: VLMClient | None = None,
        extractor_client: VLMClient | None = None,
        mode: str = "direct",
        max_tool_calls: int = 20,
    ):
        if mode not in {"direct", "tool"}:
            raise ValueError(f"Unsupported TIR-Bench mode: {mode}")
        self.normalized_data_root = normalized_data_root
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or VLMClient()
        self.extractor_client = extractor_client or self.client
        self.mode = mode
        self.max_tool_calls = max_tool_calls

    def run(self, split: str = "test", limit: int = 0) -> dict[str, Any]:
        cases = load_tirbench_cases(self.normalized_data_root, split=split, limit=limit)
        detailed_path = self.output_dir / "tirbench_results_detailed.json"
        results: list[TirBenchCaseResult] = _load_existing_results(detailed_path)
        completed_ids = {result.case_id for result in results}
        for case in cases:
            if case.case_id in completed_ids:
                continue
            try:
                results.append(self._run_case(case))
            except Exception as exc:
                extracted = ""
                score = score_tirbench_answer(
                    task=case.task,
                    model_response="",
                    extracted_answer=extracted,
                    answer=case.gold_answer,
                    item={"image_1": case.metadata.get("source_image_1", ""), "metadata": case.metadata},
                )
                results.append(
                    TirBenchCaseResult(
                        case_id=case.case_id,
                        task=case.task,
                        prompt=case.prompt,
                        answer=case.gold_answer,
                        model_response="",
                        extracted_answer=extracted,
                        score=score,
                        image_paths=case.image_paths,
                        mode=self.mode,
                        error=str(exc),
                    )
                )
            self._write_outputs(results, detailed_path)

        return self._write_outputs(results, detailed_path)

    def _write_outputs(self, results: list[TirBenchCaseResult], detailed_path: Path) -> dict[str, Any]:
        official_payload = {
            result.case_id: _case_result_to_official_dict(result)
            for result in results
        }
        results_path = self.output_dir / "tirbench_results.json"
        results_path.write_text(json.dumps(official_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        detailed_path.write_text(
            json.dumps([_case_result_to_dict(result) for result in results], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        diagnostics = self._build_diagnostics(results)
        diagnostics_path = self.output_dir / "diagnostics.json"
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2), encoding="utf-8")

        summary = {
            "cases": len(results),
            "accuracy": sum(result.score for result in results) / len(results) if results else 0.0,
            "task_accuracy": diagnostics["task_accuracy"],
            "mode": self.mode,
            "diagnostics_path": str(diagnostics_path),
            "results_path": str(results_path),
            "detailed_results_path": str(detailed_path),
        }
        summary_path = self.output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    def _run_case(self, case: TirBenchCase) -> TirBenchCaseResult:
        if self.mode == "direct":
            model_response, tool_calls = self._run_direct_case(case), []
        else:
            model_response, tool_calls = self._run_tool_case(case)

        extracted_answer = extract_tirbench_answer(
            task=case.task,
            prompt=case.prompt,
            model_response=model_response,
            extractor_client=self.extractor_client,
        )
        score = score_tirbench_answer(
            task=case.task,
            model_response=model_response,
            extracted_answer=extracted_answer,
            answer=case.gold_answer,
            item={"image_1": case.metadata.get("source_image_1", ""), "metadata": case.metadata},
        )
        return TirBenchCaseResult(
            case_id=case.case_id,
            task=case.task,
            prompt=case.prompt,
            answer=case.gold_answer,
            model_response=model_response,
            extracted_answer=extracted_answer,
            score=score,
            image_paths=case.image_paths,
            mode=self.mode,
            tool_calls=tool_calls,
        )

    def _run_direct_case(self, case: TirBenchCase) -> str:
        messages = [
            {"role": "system", "content": DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": _case_content(case)},
        ]
        response, _ = self.client.chat(messages, ModelSettings(temperature=0.0, max_tokens=4000))
        return str(response).strip()

    def _run_tool_case(self, case: TirBenchCase) -> tuple[str, list[TirBenchToolCall]]:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": TOOL_SYSTEM_PROMPT.format(
                    tool_descriptions=get_visualtoolbench_tool_descriptions(),
                ),
            },
            {"role": "user", "content": _case_content(case)},
        ]
        tool_calls: list[TirBenchToolCall] = []
        workspace = self.output_dir / str(case.case_id)
        final_answer = ""

        for _ in range(self.max_tool_calls + 1):
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
            result = execute_visualtoolbench_tool(
                tool_name,
                arguments,
                workspace_dir=workspace,
                image_paths=case.image_paths,
            )
            observation = str(result)
            tool_calls.append(
                TirBenchToolCall(
                    name=tool_name,
                    arguments=arguments,
                    status=result.status,
                    observation=observation,
                    artifacts=list(result.artifacts),
                    error=result.error,
                )
            )
            messages.append({"role": "user", "content": _observation_content(observation, result.artifacts)})

        return final_answer.strip(), tool_calls

    def _build_diagnostics(self, results: list[TirBenchCaseResult]) -> dict[str, Any]:
        task_scores: dict[str, list[float]] = {}
        tool_counts: dict[str, int] = {}
        tool_error_counts: dict[str, int] = {}
        no_tool_cases = 0
        for result in results:
            task_scores.setdefault(result.task, []).append(result.score)
            if not result.tool_calls:
                no_tool_cases += 1
            for tool_call in result.tool_calls:
                tool_counts[tool_call.name] = tool_counts.get(tool_call.name, 0) + 1
                if tool_call.status != "ok":
                    tool_error_counts[tool_call.name] = tool_error_counts.get(tool_call.name, 0) + 1
        task_accuracy = {
            task: sum(scores) / len(scores)
            for task, scores in sorted(task_scores.items())
            if scores
        }
        tool_success_rates = {
            name: (count - tool_error_counts.get(name, 0)) / count
            for name, count in sorted(tool_counts.items())
            if count
        }
        total_tool_calls = sum(tool_counts.values())
        return {
            "total_cases": len(results),
            "accuracy": sum(result.score for result in results) / len(results) if results else 0.0,
            "task_accuracy": task_accuracy,
            "task_counts": {task: len(scores) for task, scores in sorted(task_scores.items())},
            "total_tool_calls": total_tool_calls,
            "avg_tool_calls_per_case": total_tool_calls / len(results) if results else 0.0,
            "no_tool_case_ratio": no_tool_cases / len(results) if results else 0.0,
            "tool_counts": dict(sorted(tool_counts.items())),
            "tool_error_counts": dict(sorted(tool_error_counts.items())),
            "tool_success_rates": tool_success_rates,
            "error_cases": [
                {"case_id": result.case_id, "task": result.task, "error": result.error}
                for result in results
                if result.error
            ],
        }


def extract_tirbench_answer(
    task: str,
    prompt: str,
    model_response: str,
    extractor_client: VLMClient,
) -> str:
    """Extract a compact answer from a model response using a TIR-style prompt."""
    if task == "ocr":
        return str(model_response).strip()
    extraction_prompt = (
        "Please extract only the final answer from the model response for this TIR-Bench task.\n"
        "Return the answer only, without explanation.\n"
        "For multiple choice, return the option letter(s) only. For numeric tasks, return the number only. "
        "For jigsaw, return the sequence of piece numbers only.\n\n"
        f"Task type: {task}\n"
        f"Question: {prompt}\n\n"
        f"Model response: {model_response}\n\n"
        "Extracted answer:"
    )
    raw, _ = extractor_client.chat(
        [
            {"role": "system", "content": "You extract short benchmark answers."},
            {"role": "user", "content": extraction_prompt},
        ],
        ModelSettings(temperature=0.0, max_tokens=800),
    )
    return str(raw).strip()


def score_tirbench_answer(
    task: str,
    model_response: str,
    extracted_answer: str,
    answer: str,
    item: dict[str, Any] | None = None,
) -> float:
    """Score one TIR-Bench prediction following the official rule structure."""
    item = item or {}
    extracted_answer = str(extracted_answer or "").replace("*", "").strip()
    answer = str(answer)

    if task == "ocr":
        response = model_response[0] if isinstance(model_response, list) else str(model_response)
        image_1 = str(item.get("image_1", ""))
        if "60.jpg" in image_1:
            answer = "mobi"
        if "62.jpg" in image_1:
            answer = "aires"
        return 1.0 if answer in response else 0.0

    if task == "word_search":
        if _classify_string(answer) == 2:
            return _judge_int(extracted_answer, answer)
        answer_pair = _extract_two_numbers(answer)
        extracted_pair = _extract_two_numbers(extracted_answer)
        return 1.0 if answer_pair and answer_pair == extracted_pair else 0.0

    if task == "spot_difference":
        if _classify_string(answer) == 2:
            return _judge_int(extracted_answer, answer)
        return _list_iou(_extract_consecutive_integers(extracted_answer), _extract_consecutive_integers(answer))

    if task == "jigsaw":
        try:
            metadata = dict(item.get("metadata") or item.get("meta_data") or {})
            difficulty = int(metadata.get("difficulty") or 0)
            if difficulty <= 0:
                difficulty = int(len(_extract_consecutive_integers(answer)) ** 0.5)
            pred = _extract_consecutive_n_squared(extracted_answer, difficulty)
            gold = _extract_consecutive_n_squared(answer, difficulty)
            return _compare_lists(gold, pred)
        except Exception:
            return 0.0

    string_type = _classify_string(answer)
    if string_type == 1:
        return _judge_choice(extracted_answer, answer, item)
    if string_type == 2:
        return _judge_int(extracted_answer, answer)
    if string_type == 3:
        return _judge_float(extracted_answer, answer)
    return 0.0


def _case_content(case: TirBenchCase) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [
        {"type": "text", "text": f"Task type: {case.task}\nQuestion:\n{case.prompt}"}
    ]
    for image_path in case.image_paths[:5]:
        path = Path(image_path)
        parts.append({"type": "text", "text": f"\n[Image: {path.name}]"})
        parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(path)}})
    return parts


def _observation_content(observation: str, artifacts: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = [{"type": "text", "text": f"Observation:\n{observation}"}]
    for artifact in artifacts[:5]:
        path = Path(artifact)
        if path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            parts.append({"type": "text", "text": f"\n[Tool artifact: {path.name}]"})
            parts.append({"type": "image_url", "image_url": {"url": VLMClient.image_data_url(path)}})
    return parts


def _extract_action(response: str) -> dict[str, Any] | None:
    match = re.search(r"Action:\s*", response, re.IGNORECASE)
    candidate_text = response[match.end():].lstrip() if match else response.lstrip()
    json_start = candidate_text.find("{")
    if json_start < 0:
        return None
    try:
        payload, _ = json.JSONDecoder().raw_decode(candidate_text[json_start:])
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and payload.get("name") and isinstance(payload.get("arguments"), dict):
        return payload
    return None


def _extract_final_answer(response: str) -> str:
    match = re.search(
        r"Final Answer:\s*(.+?)(?:\nACTION:\s*TASK_COMPLETE|\Z)",
        response,
        re.IGNORECASE | re.DOTALL,
    )
    return match.group(1).strip() if match else response.strip()


def _extract_consecutive_n_squared(text: str, n: int) -> list[int]:
    total = n * n
    sequences = re.findall(r"[\d\s,，]+", str(text))
    for seq in sequences:
        nums = re.findall(r"\d+", seq)
        if len(nums) == total:
            return [int(num) for num in nums]
    raise ValueError(f"No consecutive {total}-number sequence found")


def _compare_lists(left: list[int], right: list[int]) -> float:
    if not left:
        return 0.0
    return sum(1 for index, value in enumerate(left) if index < len(right) and right[index] == value) / len(left)


def _extract_consecutive_integers(text: str) -> list[int]:
    return [int(match) for match in re.findall(r"\d+(?=[,\s]*|\b)", str(text))]


def _extract_two_numbers(text: str) -> tuple[int, int] | None:
    match = re.search(r"\b(\d+)\s*,\s*(\d+)\b", str(text))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _list_iou(predicted: list[int], expected: list[int]) -> float:
    pred_set = set(predicted)
    expected_set = set(expected)
    union = pred_set | expected_set
    if not union:
        return 1.0
    return len(pred_set & expected_set) / len(union)


def _classify_string(value: str) -> int:
    value = str(value).strip()
    if value.isalpha():
        return 1
    try:
        int(value)
        return 2
    except ValueError:
        pass
    try:
        float(value)
        return 3
    except ValueError:
        return 4


def _judge_int(extracted_answer: str, answer: str) -> float:
    extraction = re.sub(r"[A-Za-z*:\s]+", "", extracted_answer.replace("Extracted answer:", "")).strip()
    try:
        return 1.0 if int(extraction) == int(answer) else 0.0
    except Exception:
        numbers = re.findall(r"-?\d+", extracted_answer)
        return 1.0 if numbers and int(numbers[-1]) == int(answer) else 0.0


def _judge_float(extracted_answer: str, answer: str) -> float:
    extraction = re.sub(r"[A-Za-z*:\s]+", "", extracted_answer.replace("Extracted answer:", "")).strip()
    try:
        return 1.0 if float(extraction) == float(answer) else 0.0
    except Exception:
        numbers = re.findall(r"-?\d+(?:\.\d+)?", extracted_answer)
        return 1.0 if numbers and float(numbers[-1]) == float(answer) else 0.0


def _judge_choice(extracted_answer: str, answer: str, item: dict[str, Any]) -> float:
    choices = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    answer = str(answer).strip()
    extraction = extracted_answer.replace("Extracted answer:", "").strip()
    if len(answer) == 1 and answer in choices:
        candidate = extraction.strip().upper()
        if candidate not in choices:
            prompt = str(item.get("prompt", ""))
            for choice in choices:
                if f"{choice}. {extraction}" in prompt or f"{choice}.{extraction}" in prompt or f"{choice} {extraction}" in prompt:
                    candidate = choice
                    break
            if candidate not in choices:
                candidate = difflib.get_close_matches(candidate, choices, n=1)
                candidate = candidate[0] if candidate else ""
        return 1.0 if candidate == answer else 0.0

    sorted_answer = "".join(sorted(answer))
    sorted_extraction = "".join(sorted(re.findall(r"[A-J]", extraction.upper())))
    return 1.0 if sorted_answer == sorted_extraction else 0.0


def _case_result_to_official_dict(result: TirBenchCaseResult) -> dict[str, Any]:
    return {
        "task": result.task,
        "prompt": result.prompt,
        "answer": result.answer,
        "model_response": result.model_response,
        "extracted_answer": result.extracted_answer,
        "true_false": result.score,
        "image_1": result.image_paths[0] if result.image_paths else "",
    }


def _case_result_to_dict(result: TirBenchCaseResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["tool_calls"] = [asdict(item) for item in result.tool_calls]
    return payload


def _load_existing_results(path: Path) -> list[TirBenchCaseResult]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    results: list[TirBenchCaseResult] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tool_calls = [
            TirBenchToolCall(
                name=str(call.get("name", "")),
                arguments=dict(call.get("arguments") or {}),
                status=str(call.get("status", "")),
                observation=str(call.get("observation", "")),
                artifacts=[str(path) for path in call.get("artifacts", [])],
                error=call.get("error"),
            )
            for call in item.get("tool_calls", [])
            if isinstance(call, dict)
        ]
        results.append(
            TirBenchCaseResult(
                case_id=str(item.get("case_id", "")),
                task=str(item.get("task", "")),
                prompt=str(item.get("prompt", "")),
                answer=str(item.get("answer", "")),
                model_response=str(item.get("model_response", "")),
                extracted_answer=str(item.get("extracted_answer", "")),
                score=float(item.get("score", 0.0) or 0.0),
                image_paths=[str(path) for path in item.get("image_paths", [])],
                mode=str(item.get("mode", "")),
                tool_calls=tool_calls,
                error=item.get("error"),
            )
        )
    return results
