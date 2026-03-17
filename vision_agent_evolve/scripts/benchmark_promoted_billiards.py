from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent import AgentConfig, ReActAgent
from core.types import TaskCase
from core.vlm_client import VLMClient
from evolution.store import CapabilityStore
from skills import discover_skills, render_skills


def main() -> None:
    jsonl_path = Path("/Users/macbook/Desktop/exp_ali/MIRA/billiards/billiards.jsonl")
    image_root = jsonl_path.parent / "image"
    learned_dir = PROJECT_ROOT / "learned"
    skills_dir = PROJECT_ROOT / "skills"
    work_root = PROJECT_ROOT / "artifacts" / "benchmark_billiards_promoted"

    store = CapabilityStore(learned_dir)
    foundation = [
        skill
        for skill in discover_skills(skills_dir / "library" / "foundation")
        if skill.name != "try_direct_first"
    ]
    learned_skill = store.get_skill("billiards")
    all_skills = list(foundation)
    if learned_skill is not None:
        all_skills.append(learned_skill)
    skill_text = render_skills(all_skills)

    client = VLMClient()
    cases: list[TaskCase] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        image_name = Path(item["image_path"]).name
        cases.append(
            TaskCase(
                case_id=str(item["uid"]),
                problem_id="billiards",
                prompt=item["question"],
                gold_answer=str(item["answer"]),
                image_path=str(image_root / image_name),
            )
        )

    results: list[dict[str, object]] = []
    correct = 0
    for case in cases:
        agent = ReActAgent(
            client=client,
            config=AgentConfig(
                max_turns=10,
                work_dir=work_root / f"case_{case.case_id}",
                learned_dir=learned_dir,
            ),
            tool_definitions="Use: python -m tools [args]",
            extra_instructions=skill_text,
        )
        result = agent.run(case.prompt, case.image_path)
        final_answer = str(result.final_answer).strip()
        ok = final_answer == str(case.gold_answer)
        correct += int(ok)
        record = {
            "case_id": case.case_id,
            "answer": final_answer,
            "gold": str(case.gold_answer),
            "turns": result.total_turns,
            "ok": ok,
        }
        results.append(record)
        print(json.dumps(record, ensure_ascii=False))

    summary = {
        "correct": correct,
        "total": len(cases),
        "accuracy": round(correct / len(cases), 4) if cases else 0.0,
        "failed_cases": [record["case_id"] for record in results if not record["ok"]],
    }
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
