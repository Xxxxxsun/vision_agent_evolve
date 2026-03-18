"""Benchmark all full MIRA datasets with either baseline or learned capabilities."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.vlm_client import ModelSettings, VLMClient
from evolution.loop import EvolutionLoop
from run import _load_json_objects


@dataclass
class BenchmarkCase:
    case_id: str
    problem_id: str
    prompt: str
    gold_answer: str
    image_path: str


def _check_answer(actual: str, expected: str) -> bool:
    if "||" in expected:
        parts = [part.strip().lower() for part in expected.split("||") if part.strip()]
        actual_norm = str(actual).strip().lower()
        return all(part in actual_norm for part in parts)
    actual_norm = str(actual).strip().lower()
    expected_norm = str(expected).strip().lower()
    if actual_norm == expected_norm:
        return True
    return bool(re.search(r"(?<!\d)" + re.escape(expected_norm) + r"(?!\d)", actual_norm))


def _resolve_case_image(project_root: Path, mira_root: Path, example_path: Path, image_path: str) -> str:
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

    mira_candidate = mira_root / candidate
    if mira_candidate.exists():
        return str(mira_candidate)

    mira_example_relative = mira_root / example_path.parent.name / candidate
    if mira_example_relative.exists():
        return str(mira_example_relative)

    for folder_name in ["image", "images"]:
        mira_sibling = mira_root / example_path.parent.name / folder_name / candidate.name
        if mira_sibling.exists():
            return str(mira_sibling)

    if candidate.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        alt_suffixes = [".png", ".jpg", ".jpeg"]
        for suffix in alt_suffixes:
            if suffix == candidate.suffix.lower():
                continue
            alt_candidate = candidate.with_suffix(suffix)
            alt_checks = [
                project_root / alt_candidate,
                example_path.parent / alt_candidate,
                mira_root / alt_candidate,
                mira_root / example_path.parent.name / alt_candidate,
            ]
            alt_checks.extend(
                mira_root / example_path.parent.name / folder_name / alt_candidate.name
                for folder_name in ["image", "images"]
            )
            for alt_path in alt_checks:
                if alt_path.exists():
                    return str(alt_path)

    return image_path


def _direct_vlm_answer(client: VLMClient, prompt: str, image_path: str) -> str:
    user_text = (
        "Answer the question from the image directly.\n"
        "Return only the final answer, with no explanation.\n\n"
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


def _all_mira_examples(mira_root: Path) -> list[Path]:
    return sorted(mira_root.glob("*/*.jsonl"))


def _find_mira_root(project_root: Path) -> Path:
    env_root = Path(os.getenv("MIRA_ROOT", "").strip()).expanduser() if os.getenv("MIRA_ROOT", "").strip() else None
    if env_root is not None:
        if env_root.exists():
            return env_root
        raise FileNotFoundError(f"MIRA_ROOT is set but does not exist: {env_root}")

    candidates = [
        project_root / "MIRA",
        project_root.parent / "MIRA",
        project_root.parent.parent / "MIRA",
    ]
    best_candidate = None
    best_count = -1
    for candidate in candidates:
        if not candidate.exists():
            continue
        count = len(list(candidate.glob("*/*.jsonl")))
        if count > best_count:
            best_candidate = candidate
            best_count = count
    if best_candidate is not None:
        return best_candidate
    raise FileNotFoundError("Could not locate MIRA root directory.")


def _build_benchmark_cases(example_path: Path, mira_root: Path) -> list[BenchmarkCase]:
    family = example_path.parent.name
    cases: list[BenchmarkCase] = []
    for index, item in enumerate(_load_json_objects(example_path), start=1):
        prompt = str(item.get("prompt", item.get("question", "")))
        raw_image = str(item.get("image_path", item.get("image", "")))
        image_path = _resolve_case_image(PROJECT_ROOT, mira_root, example_path, raw_image)

        if "answer" in item:
            gold_answer = str(item["answer"])
        elif "answer1" in item and "answer2" in item:
            gold_answer = f"{item['answer1']}||{item['answer2']}"
        else:
            raise KeyError(f"No supported answer field found in {example_path} case {index}")

        cases.append(
            BenchmarkCase(
                case_id=str(item.get("id", item.get("uid", f"example_{index}"))),
                problem_id=str(item.get("problem_id", family)),
                prompt=prompt,
                gold_answer=gold_answer,
                image_path=image_path,
            )
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark all full MIRA datasets.")
    parser.add_argument(
        "--mode",
        choices=["baseline", "learned"],
        required=True,
        help="baseline = pure VLM direct answer; learned = pure ReAct with learned capabilities",
    )
    parser.add_argument(
        "--learned-dir",
        default="",
        help="Optional learned directory to use for learned mode. Defaults to PROJECT_ROOT/learned.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional JSON output path. If omitted, only stdout is used.",
    )
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Optional family filter. Can be passed multiple times.",
    )
    args = parser.parse_args()

    client = VLMClient()
    mira_root = _find_mira_root(PROJECT_ROOT)
    examples = _all_mira_examples(mira_root)
    if args.family:
        wanted = set(args.family)
        examples = [path for path in examples if path.parent.name in wanted]

    learned_dir = Path(args.learned_dir) if args.learned_dir else PROJECT_ROOT / "learned"
    loop = None
    if args.mode == "learned":
        loop = EvolutionLoop(
            work_dir=PROJECT_ROOT / "artifacts" / "benchmark_all_mira",
            learned_dir=learned_dir,
            skills_dir=PROJECT_ROOT / "skills",
            vlm_client=client,
            max_attempts=1,
            subset_id=None,
        )

    family_summaries: list[dict[str, object]] = []
    all_rows: list[dict[str, object]] = []
    total = 0
    correct = 0

    for example_path in examples:
        family = example_path.parent.name
        cases = _build_benchmark_cases(example_path, mira_root)

        family_rows: list[dict[str, object]] = []
        family_correct = 0

        print(f"\n=== FAMILY {family} ({len(cases)} cases) ===")
        for index, case in enumerate(cases, start=1):
            if args.mode == "baseline":
                answer = _direct_vlm_answer(client, case.prompt, case.image_path)
                turns = 1
                artifacts: list[str] = []
            else:
                assert loop is not None
                agent = loop._create_agent(case, attempt=1, phase=f"benchmark_{family}_{index}")
                result = agent.run(case.prompt, case.image_path, initial_observations=[])
                answer = result.final_answer
                turns = result.total_turns
                artifacts = result.get_image_artifacts()

            is_correct = _check_answer(answer, case.gold_answer)
            row = {
                "family": family,
                "case_id": case.case_id,
                "image_path": case.image_path,
                "expected": case.gold_answer,
                "answer": answer,
                "correct": is_correct,
                "turns": turns,
                "artifacts": artifacts,
            }
            family_rows.append(row)
            all_rows.append(row)
            total += 1
            if is_correct:
                family_correct += 1
                correct += 1

            status = "OK" if is_correct else "FAIL"
            print(
                f"[{index:02d}/{len(cases):02d}] {status} "
                f"case={case.case_id} expected={case.gold_answer} answer={answer!r}"
            )

        family_summary = {
            "family": family,
            "example": str(example_path),
            "total": len(family_rows),
            "correct": family_correct,
            "accuracy": (family_correct / len(family_rows)) if family_rows else 0.0,
            "results": family_rows,
        }
        family_summaries.append(family_summary)
        print(
            f"FAMILY SUMMARY {family}: {family_correct}/{len(family_rows)} "
            f"({family_summary['accuracy']:.2%})"
        )

    summary = {
        "mode": args.mode,
        "learned_dir": str(learned_dir) if args.mode == "learned" else "",
        "total": total,
        "correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "families": family_summaries,
        "results": all_rows,
    }

    print("\n=== OVERALL SUMMARY ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
