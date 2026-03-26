"""Compare direct VLM answers against empty-active agent baseline on the same cases."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.structured_data import load_normalized_cases
from core.types import AgentResult, Message, TaskCase
from core.vlm_client import ModelSettings, VLMClient
from evolution.benchmark_adapters import get_benchmark_adapter
from evolution.loop import EvolutionLoop


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug direct_vlm vs empty-active agent baseline on the same cases.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--normalized-data-root", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--case-id", default="", help="Optional single case id to inspect.")
    parser.add_argument("--output-dir", default="", help="Optional output dir. Defaults to artifacts/debug_compare/<name>.")
    args = parser.parse_args()

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else PROJECT_ROOT / "artifacts" / "debug_compare" / f"{args.dataset}_{args.split}_{args.case_id or args.limit}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    client = VLMClient()
    adapter = get_benchmark_adapter(args.dataset, client=client)
    all_cases = load_normalized_cases(Path(args.normalized_data_root), args.dataset, args.split)
    if args.case_id:
        cases = [case for case in all_cases if case.case_id == args.case_id]
    else:
        cases = all_cases[: args.limit]
    if not cases:
        raise SystemExit("No matching cases found.")

    records: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        loop = EvolutionLoop(
            work_dir=tmp_root / "work",
            learned_dir=tmp_root / "learned_empty",
            skills_dir=PROJECT_ROOT / "skills",
            vlm_client=client,
            max_attempts=1,
            subset_id=None,
            answer_checker=adapter.check_answer,
            capability_mode="persistent_tools",
        )

        for index, case in enumerate(cases, start=1):
            direct_prompt = _direct_prompt(case)
            direct_messages = [
                {
                    "role": "user",
                    "content": VLMClient.image_message_parts(case.image_path, direct_prompt),
                }
            ]
            direct_answer, _ = client.chat(direct_messages, ModelSettings(temperature=0.0, max_tokens=200))
            direct_answer = direct_answer.strip()
            direct_score = adapter.score_answer(direct_answer, case)
            direct_correct = adapter.check_answer(direct_answer, case)

            agent, chain_context = _build_empty_agent(loop, case, phase=f"debug_agent_{index}")
            agent_result = agent.run(
                case.prompt,
                case.image_path,
                initial_observations=loop._chain_observations_for_agent(chain_context),
            )
            agent_score = adapter.score_answer(agent_result.final_answer, case)
            agent_correct = adapter.check_answer(agent_result.final_answer, case)

            record = {
                "case_id": case.case_id,
                "dataset_name": case.dataset_name(),
                "capability_family": case.capability_family(),
                "prompt": case.prompt,
                "gold_answer": case.gold_answer,
                "image_path": case.image_path,
                "direct": {
                    "answer": direct_answer,
                    "correct": direct_correct,
                    "score": direct_score,
                    "messages": _sanitize_messages(direct_messages),
                },
                "agent_empty_active": {
                    "answer": agent_result.final_answer,
                    "correct": agent_correct,
                    "score": agent_score,
                    "turns": agent_result.total_turns,
                    "system_prompt": _truncate_text(agent.system_prompt, 4000),
                    "messages": _sanitize_agent_messages(agent_result.messages),
                    "steps": [_serialize_step(step) for step in agent_result.steps],
                    "chain_trace": list(chain_context.tool_sequence),
                },
                "delta": {
                    "correct_gap": int(direct_correct) - int(agent_correct),
                    "score_gap": float(direct_score) - float(agent_score),
                },
            }
            records.append(record)
            print(
                f"[{index:03d}/{len(cases):03d}] case={case.case_id} "
                f"direct={'OK' if direct_correct else 'FAIL'} "
                f"agent={'OK' if agent_correct else 'FAIL'} "
                f"gap={float(direct_score) - float(agent_score):+.3f}"
            )

    summary = {
        "dataset": args.dataset,
        "split": args.split,
        "cases": len(records),
        "direct_accuracy": sum(1 for row in records if row["direct"]["correct"]) / len(records),
        "agent_accuracy": sum(1 for row in records if row["agent_empty_active"]["correct"]) / len(records),
        "direct_avg_score": sum(float(row["direct"]["score"]) for row in records) / len(records),
        "agent_avg_score": sum(float(row["agent_empty_active"]["score"]) for row in records) / len(records),
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "per_case.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _build_empty_agent(loop: EvolutionLoop, case: TaskCase, phase: str):
    capability_snapshot = loop._tool_availability_snapshot()
    chain_context = loop.validator.build_chain_context(
        case,
        loop._usable_skill_content(None, capability_snapshot),
        attempt=1,
    )
    agent = loop._create_agent(case, attempt=1, phase=phase)
    return agent, chain_context


def _direct_prompt(case: TaskCase) -> str:
    choices = case.metadata.get("choices") if isinstance(case.metadata.get("choices"), dict) else {}
    choice_block = ""
    if choices and "choices:" not in case.prompt.lower():
        choice_lines = "\n".join(f"{label}. {text}" for label, text in sorted(choices.items()))
        choice_block = f"\nChoices:\n{choice_lines}"
    return (
        "Answer the question directly from the image.\n"
        "Return only the final short answer with no explanation.\n"
        "If the task is multiple choice, return the option letter when possible.\n\n"
        f"Question: {case.prompt}{choice_block}"
    )


def _sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_sanitize_message(message) for message in messages]


def _sanitize_agent_messages(messages: list[Message]) -> list[dict[str, Any]]:
    return [_sanitize_message(asdict(message)) for message in messages]


def _sanitize_message(message: dict[str, Any]) -> dict[str, Any]:
    sanitized = {"role": message.get("role", "")}
    content = message.get("content")
    if isinstance(content, str):
        sanitized["content"] = _truncate_text(content, 3000)
        return sanitized
    if isinstance(content, list):
        parts: list[dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict):
                parts.append({"type": "unknown", "value": _truncate_text(str(part), 200)})
                continue
            if part.get("type") == "text":
                parts.append({"type": "text", "text": _truncate_text(str(part.get("text", "")), 1200)})
            elif part.get("type") == "image_url":
                url = str((part.get("image_url") or {}).get("url", ""))
                parts.append({"type": "image_url", "url": _summarize_data_url(url)})
            else:
                parts.append({"type": str(part.get("type", "unknown"))})
        sanitized["content"] = parts
        return sanitized
    sanitized["content"] = _truncate_text(str(content), 1000)
    return sanitized


def _serialize_step(step: Any) -> dict[str, Any]:
    action = None
    if step.action is not None:
        action = {"name": step.action.name, "arguments": dict(step.action.arguments)}
    return {
        "turn": step.turn,
        "action": action,
        "thought": _truncate_text(step.thought or "", 2500),
        "observation": _truncate_text(step.observation or "", 2000),
        "artifacts": list(step.artifacts),
        "is_final": step.is_final,
        "is_format_error": step.is_format_error,
    }


def _summarize_data_url(url: str) -> str:
    if not url.startswith("data:"):
        return _truncate_text(url, 200)
    prefix, _, payload = url.partition(",")
    return f"{prefix},<payload_len={len(payload)}>"


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + f"... [truncated {len(text) - limit} chars]"


if __name__ == "__main__":
    main()
