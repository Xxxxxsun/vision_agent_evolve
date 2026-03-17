"""Main entry point for vision agent evolve."""

import argparse
import json
from pathlib import Path

from core.vlm_client import VLMClient
from core.types import TaskCase
from evolution.loop import EvolutionLoop


def _load_json_objects(example_path: Path) -> list[dict]:
    """Load one or more JSON objects from a file.

    Supports:
    - a single JSON object
    - a JSON list of objects
    - concatenated/JSONL-style top-level objects
    """
    raw = example_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    items: list[dict] = []
    idx = 0
    length = len(raw)
    while idx < length:
        while idx < length and raw[idx].isspace():
            idx += 1
        if idx >= length:
            break
        obj, next_idx = decoder.raw_decode(raw, idx)
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object at offset {idx}, got {type(obj).__name__}")
        items.append(obj)
        idx = next_idx
    return items


def _infer_problem_id(prompt: str) -> str:
    text = prompt.lower()
    if "clock" in text and "mirror" in text:
        return "mirror_clock"
    return "unknown"


def _resolve_image_path(raw_path: str, example_path: Path) -> str:
    if not raw_path:
        return ""

    candidate = Path(raw_path)
    if candidate.is_absolute() and candidate.exists():
        return str(candidate)

    project_root = Path(__file__).parent
    lookup = [
        project_root / candidate,
        example_path.parent / candidate,
        example_path.parent / "images" / candidate.name,
    ]
    for path in lookup:
        if path.exists():
            try:
                return str(path.relative_to(project_root))
            except ValueError:
                return str(path)
    return raw_path


def _build_cases(example_path: Path) -> list[TaskCase]:
    cases: list[TaskCase] = []
    for index, item in enumerate(_load_json_objects(example_path), start=1):
        prompt = item.get("prompt", item.get("question", ""))
        case_id = str(item.get("id", item.get("uid", f"example_{index}")))
        problem_id = str(item.get("problem_id") or _infer_problem_id(prompt))
        image_path = _resolve_image_path(
            item.get("image_path", item.get("image", "")),
            example_path,
        )
        dense_caption = str(item.get("dense_caption", item.get("caption", ""))).strip()
        cases.append(
            TaskCase(
                case_id=case_id,
                problem_id=problem_id,
                prompt=prompt,
                gold_answer=item["answer"],
                image_path=image_path,
                metadata={"dense_caption": dense_caption} if dense_caption else {},
            )
        )
    return cases


def main():
    parser = argparse.ArgumentParser(description="Vision Agent Self-Evolution")
    parser.add_argument(
        "--mode",
        choices=["evolve", "test"],
        default="evolve",
        help="Mode: evolve (self-improve) or test (single run)",
    )
    parser.add_argument(
        "--example",
        type=str,
        required=True,
        help="Path to example JSON file",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=10,
        help="Max evolution attempts per case",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("artifacts"),
        help="Working directory for artifacts",
    )
    parser.add_argument(
        "--subset",
        type=str,
        default=None,
        help="Subset ID for isolated evolution (e.g., 'mirror_clock', 'defuse_bomb'). Each subset has its own learned/ directory.",
    )

    args = parser.parse_args()

    # Load example
    example_path = Path(args.example)
    if not example_path.exists():
        print(f"Error: Example file not found: {example_path}")
        return

    cases = _build_cases(example_path)
    if not cases:
        print(f"Error: No cases found in {example_path}")
        return

    # Setup directories
    project_root = Path(__file__).parent
    work_dir = args.work_dir
    work_dir.mkdir(exist_ok=True)

    learned_dir = project_root / "learned"
    skills_dir = project_root / "skills"

    # Create VLM client
    vlm_client = VLMClient()

    if args.mode == "evolve":
        print("=== Vision Agent Self-Evolution ===\n")
        print(f"Cases: {len(cases)}")
        print(f"Max attempts: {args.max_attempts}")
        if args.subset:
            print(f"Subset: {args.subset} (isolated evolution)")
            print(f"Learned directory: learned/{args.subset}/")
        print()

        # Run evolution loop
        loop = EvolutionLoop(
            work_dir=work_dir,
            learned_dir=learned_dir,
            skills_dir=skills_dir,
            vlm_client=vlm_client,
            max_attempts=args.max_attempts,
            subset_id=args.subset,
        )

        all_success = True
        for idx, case in enumerate(cases, start=1):
            print(f"\n### Case {idx}/{len(cases)}: {case.case_id} ({case.problem_id})")
            print(f"Task: {case.prompt}")
            success = loop.run_single_case(case)
            if success:
                print(f"\n✓✓✓ SUCCESS! Case {case.case_id} solved. ✓✓✓")
            else:
                print(f"\n✗✗✗ FAILED to solve case {case.case_id}. ✗✗✗")
                all_success = False
                break

        if len(cases) > 1:
            print("\n=== Overall Result ===")
            print("All cases solved." if all_success else "Stopped before solving all cases.")

    elif args.mode == "test":
        print("=== Test Mode (Single Run) ===\n")

        from core.agent import ReActAgent, AgentConfig
        from evolution.store import CapabilityStore
        from skills import discover_skills, render_skills

        # Load only neutral foundation skills plus the current task-family skill.
        foundation_skills = [
            skill for skill in discover_skills(skills_dir / "library" / "foundation")
            if skill.name != "try_direct_first"
        ]
        all_skills = list(foundation_skills)
        store = CapabilityStore(learned_dir)
        case = cases[0]
        learned_skill = store.get_skill(case.problem_id)
        if learned_skill is not None:
            all_skills.append(learned_skill)

        skill_text = render_skills(all_skills)

        # Create and run agent
        config = AgentConfig(max_turns=20, work_dir=work_dir)
        agent = ReActAgent(
            client=vlm_client,
            config=config,
            tool_definitions="Use: python -m tools <tool_name> [args]",
            extra_instructions=skill_text,
        )

        result = agent.run(case.prompt, case.image_path)

        print(f"\nAgent answer: {result.final_answer}")
        print(f"Expected: {case.gold_answer}")
        print(f"Success: {result.success}")
        print(f"Turns used: {result.total_turns}")


if __name__ == "__main__":
    main()
