from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.structured_data import (
    check_chartqa_answer,
    load_normalized_cases,
    normalize_chartqa_dataset,
)
from core.types import AgentAction, AgentResult, AgentStep, TaskCase
from evolution.loop import EvolutionLoop
from evolution.store import CapabilityStore
from evolution.structured_runner import (
    StructuredBenchmarkRunner,
    StructuredCaseRecord,
    StructuredExperimentConfig,
    _aggregate_records,
)
from evolution.types import SkillProposal, ToolChainContext


class DummyClient:
    def chat(self, messages, settings=None):
        raise AssertionError("Unexpected VLM call in this test")


class FakeAgent:
    def __init__(self, answer: str, tool_name: str | None = None, artifact: str | None = None):
        self.answer = answer
        self.tool_name = tool_name
        self.artifact = artifact

    def run(self, task: str, image_path: str = "", initial_observations=None) -> AgentResult:
        steps: list[AgentStep] = []
        artifacts: list[str] = []
        if self.tool_name:
            observation = "STATUS: ok"
            if self.artifact:
                observation += f"\nARTIFACTS: {self.artifact}"
                artifacts.append(self.artifact)
            steps.append(
                AgentStep(
                    turn=1,
                    action=AgentAction(
                        name="bash",
                        arguments={"command": f"python -m tools {self.tool_name} <image_path>"},
                    ),
                    observation=observation,
                    artifacts=artifacts,
                )
            )
        return AgentResult(
            task=task,
            final_answer=self.answer,
            steps=steps,
            total_turns=max(1, len(steps)),
            success=True,
            all_artifacts=artifacts,
        )


class FakeValidator:
    def build_chain_context(self, case: TaskCase, skill_content: str | None, attempt=None):
        return ToolChainContext(latest_input_image=case.image_path)


class FakeLoop:
    _chain_observations_for_agent = staticmethod(EvolutionLoop._chain_observations_for_agent)

    def __init__(self, subset_dir: Path):
        self.store = CapabilityStore(subset_dir)
        self.validator = FakeValidator()
        self.run_single_case_calls: list[str] = []

    def _create_agent(self, case, attempt=None, phase="solve", **kwargs):
        learned = self.store.has_skill("chartqa")
        if case.case_id == "1":
            return FakeAgent(case.gold_answer)
        if case.case_id == "2":
            if learned:
                return FakeAgent(case.gold_answer, tool_name="focus_chart", artifact="artifacts/case2.png")
            return FakeAgent("wrong")
        if case.case_id == "3":
            if learned:
                return FakeAgent(case.gold_answer)
            return FakeAgent("wrong")
        return FakeAgent("wrong")

    def run_single_case(self, case):
        self.run_single_case_calls.append(case.case_id)
        self.store.promote_skill(
            "chartqa",
            SkillProposal(
                name="chartqa",
                description="Use the learned chart focus tool when direct reading fails.",
                applicability_conditions="Use when chart text or bars need local emphasis.",
                content="## SOP\n1. Run `python -m tools focus_chart <image_path>`.\n2. Answer from the improved chart artifact.",
                level="mid",
                depends_on=[],
            ),
        )
        return True


class FrozenLoop(FakeLoop):
    def run_single_case(self, case):
        raise AssertionError("Frozen evaluation must not mutate or evolve")


class TestStructuredRunner(StructuredBenchmarkRunner):
    def __init__(self, config, project_root, online_loop: FakeLoop, frozen_loop: FakeLoop):
        super().__init__(config=config, project_root=project_root, vlm_client=DummyClient())
        self._online_loop = online_loop
        self._frozen_loop = frozen_loop

    def _direct_answer(self, case: TaskCase) -> str:
        return "direct"

    def _create_plain_react_agent(self, case: TaskCase, phase: str):
        return FakeAgent(case.gold_answer if case.case_id == "1" else "wrong")

    def _make_online_loop(self):
        return self._online_loop

    def _make_frozen_loop(self, snapshot_name: str | None = None, subset_id: str | None = None):
        return self._frozen_loop


class StructuredBenchmarkTests(unittest.TestCase):
    def _write_image(self, path: Path, size=(12, 8)) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color=(255, 255, 255)).save(path)

    def _write_normalized_chartqa(self, root: Path, split: str, rows: list[dict]) -> None:
        dataset_root = root / "chartqa"
        dataset_root.mkdir(parents=True, exist_ok=True)
        split_file = dataset_root / f"{split}.jsonl"
        with split_file.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    def test_chartqa_normalization_creates_valid_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_root = root / "raw"
            normalized_root = root / "normalized"
            image_path = raw_root / "images" / "chart_1.png"
            self._write_image(image_path, size=(23, 17))
            (raw_root / "train.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "sample_1",
                            "question": "How many bars are shown?",
                            "answer": "4",
                            "imgname": "chart_1.png",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            manifest = normalize_chartqa_dataset(raw_root, normalized_root, splits=["train"])
            cases = load_normalized_cases(normalized_root, "chartqa", "train")

            self.assertEqual(manifest["splits"]["train"]["count"], 1)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].problem_id, "chartqa")
            self.assertEqual(cases[0].metadata["dataset_name"], "chartqa")
            self.assertEqual(cases[0].metadata["split"], "train")
            self.assertEqual(cases[0].metadata["source_id"], "sample_1")
            self.assertEqual(cases[0].metadata["answer_type"], "numeric")
            self.assertEqual(cases[0].metadata["image_width"], 23)
            self.assertEqual(cases[0].metadata["image_height"], 17)

    def test_online_evolve_skips_initially_correct_cases_and_reuses_shared_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            self._write_image(chart_dir / "2.png")
            self._write_image(chart_dir / "3.png")

            rows = [
                {
                    "id": "1",
                    "problem_id": "chartqa",
                    "prompt": "Q1",
                    "answer": "A",
                    "image_path": str(chart_dir / "1.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "train", "source_id": "1", "question_type": "generic", "answer_type": "string"},
                },
                {
                    "id": "2",
                    "problem_id": "chartqa",
                    "prompt": "Q2",
                    "answer": "B",
                    "image_path": str(chart_dir / "2.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "train", "source_id": "2", "question_type": "generic", "answer_type": "string"},
                },
                {
                    "id": "3",
                    "problem_id": "chartqa",
                    "prompt": "Q3",
                    "answer": "C",
                    "image_path": str(chart_dir / "3.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "train", "source_id": "3", "question_type": "generic", "answer_type": "string"},
                },
            ]
            self._write_normalized_chartqa(root / "normalized", "train", rows)

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v1",
                k=3,
            )
            online_loop = FakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            cases = load_normalized_cases(config.normalized_data_root, "chartqa", "train", limit=3)
            records, snapshot_name = runner._run_online_evolve(cases)

            self.assertEqual(snapshot_name, "chartqa_refocus_v1_train_k3_snapshot")
            self.assertEqual(online_loop.run_single_case_calls, ["2"])
            self.assertFalse(records[0].evolve_triggered)
            self.assertTrue(records[1].evolve_triggered)
            self.assertFalse(records[2].evolve_triggered)
            self.assertTrue(records[2].correct)
            self.assertTrue((root / "learned" / "snapshots" / snapshot_name).exists())

    def test_frozen_transfer_uses_existing_capabilities_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            row = {
                "id": "1",
                "problem_id": "chartqa",
                "prompt": "Q1",
                "answer": "A",
                "image_path": str(chart_dir / "1.png"),
                "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "1", "question_type": "generic", "answer_type": "string"},
            }
            self._write_normalized_chartqa(root / "normalized", "val", [row])

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v1",
            )
            online_loop = FakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            frozen_loop.store.promote_skill(
                "chartqa",
                SkillProposal(
                    name="chartqa",
                    description="Frozen chart skill.",
                    applicability_conditions="Use when chart focus helps.",
                    content="## SOP\n1. Use learned chart rules.",
                    level="mid",
                    depends_on=[],
                ),
            )
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            records = runner.run_frozen_transfer(subset_id=config.subset_id)

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].correct)

    def test_metrics_aggregation_captures_accuracy_tool_and_readability_stats(self):
        rows = [
            StructuredCaseRecord(
                setting="online_evolve",
                split="train",
                case_id="1",
                problem_id="chartqa",
                expected="A",
                answer="A",
                correct=True,
                turns=2,
                tool_count=1,
                tool_names=["focus_chart"],
                used_tool=True,
                artifact_paths=["artifacts/1.png"],
                readability_improved="yes",
                target_region_clearer=4,
                text_or_marks_more_legible=5,
                overall_usefulness=4,
            ),
            StructuredCaseRecord(
                setting="online_evolve",
                split="train",
                case_id="2",
                problem_id="chartqa",
                expected="B",
                answer="wrong",
                correct=False,
                turns=1,
                tool_count=0,
                tool_names=[],
                used_tool=False,
                artifact_paths=[],
            ),
        ]

        summary = _aggregate_records(rows)["online_evolve"]

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["correct"], 1)
        self.assertAlmostEqual(summary["accuracy"], 0.5)
        self.assertAlmostEqual(summary["tool_usage_rate"], 0.5)
        self.assertAlmostEqual(summary["avg_tool_calls_per_case"], 0.5)
        self.assertAlmostEqual(summary["artifact_production_rate"], 0.5)
        self.assertEqual(summary["readability_summary"]["judged_cases"], 1)
        self.assertAlmostEqual(summary["readability_summary"]["readability_improved_rate"], 1.0)
        self.assertEqual(summary["readability_summary"]["manual_spotcheck_case_ids"], ["1"])

    def test_chartqa_answer_checker_handles_numeric_and_string_matches(self):
        self.assertTrue(check_chartqa_answer("4", "4"))
        self.assertTrue(check_chartqa_answer("The answer is 4", "4"))
        self.assertTrue(check_chartqa_answer("4.0", "4"))
        self.assertFalse(check_chartqa_answer("5", "4"))


if __name__ == "__main__":
    unittest.main()
