"""
Quick sanity-check for the new MathVista tool gate logic.

Run:
    python test_mathvista_gate.py

Tests:
1. Classification logic — verify which cases are "pure visual perception" vs "needs tools"
2. (Optional) Live API test using OpenRouter to verify the model uses tools correctly
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.types import TaskCase
from core.tool_calling_runtime import _mathvista_is_pure_visual_perception, _apply_case_tool_gate
from core.skill_routing import ResolvedSkillContext
from core.tool_calling_runtime import ToolCallingRuntimeConfig


def make_case(prompt: str, choices: dict | None = None, answer_type: str = "integer") -> TaskCase:
    return TaskCase(
        case_id="test",
        problem_id="mathvista",
        prompt=prompt,
        gold_answer="",
        image_path="",
        metadata={
            "dataset_name": "mathvista",
            "answer_type": answer_type,
            "choices": choices or {},
            "capability_family": "mathvista_test",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Classification logic tests
# ─────────────────────────────────────────────────────────────────────────────

CASES_NO_TOOLS = [
    # Yes/No MCQ
    ("Is the number of apples greater than oranges?", {"A": "Yes", "B": "No"}),
    ("Does the curve increase monotonically?", {"A": "Yes", "B": "No"}),
    # Pattern completion
    ("Which figure comes next in the sequence?", {"A": "△", "B": "□", "C": "○", "D": "◇"}),
    ("Complete the matrix. What is the missing picture?", {"A": "X", "B": "Y", "C": "Z"}),
    ("Which net of the cube is correct?", {"A": "net1", "B": "net2", "C": "net3"}),
    ("The paper folding result is which shape?", {"A": "circle", "B": "square"}),
    ("Select the figure that comes next in the sequence.", {"A": "A", "B": "B", "C": "C"}),
]

CASES_NEEDS_TOOLS = [
    # Geometry
    ("What is the area of the triangle with base 6 and height shown in the figure?", None),
    ("Find the value of angle x in the diagram.", {"A": "30", "B": "45", "C": "60", "D": "90"}),
    # Chart reading
    ("What is the value shown in the bar chart for 2019?", None),
    ("How many bars in the chart exceed the threshold of 50?", None),
    ("What is the mean score across all subjects shown?", None),
    # Measurement
    ("What length does the ruler show?", None),
    ("What is the reading on the dial?", None),
    # Arithmetic MCQ with numbers
    ("What is the perimeter of the rectangle?", {"A": "12", "B": "16", "C": "20", "D": "24"}),
    # Stats
    ("What is the median of the data shown in the box plot?", None),
    # Free-form float
    ("Calculate the slope of the line shown.", None, "float"),
    # Normal counting that needs zoom
    ("How many triangles are in the figure?", None),
    # Comparison question
    ("Is the sum of the two smallest bars greater than the largest bar?",
     {"A": "Yes", "B": "No", "C": "Cannot be determined"}),  # 3 choices, not pure yes/no
]


def run_classification_tests() -> None:
    print("=" * 60)
    print("Classification tests")
    print("=" * 60)

    passed = 0
    failed = 0

    print("\n[Should be no-tools]")
    for item in CASES_NO_TOOLS:
        prompt, choices = item[0], item[1]
        answer_type = item[2] if len(item) > 2 else "integer"
        case = make_case(prompt, choices, answer_type)
        result = _mathvista_is_pure_visual_perception(case)
        status = "✓ PASS" if result else "✗ FAIL"
        if result:
            passed += 1
        else:
            failed += 1
        print(f"  {status}  {prompt[:60]!r}")

    print("\n[Should need tools]")
    for item in CASES_NEEDS_TOOLS:
        prompt, choices = item[0], item[1]
        answer_type = item[2] if len(item) > 2 else "integer"
        case = make_case(prompt, choices, answer_type)
        result = _mathvista_is_pure_visual_perception(case)
        status = "✓ PASS" if not result else "✗ FAIL"
        if not result:
            passed += 1
        else:
            failed += 1
        print(f"  {status}  {prompt[:60]!r}")

    print(f"\n{passed}/{passed+failed} passed")


def run_gate_tests() -> None:
    """Verify that the gate correctly sets effective_tool_names.

    New strategy (data-driven from doubao-seed-2.0-pro 900-case analysis):
      - pure visual perception (yes/no MCQ, IQ matrix) → no tools
      - everything else → execute_python only (no zoom/crop)
    """
    print("\n" + "=" * 60)
    print("Tool gate integration tests")
    print("=" * 60)

    config = ToolCallingRuntimeConfig(enable_tools=True)

    # (prompt, choices, expected_tool_set)
    test_cases = [
        # Pure visual perception → no tools
        ("Which figure comes next in the sequence?", {"A": "△", "B": "□"}, set()),
        ("Is the blue bar taller than the red bar?", {"A": "Yes", "B": "No"}, set()),
        # Everything else → python only, no zoom
        ("What is the area of the triangle shown in the figure?", None, {"execute_python"}),
        ("Find the value of angle x.", {"A": "30", "B": "45"}, {"execute_python"}),
        ("What is the mean of the values in the chart?", None, {"execute_python"}),
        ("How many triangles are in the figure?", None, {"execute_python"}),
    ]

    passed = failed = 0
    for prompt, choices, expected_tools in test_cases:
        case = make_case(prompt, choices)
        ctx = ResolvedSkillContext()
        ctx.effective_tool_names = ["dummy"]
        _apply_case_tool_gate(case, ctx, config)

        actual_tools = set(t for t in ctx.effective_tool_names if t != "__no_tools__")
        ok = actual_tools == expected_tools
        passed += ok; failed += not ok
        zoom_exposed = "zoom_image" in actual_tools or "crop_image" in actual_tools
        tools_str = str(sorted(actual_tools)) if actual_tools else "none"
        print(f"  {'✓' if ok else '✗'}  tools={tools_str:<30} zoom={'YES ← BAD' if zoom_exposed else 'no'}  {prompt[:45]!r}")

    print(f"\n{passed}/{passed+failed} passed")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Live API test (optional)
# ─────────────────────────────────────────────────────────────────────────────

def run_live_api_test() -> None:
    """Send a few MathVista-style text questions to OpenRouter and check answers."""
    try:
        from openai import OpenAI
    except ImportError:
        print("\n[Skip] openai package not installed — skipping live API test.")
        return

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("\n[Skip] Set OPENROUTER_API_KEY to run live API tests.")
        return
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    model = "openai/gpt-4o"

    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Execute Python code. Always use print() to output results.",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                },
            },
        }
    ]

    # Simple arithmetic problems the model should use execute_python for
    test_questions = [
        {
            "q": "A triangle has angles of 55° and 72°. What is the third angle in degrees? Final answer must be one integer only.",
            "expected": "53",
        },
        {
            "q": "A rectangle has length 8 and width 5. What is its perimeter? Final answer must be one integer only.",
            "expected": "26",
        },
        {
            "q": "The values are 12, 15, 9, 18, 11. What is the mean? Round to 1 decimal. Final answer must be one decimal number only.",
            "expected": "13.0",
        },
    ]

    print("\n" + "=" * 60)
    print("Live API tests (OpenRouter / gpt-4o)")
    print("=" * 60)

    for item in test_questions:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are solving multimodal benchmark questions. "
                    "Use execute_python to verify arithmetic. "
                    "The final line of your response must begin with 'Final answer:'."
                ),
            },
            {"role": "user", "content": item["q"]},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tool_schemas,
            max_tokens=512,
        )
        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []
        used_tool = bool(tool_calls)

        # If tool was called, execute and get follow-up
        if tool_calls:
            code = json.loads(tool_calls[0].function.arguments).get("code", "")
            import io, contextlib
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(code, {})
                output = buf.getvalue().strip()
            except Exception as e:
                output = str(e)

            messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": tool_calls[0].id, "type": "function",
                 "function": {"name": "execute_python", "arguments": tool_calls[0].function.arguments}}
            ]})
            messages.append({"role": "tool", "tool_call_id": tool_calls[0].id, "content": output})

            response2 = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=128,
            )
            final_text = response2.choices[0].message.content or ""
        else:
            final_text = msg.content or ""

        import re
        m = re.search(r"Final answer:\s*(.+)$", final_text, re.IGNORECASE | re.MULTILINE)
        answer = m.group(1).strip() if m else final_text.strip()

        correct = answer == item["expected"]
        print(f"  {'✓' if correct else '~'}  used_tool={used_tool}  answer={answer!r}  expected={item['expected']!r}")
        print(f"     Q: {item['q'][:70]}")


if __name__ == "__main__":
    run_classification_tests()
    run_gate_tests()
    run_live_api_test()
