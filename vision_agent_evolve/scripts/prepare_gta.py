"""Convert GTA benchmark dataset into normalized JSONL format for the evolution framework.

Usage:
    python scripts/prepare_gta.py \
        --gta-root opencompass/data/gta_dataset \
        --output-root datasets/structured_gta \
        --train-ratio 0.3

This produces:
    datasets/structured_gta/gta/train.jsonl
    datasets/structured_gta/gta/val.jsonl
    datasets/structured_gta/gta/manifest.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _build_tool_description(tools: list[dict]) -> str:
    """Format tool metadata into a concise tool catalog string."""
    lines = []
    for t in tools:
        inputs = ", ".join(
            f"{inp['name']}:{inp['type']}" for inp in t.get("inputs", [])
        )
        outputs = ", ".join(
            out.get("type", "any") for out in t.get("outputs", [])
        )
        lines.append(f"- {t['name']}({inputs}) -> {outputs}: {t['description']}")
    return "\n".join(lines)


def _extract_gt_tool_chain(dialogs: list[dict]) -> list[dict]:
    """Extract the ground-truth tool call sequence from dialogs."""
    chain = []
    for turn in dialogs:
        if turn.get("role") == "assistant" and turn.get("tool_calls"):
            for tc in turn["tool_calls"]:
                func = tc.get("function", {})
                chain.append({
                    "tool": func.get("name", ""),
                    "arguments": func.get("arguments", {}),
                    "thought": turn.get("thought", ""),
                })
    return chain


def _classify_tool_category(tools: list[str]) -> str:
    """Classify the primary tool category for family grouping."""
    perception = {"OCR", "ImageDescription", "RegionAttributeDescription",
                  "CountGivenObject", "TextToBbox", "MathOCR"}
    operation = {"DrawBox", "AddText", "GoogleSearch"}
    logic = {"Calculator", "Plot", "Solver"}
    creativity = {"TextToImage", "ImageStylization"}

    tool_set = set(tools)
    cats = []
    if tool_set & perception:
        cats.append("perception")
    if tool_set & operation:
        cats.append("operation")
    if tool_set & logic:
        cats.append("logic")
    if tool_set & creativity:
        cats.append("creativity")
    return "+".join(cats) if cats else "unknown"


def convert(gta_root: Path, output_root: Path, train_ratio: float, seed: int) -> None:
    dataset_file = gta_root / "dataset.json"
    toolmeta_file = gta_root / "toolmeta.json"
    image_dir = gta_root / "image"

    with open(dataset_file) as f:
        raw_data = json.load(f)
    with open(toolmeta_file) as f:
        toolmeta = json.load(f)

    cases = []
    for qid, item in sorted(raw_data.items(), key=lambda x: int(x[0])):
        user_query = ""
        for d in item["dialogs"]:
            if d["role"] == "user":
                user_query = d["content"]
                break

        files = item.get("files", [])
        image_paths = []
        for f in files:
            local_path = gta_root / f["path"]
            if local_path.exists():
                image_paths.append(str(local_path.resolve()))
            else:
                image_paths.append(str(local_path))

        gt_answer_raw = item.get("gt_answer")
        if isinstance(gt_answer_raw, dict):
            whitelist = gt_answer_raw.get("whitelist", [[]])
            blacklist = gt_answer_raw.get("blacklist")
            answer_str = str(whitelist[0][0]) if whitelist and whitelist[0] else ""
        elif isinstance(gt_answer_raw, list) and gt_answer_raw:
            whitelist = [[str(gt_answer_raw[0])]]
            blacklist = None
            answer_str = str(gt_answer_raw[0])
        else:
            whitelist = [[]]
            blacklist = None
            answer_str = ""

        gt_tools = [t["name"] for t in item.get("tools", [])]
        gt_chain = _extract_gt_tool_chain(item["dialogs"])
        tool_category = _classify_tool_category(gt_tools)

        tool_catalog = _build_tool_description(
            [toolmeta[t] for t in toolmeta if t in set(gt_tools)]
            if toolmeta else item.get("tools", [])
        )

        # Build prompt: include query + available tools + image references
        image_refs = "\n".join(f"[Image {i+1}]: {p}" for i, p in enumerate(image_paths))
        prompt = (
            f"{user_query}\n\n"
            f"You have access to the following tools:\n{tool_catalog}\n\n"
            f"Images provided:\n{image_refs}"
        )

        cases.append({
            "id": f"gta_{qid}",
            "problem_id": f"gta_{tool_category}",
            "prompt": prompt,
            "answer": answer_str,
            "image_path": image_paths[0] if image_paths else "",
            "metadata": {
                "dataset_name": "gta",
                "source_id": qid,
                "question_type": tool_category,
                "answer_type": "free_form",
                "gt_tools": gt_tools,
                "gt_tool_chain": gt_chain,
                "gt_answer_whitelist": whitelist,
                "gt_answer_blacklist": blacklist,
                "all_image_paths": image_paths,
                "num_tools": len(gt_tools),
                "num_steps": len(gt_chain),
                "tool_category": tool_category,
                "capability_family": f"gta_{tool_category}",
            },
        })

    # Filter out cases without gold answers (creativity/operation tasks with no ground truth)
    scorable = [c for c in cases if c["answer"].strip()]
    skipped = len(cases) - len(scorable)
    if skipped:
        print(f"Filtered out {skipped} cases without gold answers (creativity/open-ended tasks)")
    cases = scorable

    # Split into train/val
    random.seed(seed)
    indices = list(range(len(cases)))
    random.shuffle(indices)
    train_size = max(1, int(len(cases) * train_ratio))
    train_indices = sorted(indices[:train_size])
    val_indices = sorted(indices[train_size:])

    output_dir = output_root / "gta"
    output_dir.mkdir(parents=True, exist_ok=True)

    for split_name, split_indices in [("train", train_indices), ("val", val_indices)]:
        split_file = output_dir / f"{split_name}.jsonl"
        with open(split_file, "w") as f:
            for idx in split_indices:
                f.write(json.dumps(cases[idx], ensure_ascii=False) + "\n")
        print(f"Wrote {len(split_indices)} cases to {split_file}")

    manifest = {
        "dataset_name": "gta",
        "total_cases": len(cases),
        "train_cases": len(train_indices),
        "val_cases": len(val_indices),
        "train_ratio": train_ratio,
        "seed": seed,
        "unique_tools": sorted(set(t for c in cases for t in c["metadata"]["gt_tools"])),
        "tool_categories": sorted(set(c["metadata"]["tool_category"] for c in cases)),
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Manifest: {json.dumps(manifest, indent=2)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare GTA dataset for evolution framework.")
    parser.add_argument("--gta-root", type=Path, required=True, help="Path to gta_dataset directory")
    parser.add_argument("--output-root", type=Path, required=True, help="Output directory for normalized JSONL")
    parser.add_argument("--train-ratio", type=float, default=0.3, help="Fraction of data for training")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split")
    args = parser.parse_args()
    convert(args.gta_root, args.output_root, args.train_ratio, args.seed)


if __name__ == "__main__":
    main()
