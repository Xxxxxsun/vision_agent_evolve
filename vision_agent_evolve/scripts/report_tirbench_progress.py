"""Report progress for a TIR-Bench run directory."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Report partial or final TIR-Bench run progress.")
    parser.add_argument("run_dir", help="Directory containing tirbench_results_detailed.json")
    parser.add_argument("--total", type=int, default=1215)
    args = parser.parse_args()

    detailed_path = Path(args.run_dir) / "tirbench_results_detailed.json"
    if not detailed_path.exists():
        print(json.dumps({"completed": 0, "total": args.total, "exists": False}, indent=2))
        return

    rows = json.loads(detailed_path.read_text(encoding="utf-8"))
    task_scores: dict[str, list[float]] = defaultdict(list)
    tool_counts = Counter()
    tool_errors = Counter()
    for row in rows:
        task_scores[str(row.get("task", ""))].append(float(row.get("score", 0.0) or 0.0))
        for call in row.get("tool_calls", []):
            name = str(call.get("name", ""))
            tool_counts[name] += 1
            if call.get("status") != "ok":
                tool_errors[name] += 1

    completed = len(rows)
    payload = {
        "exists": True,
        "completed": completed,
        "total": args.total,
        "completion": completed / args.total if args.total else 0.0,
        "accuracy_so_far": sum(float(row.get("score", 0.0) or 0.0) for row in rows) / completed if completed else 0.0,
        "last_case_id": rows[-1].get("case_id") if rows else None,
        "last_task": rows[-1].get("task") if rows else None,
        "task_accuracy_so_far": {
            task: sum(scores) / len(scores)
            for task, scores in sorted(task_scores.items())
            if scores
        },
        "tool_counts": dict(sorted(tool_counts.items())),
        "tool_error_counts": dict(sorted(tool_errors.items())),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
