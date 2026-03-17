"""Benchmark a learned subset directly on a JSON/JSONL dataset."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent import AgentConfig, ReActAgent
from core.vlm_client import ModelSettings, VLMClient
from evolution.loop import EvolutionLoop
from run import _build_cases


def _check_answer(actual: str, expected: str) -> bool:
    actual_norm = str(actual).strip().lower()
    expected_norm = str(expected).strip().lower()
    if actual_norm == expected_norm:
        return True
    return bool(re.search(r"(?<!\d)" + re.escape(expected_norm) + r"(?!\d)", actual_norm))


def _resolve_case_image(project_root: Path, example_path: Path, image_path: str) -> str:
    """Fix dataset-relative image paths for direct benchmarks."""
    if not image_path:
        return image_path

    candidate = Path(image_path)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)

    direct = project_root / candidate
    if direct.exists():
        try:
            return str(direct.relative_to(project_root))
        except ValueError:
            return str(direct)

    example_relative = example_path.parent / candidate
    if example_relative.exists():
        return str(example_relative)

    for folder_name in ["image", "images"]:
        sibling = example_path.parent / folder_name / candidate.name
        if sibling.exists():
            return str(sibling)

    mira_candidate = project_root / "MIRA" / candidate
    if mira_candidate.exists():
        return str(mira_candidate.relative_to(project_root))

    return image_path


def _direct_vlm_answer(client: VLMClient, prompt: str, image_path: str) -> str:
    """Pure VLM baseline: one multimodal turn, no ReAct and no tools."""
    user_text = (
        "Answer the question from the image directly.\n"
        "Return only the final clock time answer, with no explanation.\n\n"
        f"Question: {prompt}"
    )
    messages = [
        {
            "role": "user",
            "content": VLMClient.image_message_parts(str(PROJECT_ROOT / image_path), user_text),
        }
    ]
    response, _ = client.chat(messages, ModelSettings(temperature=0.0, max_tokens=200))
    return response.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Direct benchmark for a learned subset")
    parser.add_argument("--example", required=True, help="Path to JSON/JSONL examples")
    parser.add_argument("--subset", default="", help="learned/<subset> to use")
    parser.add_argument("--limit", type=int, default=0, help="Optional case limit")
    parser.add_argument("--baseline", action="store_true", help="Run with no learned skill or tool")
    parser.add_argument(
        "--pure-react",
        action="store_true",
        help="For learned subsets, do not pre-run the tool chain or inject initial observations; let the ReAct agent decide and execute tools itself.",
    )
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    example_path = Path(args.example)
    if not example_path.is_absolute():
        example_path = project_root / example_path

    cases = _build_cases(example_path)
    if args.limit > 0:
        cases = cases[:args.limit]
    for case in cases:
        case.image_path = _resolve_case_image(project_root, example_path, case.image_path)

    client = VLMClient()
    loop = None
    if not args.baseline:
        if not args.subset:
            raise SystemExit("--subset is required unless --baseline is used")
        loop = EvolutionLoop(
            work_dir=project_root / "artifacts",
            learned_dir=project_root / "learned",
            skills_dir=project_root / "skills",
            vlm_client=client,
            max_attempts=1,
            subset_id=args.subset,
        )

    rows: list[dict[str, object]] = []
    for index, case in enumerate(cases, start=1):
        if args.baseline:
            chain_trace: list[str] = []
            answer = _direct_vlm_answer(client, case.prompt, case.image_path)
            turns = 1
            artifacts: list[str] = []
        else:
            assert loop is not None
            agent = loop._create_agent(case, attempt=1, phase=f"benchmark_{index}")
            if args.pure_react:
                chain_trace = []
                initial_observations = []
            else:
                skill = loop.store.get_skill(case.problem_id)
                chain_context = loop.validator.build_chain_context(
                    case,
                    skill.content if skill else None,
                    attempt=1,
                )
                chain_trace = chain_context.tool_sequence
                initial_observations = loop._chain_observations_for_agent(chain_context)
            result = agent.run(
                case.prompt,
                case.image_path,
                initial_observations=initial_observations,
            )
            answer = result.final_answer
            turns = result.total_turns
            artifacts = result.get_image_artifacts()

        correct = _check_answer(answer, case.gold_answer)
        rows.append(
            {
                "case_id": case.case_id,
                "image_path": case.image_path,
                "expected": case.gold_answer,
                "answer": answer,
                "correct": correct,
                "turns": turns,
                "artifacts": artifacts,
                "chain_trace": chain_trace,
            }
        )
        status = "OK" if correct else "FAIL"
        print(
            f"[{index:02d}/{len(cases):02d}] {status} "
            f"case={case.case_id} expected={case.gold_answer} answer={answer!r}"
        )

    correct_count = sum(1 for row in rows if row["correct"])
    summary = {
        "subset": args.subset,
        "baseline": args.baseline,
        "pure_react": args.pure_react,
        "example": str(example_path),
        "total": len(rows),
        "correct": correct_count,
        "accuracy": (correct_count / len(rows)) if rows else 0.0,
        "results": rows,
    }

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
