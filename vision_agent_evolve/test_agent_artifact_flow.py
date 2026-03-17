"""Focused tests for artifact visibility across agent turns."""

from __future__ import annotations

import base64
import tempfile
import unittest
from pathlib import Path

from core.agent import AgentConfig, ReActAgent


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yf9cAAAAASUVORK5CYII="
)


class AgentArtifactFlowTests(unittest.TestCase):
    def _make_agent(self, root: Path) -> ReActAgent:
        agent = ReActAgent(client=None, config=AgentConfig(work_dir=root / "artifacts"))
        agent.project_root = root
        agent.work_dir = root / "artifacts"
        agent.work_dir.mkdir(parents=True, exist_ok=True)
        return agent

    def _write_png(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG_1X1)

    def test_observation_embeds_project_relative_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_png(root / "artifacts" / "flipped.png")
            agent = self._make_agent(root)

            content = agent._build_observation_content(
                "ANSWER: ok\nSTATUS: ok\nARTIFACTS: artifacts/flipped.png",
                ["artifacts/flipped.png"],
            )

            self.assertIsInstance(content, list)
            image_parts = [part for part in content if part["type"] == "image_url"]
            self.assertEqual(len(image_parts), 1)
            self.assertTrue(image_parts[0]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_normalize_artifacts_finds_legacy_nested_workdir_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested_output = root / "artifacts" / "artifacts" / "flipped.png"
            self._write_png(nested_output)
            agent = self._make_agent(root)

            normalized = agent._normalize_artifacts(["artifacts/flipped.png"])

            self.assertEqual(normalized, ["artifacts/artifacts/flipped.png"])

            content = agent._build_observation_content("Observation", normalized)
            image_parts = [part for part in content if part["type"] == "image_url"]
            self.assertEqual(len(image_parts), 1)

    def test_run_bash_uses_project_root_for_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_file = root / "datasets" / "sample.txt"
            data_file.parent.mkdir(parents=True, exist_ok=True)
            data_file.write_text("visible-from-project-root", encoding="utf-8")
            agent = self._make_agent(root)

            output = agent._run_bash(
                'python -c "from pathlib import Path; print(Path(\'datasets/sample.txt\').read_text())"'
            )

            self.assertIn("visible-from-project-root", output)


if __name__ == "__main__":
    unittest.main()
