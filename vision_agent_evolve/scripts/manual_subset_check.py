from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent import AgentConfig, ReActAgent
from core.vlm_client import VLMClient
from evolution.store import CapabilityStore
from run import _build_cases
from skills import discover_skills, render_skills


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a learned subset directly with a ReAct agent.")
    parser.add_argument("--subset", required=True, help="Subset under learned/")
    parser.add_argument("--example", required=True, help="Example JSON/JSONL path")
    parser.add_argument("--problem-id", default=None, help="Optional problem_id override")
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--case-id", default=None, help="Optional single case_id filter")
    parser.add_argument("--dump-steps", action="store_true", help="Print each agent step for debugging")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    subset_dir = project_root / "learned" / args.subset
    skills_dir = project_root / "skills"
    work_dir = project_root / "artifacts" / f"manual_subset_check_{args.subset}"

    store = CapabilityStore(subset_dir)
    vlm = VLMClient()
    foundation = [
        skill
        for skill in discover_skills(skills_dir / "library" / "foundation")
        if skill.name != "try_direct_first"
    ]

    cases = _build_cases(project_root / args.example)
    for case in cases:
        if args.case_id and str(case.case_id) != str(args.case_id):
            continue
        if args.problem_id:
            case.problem_id = args.problem_id
        all_skills = list(foundation)
        learned_skill = store.get_skill(case.capability_family())
        if learned_skill is not None:
            all_skills.append(learned_skill)

        skill_text = render_skills(all_skills)
        agent = ReActAgent(
            client=vlm,
            config=AgentConfig(
                max_turns=args.max_turns,
                work_dir=work_dir / f"case_{case.case_id}",
                learned_dir=subset_dir,
            ),
            tool_definitions="Use: python -m tools [args]",
            extra_instructions=skill_text,
        )
        result = agent.run(case.prompt, case.image_path)
        print(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "problem_id": case.problem_id,
                    "final_answer": result.final_answer,
                    "turns": result.total_turns,
                    "success": result.success,
                },
                ensure_ascii=False,
            )
        )
        if args.dump_steps:
            for step in result.steps:
                payload = {
                    "turn": step.turn,
                    "thought": step.thought,
                    "action": None if step.action is None else {
                        "name": step.action.name,
                        "arguments": step.action.arguments,
                    },
                    "observation": step.observation,
                    "artifacts": step.artifacts,
                    "is_final": step.is_final,
                    "is_format_error": step.is_format_error,
                }
                print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
