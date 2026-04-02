"""Unified CLI entry point for all tools."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[1]))

from tools.builtin_tools import execute_builtin_tool, list_builtin_tools
from tools.dynamic_loader import discover_learned_tools, execute_learned_tool


def _discover_all_learned_tools(learned_dir: Path) -> dict[str, Path]:
    """Discover learned tools from root and subset directories."""
    discovered: dict[str, Path] = {}

    # Root learned/tools/*.py
    discovered.update(discover_learned_tools(learned_dir))

    # Subset learned/<subset>/tools/*.py
    if learned_dir.exists():
        for subset_dir in learned_dir.iterdir():
            if not subset_dir.is_dir():
                continue
            for name, path in discover_learned_tools(subset_dir).items():
                discovered[name] = path

    return discovered


def main():
    """Main CLI dispatcher with dynamic learned tool support."""
    project_root = Path(__file__).parents[1]
    builtin_tools = {tool.name: tool for tool in list_builtin_tools()}
    scoped_learned_dir = os.environ.get("VISION_AGENT_LEARNED_DIR", "").strip()
    if scoped_learned_dir:
        learned_dir = Path(scoped_learned_dir)
        learned_tools = discover_learned_tools(learned_dir)
    else:
        learned_dir = project_root / "learned"
        learned_tools = _discover_all_learned_tools(learned_dir)

    if len(sys.argv) < 2:
        print("Usage: python -m tools <tool_name> [args...]")
        print("\nBuilt-in tools:")
        for tool in sorted(builtin_tools.values(), key=lambda item: item.name):
            print(f"  {tool.name}  - {tool.description}")
            print(f"    usage: {tool.usage_example}")
        if learned_tools:
            print("\nLearned tools:")
            for tool_name in sorted(learned_tools.keys()):
                print(f"  {tool_name}  - Dynamically loaded")
        else:
            print("\nNo learned tools found yet.")
        sys.exit(1)

    tool_name = sys.argv[1]

    if tool_name in builtin_tools:
        if len(sys.argv) < 3 and " <image_path>" in builtin_tools[tool_name].usage_example:
            print(f"Usage: {builtin_tools[tool_name].usage_example}")
            sys.exit(1)
        print(execute_builtin_tool(tool_name, *sys.argv[2:]))
        return

    if tool_name in learned_tools:
        # Execute learned tool
        tool_path = learned_tools[tool_name]
        args = sys.argv[2:]  # All remaining args
        output = execute_learned_tool(tool_path, args)
        print(output)
        return

    print(f"Unknown tool: {tool_name}")
    print("Available built-in tools:")
    for name in sorted(builtin_tools.keys()):
        print(f"  {name}")
    if learned_tools:
        print("Available learned tools:")
        for name in sorted(learned_tools.keys()):
            print(f"  {name}")
    sys.exit(1)


if __name__ == "__main__":
    main()
