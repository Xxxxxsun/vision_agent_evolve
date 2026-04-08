from __future__ import annotations

import json
import os
import tempfile
import unittest
import base64
import importlib.util
from io import BytesIO
from pathlib import Path
from unittest import mock

from PIL import Image

from core.structured_data import (
    check_chartqa_answer,
    check_mathvista_answer,
    check_multiple_choice_answer,
    infer_choices_from_prompt,
    load_normalized_cases,
    normalize_chartqa_dataset,
    normalize_gta_dataset,
    normalize_hrbench_dataset,
    normalize_mathvista_dataset,
    normalize_textvqa_dataset,
    normalize_vstar_dataset,
    score_textvqa_answer,
)
from core.agent import AgentConfig, ReActAgent
from core.types import AgentAction, AgentResult, AgentStep, TaskCase
from evolution.benchmark_adapters import GTAAdapter, ChartQAAdapter, HRBenchAdapter, MathVistaAdapter, TextVQAAdapter, VStarAdapter, available_benchmark_datasets
from evolution.loop import EvolutionLoop
from evolution.roles import AnalyzerDecider, Generator
from evolution.store import CapabilityStore
from evolution.subset_loop import SubsetEvaluator, SubsetEvolutionLoop, SubsetEvolutionRunReport, SubsetPlanner
from evolution.structured_runner import (
    StructuredBenchmarkRunner,
    StructuredCaseRecord,
    StructuredExperimentConfig,
    _aggregate_records,
)
from evolution.validator import Validator
from evolution.types import (
    CapabilityBundleProposal,
    CandidateEvalResult,
    CoverageContract,
    FailedDirection,
    FailureAnalysis,
    FamilyMemory,
    MasteryProfile,
    MasteryStrategyCandidate,
    RevisionBrief,
    SkillProposal,
    ToolProposal,
    ToolChainContext,
    TrainSetEvalRecord,
    TrainSetEvalSummary,
    TrainingSetDigest,
    ValidationResult,
)
from tools.builtin_tools import execute_builtin_tool
from tools.dynamic_loader import _normalize_artifact_output, _normalize_run_args, _snapshot_artifacts

_RUN_STRUCTURED_EXPERIMENT_SPEC = importlib.util.spec_from_file_location(
    "run_structured_experiment_module",
    Path(__file__).resolve().parent / "scripts" / "run_structured_experiment.py",
)
assert _RUN_STRUCTURED_EXPERIMENT_SPEC is not None
assert _RUN_STRUCTURED_EXPERIMENT_SPEC.loader is not None
_RUN_STRUCTURED_EXPERIMENT_MODULE = importlib.util.module_from_spec(_RUN_STRUCTURED_EXPERIMENT_SPEC)
_RUN_STRUCTURED_EXPERIMENT_SPEC.loader.exec_module(_RUN_STRUCTURED_EXPERIMENT_MODULE)
_normalize_settings = _RUN_STRUCTURED_EXPERIMENT_MODULE._normalize_settings
_validate_dataset_assets = _RUN_STRUCTURED_EXPERIMENT_MODULE._validate_dataset_assets


class DummyClient:
    def chat(self, messages, settings=None):
        raise AssertionError("Unexpected VLM call in this test")


class JudgeClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def chat(self, messages, settings=None):
        self.calls += 1
        return self.response, DummyUsage()


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


class ScratchFakeAgent:
    def __init__(self, answer: str, artifact: str | None = None):
        self.answer = answer
        self.artifact = artifact

    def run(self, task: str, image_path: str = "", initial_observations=None) -> AgentResult:
        steps: list[AgentStep] = []
        artifacts: list[str] = []
        if self.artifact:
            artifacts.append(self.artifact)
            steps.append(
                AgentStep(
                    turn=1,
                    action=AgentAction(
                        name="bash",
                        arguments={"command": "python scratch_edit.py"},
                    ),
                    observation=f"STATUS: ok\nARTIFACTS: {self.artifact}",
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

    def _create_agent(self, case, attempt=None, phase="solve", required_skill_name=None, require_bash_action_before_complete=False, required_image_artifact_before_complete=False, include_learned_skills=True, **kwargs):
        learned = include_learned_skills and self.store.has_skill("chartqa")
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
        self.last_case_report = {
            "case_id": case.case_id,
            "problem_id": case.problem_id,
            "prompt": case.prompt,
            "gold_answer": case.gold_answer,
            "attempts": [
                {
                    "attempt": 1,
                    "initial_result": {"final_answer": "wrong"},
                    "analysis": {"next_action": "generate_skill"},
                    "skill_proposal": {"name": "chartqa", "content": "## SOP\n1. Focus on the right bar."},
                    "retry_result": {"final_answer": case.gold_answer},
                    "decision": "keep",
                }
            ],
            "solved": True,
            "attempts_used": 1,
            "final_result": {"final_answer": case.gold_answer},
        }
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


class ScratchFakeLoop(FakeLoop):
    def _create_agent(self, case, attempt=None, phase="solve", required_skill_name=None, require_bash_action_before_complete=False, required_image_artifact_before_complete=False, include_learned_skills=True, **kwargs):
        learned = include_learned_skills and self.store.has_skill("chartqa")
        if case.case_id == "1":
            return ScratchFakeAgent(case.gold_answer, artifact="artifacts/case1_edit.png")
        if case.case_id == "2":
            if learned:
                return ScratchFakeAgent(case.gold_answer, artifact="artifacts/case2_edit.png")
            return ScratchFakeAgent("wrong")
        return ScratchFakeAgent("wrong")


class MultipleChoiceRecoveryTests(unittest.TestCase):
    def test_infer_choices_from_prompt_extracts_option_lines(self):
        prompt = (
            "What is the color of the trash can?\n"
            "(A) black\n"
            "(B) silver\n"
            "(C) yellow\n"
            "(D) green\n"
            "Answer with the option's letter from the given choices directly."
        )
        self.assertEqual(
            infer_choices_from_prompt(prompt),
            {"A": "black", "B": "silver", "C": "yellow", "D": "green"},
        )

    def test_load_normalized_cases_backfills_missing_multiple_choice_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "vstar"
            dataset_root.mkdir(parents=True, exist_ok=True)
            image_path = root / "sample.png"
            image_path.write_bytes(b"fake")
            prompt = (
                "Is the switch on the left or right side of the towel?\n"
                "(A) left\n"
                "(B) right\n"
                "Answer with the option's letter from the given choices directly."
            )
            (dataset_root / "val.jsonl").write_text(
                json.dumps(
                    {
                        "id": "1",
                        "problem_id": "vstar",
                        "prompt": prompt,
                        "answer": "B",
                        "image_path": str(image_path),
                        "metadata": {"dataset_name": "vstar", "answer_type": "multiple_choice", "choices": {}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            [case] = load_normalized_cases(root, "vstar", "val")

        self.assertEqual(case.metadata["choices"], {"A": "left", "B": "right"})
        self.assertTrue(check_multiple_choice_answer("right", case.gold_answer, case.metadata["choices"]))

    def test_validate_dataset_assets_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dataset_root = root / "vstar"
            dataset_root.mkdir(parents=True, exist_ok=True)
            prompt = "What color?\n(A) red\n(B) blue"
            (dataset_root / "train.jsonl").write_text(
                json.dumps(
                    {
                        "id": "missing-1",
                        "problem_id": "vstar",
                        "prompt": prompt,
                        "answer": "A",
                        "image_path": str(root / "missing.png"),
                        "metadata": {"dataset_name": "vstar", "answer_type": "multiple_choice", "choices": {}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (dataset_root / "val.jsonl").write_text(
                (dataset_root / "train.jsonl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            config = StructuredExperimentConfig(
                dataset="vstar",
                raw_data_root=root,
                normalized_data_root=root,
                subset_id="tmp",
                evolve_split="train",
                held_out_split="val",
                settings=["direct_vlm"],
            )

            with self.assertRaises(SystemExit) as exc:
                _validate_dataset_assets(config)

        self.assertIn("Dataset asset validation failed", str(exc.exception))
        self.assertIn("missing-1", str(exc.exception))

    def run_single_case(self, case):
        self.run_single_case_calls.append(case.case_id)
        self.last_case_report = {
            "case_id": case.case_id,
            "problem_id": case.problem_id,
            "prompt": case.prompt,
            "gold_answer": case.gold_answer,
            "attempts": [
                {
                    "attempt": 1,
                    "initial_result": {"final_answer": "wrong"},
                    "analysis": {"next_action": "generate_code_skill"},
                    "skill_proposal": {"name": "chartqa", "content": "## SOP\n1. Write temporary editing code.\n2. Save an edited image.\n3. Answer from the edited image."},
                    "retry_result": {"final_answer": case.gold_answer},
                    "decision": "keep",
                }
            ],
            "solved": True,
            "attempts_used": 1,
            "final_result": {"final_answer": case.gold_answer},
        }
        self.store.promote_skill(
            "chartqa",
            SkillProposal(
                name="chartqa",
                description="Write temporary editing code before answering.",
                applicability_conditions="Use when only part of the chart is relevant.",
                content="## SOP\n1. Identify the target evidence.\n2. Write temporary Python code that edits the image and saves an artifact.\n3. Answer from the edited image.",
                level="mid",
                depends_on=[],
            ),
        )
        return True


class FakeSubsetLoop:
    def __init__(self, report: SubsetEvolutionRunReport):
        self.report = report
        self.run_calls: list[list[str]] = []

    def run(self, cases: list[TaskCase]) -> SubsetEvolutionRunReport:
        self.run_calls.append([case.case_id for case in cases])
        return self.report


class RecordingClient:
    def __init__(self, response: str):
        self.response = response
        self.messages = None

    def chat(self, messages, settings=None):
        self.messages = messages
        return self.response, DummyUsage()


class DummyUsage:
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0

    def __add__(self, other):
        return self


class LoopAnalyzerStub:
    total_usage = DummyUsage()

    def analyze_and_decide(self, **kwargs):
        self.last_kwargs = kwargs
        return FailureAnalysis(
            root_cause="Read the wrong year.",
            next_action="generate_skill",
            confidence=0.8,
            missing_step="Locate the exact year label before reading the value.",
            skill_update_note="Read the label first, then the bar value.",
            rationale="The value lookup is fine, but year alignment is off.",
            differentiation_note="Use year-label alignment instead of generic rereading.",
        )


class LoopGeneratorStub:
    total_usage = DummyUsage()

    def generate_coverage_contract(self, case, target_cluster_ids, training_context, representative_case_summaries, planner_action):
        return CoverageContract(
            target_family=case.capability_family(),
            target_cluster_ids=list(target_cluster_ids),
            problem_pattern="shared family pattern",
            supported_variations=["variation a", "variation b"],
            unsupported_variations=["variation outside scope"],
            forbidden_case_specific_assumptions=["no one-image thresholds"],
            primitive_category="chart_value_overlay",
            tool_validation_scope="family",
            recommended_action=planner_action,
            why_this_should_generalize="Cluster-level pattern repeats.",
        )

    def generate_skill(self, *args, **kwargs):
        return SkillProposal(
            name="chartqa",
            description="Use year alignment before reading the bar.",
            applicability_conditions="Use when neighboring years are easy to confuse.",
            content="## SOP\n1. Find the year label.\n2. Read only the aligned value.",
            level="mid",
            depends_on=[],
        )

    def revise_skill(self, skill, revision_brief, coverage_contract, training_context):
        return skill


class LoopValidatorStub:
    def build_chain_context(self, case: TaskCase, skill_content: str | None, attempt=None):
        return ToolChainContext(latest_input_image=case.image_path)

    def validate_skill(self, proposal, problem_id):
        return ValidationResult(passed=True)

    def is_untrusted_tool_code(self, code: str) -> bool:
        return False


class SequenceAgent:
    def __init__(self, answers: list[str]):
        self.answers = list(answers)

    def run(self, task: str, image_path: str = "", initial_observations=None) -> AgentResult:
        answer = self.answers.pop(0)
        return AgentResult(
            task=task,
            final_answer=answer,
            steps=[],
            total_turns=1,
            success=True,
            all_artifacts=[],
        )


class TestStructuredRunner(StructuredBenchmarkRunner):
    def __init__(self, config, project_root, online_loop: FakeLoop, frozen_loop: FakeLoop, subset_loop: FakeSubsetLoop | None = None):
        super().__init__(config=config, project_root=project_root, vlm_client=DummyClient())
        self._online_loop = online_loop
        self._frozen_loop = frozen_loop
        self._subset_loop = subset_loop

    def _direct_answer(self, case: TaskCase) -> str:
        return "direct"

    def _create_plain_react_agent(self, case: TaskCase, phase: str):
        return FakeAgent(case.gold_answer if case.case_id == "1" else "wrong")

    def _make_online_loop(self, capability_mode="persistent_tools"):
        return self._online_loop

    def _make_subset_loop(self, cases=None, capability_mode="persistent_tools"):
        if self._subset_loop is None:
            return super()._make_subset_loop(cases, capability_mode=capability_mode)
        return self._subset_loop

    def _make_frozen_loop(self, snapshot_name: str | None = None, subset_id: str | None = None, capability_mode="persistent_tools"):
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

    def _write_json_rows(self, path: Path, rows: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows), encoding="utf-8")

    def _image_base64(self, size=(12, 8)) -> str:
        buffer = BytesIO()
        Image.new("RGB", size, color=(255, 255, 255)).save(buffer, format="PNG")
        return __import__("base64").b64encode(buffer.getvalue()).decode("utf-8")

    def _make_subset_report(self, rows: list[dict], baseline_correct_case_ids: set[str], final_correct_case_ids: set[str]) -> SubsetEvolutionRunReport:
        baseline_records: list[TrainSetEvalRecord] = []
        final_records: list[TrainSetEvalRecord] = []
        for row in rows:
            metadata = dict(row.get("metadata") or {})
            baseline_records.append(
                TrainSetEvalRecord(
                    case_id=row["id"],
                    dataset_name=metadata.get("dataset_name", "chartqa"),
                    capability_family=metadata.get("capability_family", "chartqa"),
                    prompt=row["prompt"],
                    expected=row["answer"],
                    answer=row["answer"] if row["id"] in baseline_correct_case_ids else "wrong",
                    correct=row["id"] in baseline_correct_case_ids,
                    turns=1,
                    tool_names=["focus_chart"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                    artifact_paths=["artifacts/focus.png"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                    chain_trace=["focus_chart"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                )
            )
            final_records.append(
                TrainSetEvalRecord(
                    case_id=row["id"],
                    dataset_name=metadata.get("dataset_name", "chartqa"),
                    capability_family=metadata.get("capability_family", "chartqa"),
                    prompt=row["prompt"],
                    expected=row["answer"],
                    answer=row["answer"] if row["id"] in final_correct_case_ids else "wrong",
                    correct=row["id"] in final_correct_case_ids,
                    turns=1,
                    tool_names=["focus_chart"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                    artifact_paths=["artifacts/focus.png"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                    chain_trace=["focus_chart"] if row["id"] in final_correct_case_ids and row["id"] not in baseline_correct_case_ids else [],
                )
            )
        baseline_summary = TrainSetEvalSummary(
            total_cases=len(baseline_records),
            correct_cases=sum(1 for row in baseline_records if row.correct),
            primary_score=sum(1 for row in baseline_records if row.correct) / len(baseline_records),
            per_dataset_scores={"chartqa": sum(1 for row in baseline_records if row.correct) / len(baseline_records)},
            per_family_scores={"chartqa": sum(1 for row in baseline_records if row.correct) / len(baseline_records)},
        )
        final_summary = TrainSetEvalSummary(
            total_cases=len(final_records),
            correct_cases=sum(1 for row in final_records if row.correct),
            primary_score=sum(1 for row in final_records if row.correct) / len(final_records),
            per_dataset_scores={"chartqa": sum(1 for row in final_records if row.correct) / len(final_records)},
            per_family_scores={"chartqa": sum(1 for row in final_records if row.correct) / len(final_records)},
        )
        return SubsetEvolutionRunReport(
            baseline_summary=baseline_summary,
            final_summary=final_summary,
            baseline_records=baseline_records,
            final_records=final_records,
            round_results=[
                CandidateEvalResult(
                    run_id="round_1",
                    accepted=True,
                    reason="Accepted candidate with score delta 0.3333",
                    baseline_score=baseline_summary.primary_score,
                    candidate_score=final_summary.primary_score,
                    score_delta=final_summary.primary_score - baseline_summary.primary_score,
                    smoke_passed=True,
                    target_family="chartqa",
                    target_cluster_ids=["cluster_1"],
                    representative_case_ids=["2"],
                    activated_snapshot="chartqa_refocus_v1_round_1_accepted",
                    baseline_summary=baseline_summary,
                    candidate_summary=final_summary,
                )
            ],
            snapshot_name="chartqa_refocus_v1_train_snapshot",
        )

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

    def test_chartqa_normalization_finds_images_in_nested_official_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_root = root / "ChartQA Dataset"
            normalized_root = root / "normalized"
            image_path = raw_root / "train" / "png" / "two_col_103562.png"
            self._write_image(image_path, size=(19, 13))
            (raw_root / "train" / "train_augmented.json").parent.mkdir(parents=True, exist_ok=True)
            (raw_root / "train" / "train_augmented.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "sample_nested",
                            "question": "Which bar is highest?",
                            "answer": "B",
                            "imgname": "two_col_103562.png",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            manifest = normalize_chartqa_dataset(raw_root, normalized_root, splits=["train"])
            cases = load_normalized_cases(normalized_root, "chartqa", "train")

            self.assertEqual(manifest["splits"]["train"]["count"], 1)
            self.assertEqual(len(cases), 1)
            self.assertTrue(cases[0].image_path.endswith("two_col_103562.png"))
            self.assertEqual(cases[0].metadata["image_width"], 19)
            self.assertEqual(cases[0].metadata["image_height"], 13)

    def test_multibench_normalizers_create_expected_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normalized_root = root / "normalized"

            image_root = root / "images"
            self._write_image(image_root / "v1.png")
            self._write_image(image_root / "mv1.png")
            self._write_image(image_root / "tv1.png")
            self._write_image(image_root / "tv2.png")

            self._write_json_rows(
                root / "vstar" / "test.json",
                [
                    {
                        "id": "v1",
                        "question": "Which option is correct?",
                        "answer": "B",
                        "choices": ["one", "two", "three", "four"],
                        "category": "logic",
                        "image_path": str(image_root / "v1.png"),
                    },
                    {
                        "id": "v2",
                        "question": "Which option is correct?",
                        "answer": "A",
                        "choices": ["alpha", "beta", "gamma", "delta"],
                        "category": "logic",
                        "image_path": str(image_root / "v1.png"),
                    },
                ],
            )

            self._write_json_rows(
                root / "hrbench" / "hrbench_4k.json",
                [
                    {
                        "id": "h1",
                        "question": "Pick the best answer.",
                        "answer": "B",
                        "options": {"A": "red", "B": "blue", "C": "green", "D": "yellow"},
                        "category": "doc",
                        "cycle_category": "chart",
                        "image": self._image_base64(),
                    },
                    {
                        "id": "h2",
                        "question": "Pick the best answer.",
                        "answer": "A",
                        "options": {"A": "north", "B": "south", "C": "east", "D": "west"},
                        "category": "doc",
                        "cycle_category": "chart",
                        "image": self._image_base64(),
                    },
                ],
            )

            self._write_json_rows(
                root / "mathvista" / "testmini.json",
                [
                    {
                        "id": "m1",
                        "question": "Which option matches the figure?",
                        "answer": "C",
                        "choices": ["1", "2", "3", "4"],
                        "source": "geometry",
                        "question_type": "multi_choice",
                        "answer_type": "multi_choice",
                        "precision": 0,
                        "unit": "",
                        "image_path": str(image_root / "mv1.png"),
                    },
                    {
                        "id": "m2",
                        "question": "What is the value?",
                        "answer": "3.14",
                        "source": "algebra",
                        "question_type": "free_form",
                        "answer_type": "float",
                        "precision": 2,
                        "unit": "",
                        "image_path": str(image_root / "mv1.png"),
                    },
                ],
            )

            self._write_json_rows(
                root / "textvqa" / "train.json",
                [
                    {
                        "id": "t1",
                        "question": "What word is shown?",
                        "answers": ["openai", "openai", "open ai"],
                        "ocr_tokens": ["OPENAI"],
                        "image_path": str(image_root / "tv1.png"),
                    }
                ],
            )
            self._write_json_rows(
                root / "textvqa" / "validation.json",
                [
                    {
                        "id": "t2",
                        "question": "What number is shown?",
                        "answers": ["42", "42", "42", "forty two"],
                        "ocr_tokens": ["42"],
                        "image_path": str(image_root / "tv2.png"),
                    }
                ],
            )

            normalize_vstar_dataset(root / "vstar", normalized_root, train_size=1, val_size=1)
            normalize_hrbench_dataset(root / "hrbench", normalized_root, train_size=1, val_size=1)
            normalize_mathvista_dataset(root / "mathvista", normalized_root, train_size=1, val_size=1)
            normalize_textvqa_dataset(root / "textvqa", normalized_root)

            vstar_cases = load_normalized_cases(normalized_root, "vstar", "train")
            hrbench_cases = load_normalized_cases(normalized_root, "hrbench", "train")
            mathvista_cases = load_normalized_cases(normalized_root, "mathvista", "train")
            textvqa_cases = load_normalized_cases(normalized_root, "textvqa", "train")

            self.assertEqual(vstar_cases[0].metadata["capability_family"], "vstar_logic")
            self.assertEqual(hrbench_cases[0].metadata["capability_family"], "hrbench_doc")
            self.assertTrue(Path(hrbench_cases[0].image_path).exists())
            self.assertIn("choices", mathvista_cases[0].metadata)
            self.assertIn("answers", textvqa_cases[0].metadata)
            self.assertEqual(textvqa_cases[0].metadata["capability_family"], "textvqa_ocr")

    def test_hrbench_normalizer_supports_letter_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normalized_root = root / "normalized"
            self._write_image(root / "images" / "h1.png")

            self._write_json_rows(
                root / "hrbench" / "hrbench_4k.json",
                [
                    {
                        "id": "h1",
                        "question": "Pick the best answer.",
                        "A": "left",
                        "B": "right",
                        "C": "up",
                        "D": "down",
                        "answer": "B",
                        "category": "doc",
                        "cycle_category": "chart",
                        "image_path": str(root / "images" / "h1.png"),
                    },
                    {
                        "id": "h2",
                        "question": "Pick the best answer.",
                        "A": "red",
                        "B": "blue",
                        "C": "green",
                        "D": "yellow",
                        "answer": "A",
                        "category": "doc",
                        "cycle_category": "chart",
                        "image_path": str(root / "images" / "h1.png"),
                    },
                ],
            )

            normalize_hrbench_dataset(root / "hrbench", normalized_root, train_size=1, val_size=1)
            train_cases = load_normalized_cases(normalized_root, "hrbench", "train")

            self.assertEqual(train_cases[0].gold_answer, "B")
            self.assertEqual(
                train_cases[0].metadata["choices"],
                {"A": "left", "B": "right", "C": "up", "D": "down"},
            )

    def test_hrbench_normalizer_reuses_cached_asset_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normalized_root = root / "normalized"
            row = {
                "id": "h1",
                "question": "Pick the best answer.",
                "options": {"A": "red", "B": "blue", "C": "green", "D": "yellow"},
                "answer": "B",
                "category": "doc",
                "cycle_category": "chart",
                "image": self._image_base64(),
            }
            self._write_json_rows(root / "hrbench" / "hrbench_4k.json", [row, dict(row, id="h2", answer="A")])

            normalize_hrbench_dataset(root / "hrbench", normalized_root, train_size=1, val_size=1)
            asset_path = normalized_root / "_assets" / "hrbench" / "train_val" / "h1.png"
            first_mtime = asset_path.stat().st_mtime

            normalize_hrbench_dataset(root / "hrbench", normalized_root, train_size=1, val_size=1)
            second_mtime = asset_path.stat().st_mtime

            self.assertEqual(first_mtime, second_mtime)

    def test_new_benchmark_answer_checkers_cover_multiple_choice_mathvista_and_textvqa(self):
        hr_case = TaskCase(
            case_id="h1",
            problem_id="hrbench",
            prompt="Pick the best answer.",
            gold_answer="B",
            metadata={"choices": {"A": "red", "B": "blue", "C": "green", "D": "yellow"}},
        )
        self.assertTrue(HRBenchAdapter().check_answer("blue", hr_case))
        self.assertTrue(check_multiple_choice_answer("option B", "B", hr_case.metadata["choices"]))

        mv_choice_case = TaskCase(
            case_id="m1",
            problem_id="mathvista",
            prompt="Which option is correct?",
            gold_answer="C",
            metadata={"choices": {"A": "1", "B": "2", "C": "3", "D": "4"}, "answer_type": "multi_choice", "precision": 0, "unit": ""},
        )
        self.assertTrue(MathVistaAdapter().check_answer("3", mv_choice_case))

        mv_numeric_case = TaskCase(
            case_id="m2",
            problem_id="mathvista",
            prompt="What is the value?",
            gold_answer="3.14",
            metadata={"answer_type": "float", "precision": 2, "unit": ""},
        )
        self.assertTrue(check_mathvista_answer("The answer is 3.141", "3.14", prompt="What is the value?", precision=2))
        self.assertTrue(MathVistaAdapter().check_answer("3.141", mv_numeric_case))

        text_case = TaskCase(
            case_id="t1",
            problem_id="textvqa",
            prompt="What word is shown?",
            gold_answer="openai",
            metadata={"answers": ["openai", "openai", "open ai", "openai"]},
        )
        self.assertAlmostEqual(score_textvqa_answer("openai", text_case.metadata["answers"]), 1.0)
        self.assertGreaterEqual(TextVQAAdapter().score_answer("open ai", text_case), 1 / 3)

    def test_mathvista_adapter_uses_llm_judge_for_freeform_fallback(self):
        client = JudgeClient("CORRECT")
        adapter = MathVistaAdapter(client=client)
        case = TaskCase(
            case_id="m3",
            problem_id="mathvista",
            prompt="What fraction of the shape is shaded?",
            gold_answer="one half",
            metadata={
                "dataset_name": "mathvista",
                "capability_family": "mathvista_geometry_free_form",
                "answer_type": "text",
                "question_type": "free_form",
                "choices": {},
                "precision": None,
                "unit": "",
            },
        )

        self.assertEqual(adapter.score_answer("The shaded region is 1/2.", case), 1.0)
        self.assertTrue(adapter.check_answer("The shaded region is 1/2.", case))
        self.assertEqual(client.calls, 1)

    def test_mathvista_adapter_does_not_use_llm_judge_for_multiple_choice(self):
        client = JudgeClient("CORRECT")
        adapter = MathVistaAdapter(client=client)
        case = TaskCase(
            case_id="m4",
            problem_id="mathvista",
            prompt="Which option is correct?",
            gold_answer="C",
            metadata={
                "dataset_name": "mathvista",
                "capability_family": "mathvista_geometry_multi_choice",
                "answer_type": "multi_choice",
                "question_type": "multi_choice",
                "choices": {"A": "1", "B": "2", "C": "3", "D": "4"},
                "precision": 0,
                "unit": "",
            },
        )

        self.assertEqual(adapter.score_answer("3", case), 1.0)
        self.assertTrue(adapter.check_answer("3", case))
        self.assertEqual(client.calls, 0)

    def test_available_benchmark_datasets_includes_new_datasets(self):
        datasets = available_benchmark_datasets()
        self.assertIn("gta", datasets)
        self.assertIn("mathvista", datasets)
        self.assertIn("textvqa", datasets)
        self.assertIn("vstar", datasets)

    def test_gta_adapter_respects_whitelist_blacklist_and_numeric_tolerance(self):
        adapter = GTAAdapter()
        case = TaskCase(
            case_id="g1",
            problem_id="gta_perception",
            prompt="How much should I pay?",
            gold_answer="12",
            metadata={
                "dataset_name": "gta",
                "capability_family": "gta_perception",
                "tool_category": "perception",
                "num_steps": 4,
                "gt_tools": ["OCR", "Calculator"],
                "gt_answer_whitelist": [["12"]],
                "gt_answer_blacklist": [["13"]],
            },
        )

        self.assertEqual(adapter.score_answer("You should pay 12.0 dollars.", case), 1.0)
        self.assertEqual(adapter.score_answer("You should pay 13 dollars.", case), 0.0)
        result = AgentResult(task="", final_answer="", steps=[], total_turns=0, success=True)
        self.assertEqual(adapter.cluster_key(case, result, False), "gta::perception::long")

    def test_normalize_gta_dataset_writes_current_machine_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_root = root / "raw_gta"
            (raw_root / "image").mkdir(parents=True, exist_ok=True)
            self._write_image(raw_root / "image" / "image_1.jpg")

            dataset = {
                "0": {
                    "dialogs": [
                        {"role": "user", "content": "What number is on the sign?"},
                        {
                            "role": "assistant",
                            "thought": "Use OCR.",
                            "tool_calls": [{"function": {"name": "OCR", "arguments": {"image": "image/image_1.jpg"}}}],
                        },
                    ],
                    "files": [{"path": "image/image_1.jpg"}],
                    "gt_answer": {"whitelist": [["42"]], "blacklist": [["24"]]},
                    "tools": [{"name": "OCR"}],
                }
            }
            toolmeta = {
                "OCR": {
                    "name": "OCR",
                    "description": "Read text from an image.",
                    "inputs": [{"name": "image", "type": "image"}],
                    "outputs": [{"type": "text"}],
                }
            }
            (raw_root / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
            (raw_root / "toolmeta.json").write_text(json.dumps(toolmeta), encoding="utf-8")

            manifest = normalize_gta_dataset(raw_root, root / "normalized", train_ratio=1.0, seed=7)
            cases = load_normalized_cases(root / "normalized", "gta", "train")

            self.assertEqual(manifest["total_cases"], 1)
            self.assertEqual(cases[0].image_path, str((raw_root / "image" / "image_1.jpg").resolve()))
            self.assertEqual(cases[0].metadata["tool_category"], "perception")
            self.assertEqual(cases[0].metadata["gt_answer_whitelist"], [["42"]])

    def test_subset_level_train_adaptive_uses_final_active_snapshot(self):
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
            subset_loop = FakeSubsetLoop(
                self._make_subset_report(rows, baseline_correct_case_ids={"1"}, final_correct_case_ids={"1", "2", "3"})
            )
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop, subset_loop=subset_loop)

            cases = load_normalized_cases(config.normalized_data_root, "chartqa", "train", limit=3)
            records, snapshot_name = runner._run_online_evolve(cases)

            self.assertEqual(snapshot_name, "chartqa_refocus_v1_train_snapshot")
            self.assertEqual(subset_loop.run_calls, [["1", "2", "3"]])
            self.assertFalse(records[0].evolve_triggered)
            self.assertTrue(records[1].evolve_triggered)
            self.assertTrue(records[2].evolve_triggered)
            self.assertTrue(records[2].correct)
            saved_reports = json.loads(runner.evolve_reports_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved_reports), 1)
            self.assertEqual(saved_reports[0]["case_id"], "2")
            self.assertEqual(saved_reports[0]["attempts"][0]["decision"], "keep")
            self.assertEqual(records[0].full_agent_answer, "A")
            self.assertTrue(records[0].full_agent_correct)
            self.assertEqual(records[1].post_evolve_answer, "B")
            self.assertTrue(records[1].post_evolve_correct)

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
                setting="agent_train_adaptive",
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
                full_agent_answer="A",
                full_agent_correct=True,
                post_evolve_answer="A",
                post_evolve_correct=True,
            ),
            StructuredCaseRecord(
                setting="agent_train_adaptive",
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
                full_agent_answer="wrong",
                full_agent_correct=False,
                post_evolve_answer="wrong",
                post_evolve_correct=False,
            ),
        ]

        summary = _aggregate_records(rows)["agent_train_adaptive"]

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["correct"], 1)
        self.assertAlmostEqual(summary["accuracy"], 0.5)
        self.assertAlmostEqual(summary["tool_usage_rate"], 0.5)
        self.assertAlmostEqual(summary["avg_tool_calls_per_case"], 0.5)
        self.assertAlmostEqual(summary["artifact_production_rate"], 0.5)
        self.assertAlmostEqual(summary["full_agent_accuracy"], 0.5)
        self.assertAlmostEqual(summary["post_evolve_recovery_accuracy"], 0.5)
        self.assertEqual(summary["readability_summary"]["judged_cases"], 1)
        self.assertAlmostEqual(summary["readability_summary"]["readability_improved_rate"], 1.0)
        self.assertEqual(summary["readability_summary"]["manual_spotcheck_case_ids"], ["1"])

    def test_frozen_inference_forced_skill_marks_enforcement(self):
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
                    content="## SOP\n1. Run a bash step before answering.",
                    level="mid",
                    depends_on=[],
                ),
            )
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            records = runner.run_frozen_inference(subset_id=config.subset_id, force_skill=True)

            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].forced_skill_enforced)
            self.assertEqual(records[0].forced_skill_name, "chartqa")

    def test_scratch_skill_train_adaptive_promotes_skill_without_writing_new_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            self._write_image(chart_dir / "2.png")
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
            ]
            self._write_normalized_chartqa(root / "normalized", "train", rows)

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_scratch_v1",
                k=2,
            )
            online_loop = ScratchFakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            cases = load_normalized_cases(config.normalized_data_root, "chartqa", "train", limit=2)
            records, snapshot_name = runner._run_scratch_skill_train_adaptive(cases)

            self.assertEqual(snapshot_name, "chartqa_scratch_v1_train_k2_snapshot")
            self.assertEqual(online_loop.run_single_case_calls, ["2"])
            self.assertTrue(records[0].scratch_code_triggered)
            self.assertTrue(records[0].scratch_code_success)
            self.assertTrue(records[0].code_writing_skill_used)
            self.assertEqual(records[0].scratch_script_summary, "python scratch_edit.py")
            tools_dir = root / "learned" / config.subset_id / "tools"
            self.assertEqual(list(tools_dir.glob("*.py")), [])
            self.assertEqual(list(tools_dir.glob("*.json")), [])

    def test_chartqa_answer_checker_handles_numeric_and_string_matches(self):
        self.assertTrue(check_chartqa_answer("4", "4"))
        self.assertTrue(check_chartqa_answer("The answer is 4", "4"))
        self.assertTrue(check_chartqa_answer("4.0", "4"))
        self.assertFalse(check_chartqa_answer("5", "4"))
        self.assertTrue(
            check_chartqa_answer(
                "The Mexican government spent 6.61 billion dollars on the military in the year 2020.",
                "2020",
                prompt="In what year did the Mexican government spend 6.61 billion dollars in the military?",
            )
        )
        self.assertTrue(
            check_chartqa_answer(
                "The Mexican government spent 6.61 billion dollars on the military in the year 2020.",
                "6.61",
                prompt="How much did the Mexican government spend in the military a year earlier?",
            )
        )
        self.assertTrue(
            check_chartqa_answer(
                "The U.S. exports of goods and services made up 9.23 percent of its GDP in the year 1990.",
                "1990",
                prompt="In what year did the U.S. exports of goods and services make up 9.23 percent of its GDP?",
            )
        )
        self.assertTrue(
            check_chartqa_answer(
                "In 1990, exports accounted for 9.23% of the GDP of the United States.",
                "9.23",
                prompt="What percentage of the GDP of the United States was exported in 1990?",
            )
        )

    def test_failed_direction_store_persists_and_dedupes_similar_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CapabilityStore(Path(tmp) / "learned")
            first = FailedDirection(
                case_id="case_1",
                attempt=1,
                created_at="2026-03-18T10:00:00",
                root_cause="Read the wrong year.",
                missing_step="Locate the exact year label before reading the value.",
                next_action="generate_skill",
                skill_update_note="Read the year label first and only then the bar value.",
                failure_reason="Retry still picked the neighboring year.",
                source="retry_failed",
            )
            second = FailedDirection(
                case_id="case_2",
                attempt=2,
                created_at="2026-03-18T10:05:00",
                root_cause="Still using the neighboring year.",
                missing_step="Locate the exact year label before reading the bar value.",
                next_action="generate_skill",
                skill_update_note="Align to the year label before reading the value.",
                failure_reason="Retry still picked the neighboring year.",
                source="retry_failed",
            )

            first_save = store.save_failed_direction("chartqa", first)
            second_save = store.save_failed_direction("chartqa", second)
            loaded = store.list_failed_directions("chartqa", limit=5)

            self.assertFalse(first_save["deduped"])
            self.assertTrue(second_save["deduped"])
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].times_failed, 2)
            self.assertEqual(loaded[0].last_case_id, "case_2")

    def test_analyzer_prompt_includes_recent_failed_directions(self):
        client = RecordingClient(
            json.dumps(
                {
                    "root_cause": "Used a repeated direction.",
                    "missing_step": "Try a different chart grounding step.",
                    "next_action": "generate_tool",
                    "tool_goal": "Highlight the target year column.",
                    "skill_update_note": "",
                    "differentiation_note": "Switching from strategy advice to visual grounding.",
                    "confidence": 0.7,
                    "rationale": "A visual tool is more distinct than another SOP rewrite.",
                }
            )
        )
        analyzer = AnalyzerDecider(client)
        case = TaskCase(case_id="1", problem_id="chartqa", prompt="Q", gold_answer="A")
        result = AgentResult(task="Q", final_answer="wrong", steps=[], total_turns=1, success=True)
        failed_direction = FailedDirection(
            case_id="old_case",
            attempt=1,
            created_at="2026-03-18T09:00:00",
            root_cause="Read the wrong year.",
            missing_step="Locate the exact year label before reading the value.",
            next_action="generate_skill",
            skill_update_note="Read the label first, then the bar value.",
            failure_reason="Retry still failed.",
            source="retry_failed",
        )

        analysis = analyzer.analyze_and_decide(
            case=case,
            result=result,
            current_capabilities=["- none"],
            failed_directions=[failed_direction],
        )

        prompt_text = client.messages[1]["content"]
        self.assertIn("Previously tried and failed directions for this task family", prompt_text)
        self.assertIn("old_case", prompt_text)
        self.assertEqual(analysis.differentiation_note, "Switching from strategy advice to visual grounding.")

    def test_subset_planner_prompt_uses_digest_not_full_training_set(self):
        client = RecordingClient(
            json.dumps(
                {
                    "target_family": "chartqa",
                    "target_cluster_ids": ["cluster_1"],
                    "representative_case_ids": ["case_2"],
                    "next_action": "generate_skill",
                    "tool_goal": "",
                    "skill_update_note": "Tighten the chart SOP.",
                    "rationale": "Largest remaining cluster.",
                    "expected_gain": "Improve train accuracy.",
                }
            )
        )
        planner = SubsetPlanner(client, LoopGeneratorStub(), Path("/tmp/skills"))
        digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
            baseline_summary=TrainSetEvalSummary(
                total_cases=3,
                correct_cases=1,
                primary_score=1 / 3,
                per_dataset_scores={"chartqa": 1 / 3},
                per_family_scores={"chartqa": 1 / 3},
            ),
            failure_clusters=[
                __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                    cluster_id="cluster_1",
                    dataset_name="chartqa",
                    capability_family="chartqa",
                    cluster_key="chartqa::generic",
                    total_cases=2,
                    representative_case_ids=["case_2"],
                    summary_lines=["case_id=case_2; prompt=Read the right bar; expected=5; answer=wrong"],
                )
            ],
            representative_cases=[{"case_id": "case_2", "dataset_name": "chartqa", "capability_family": "chartqa", "prompt": "Read the right bar"}],
            recent_rejected_plans=[{"run_id": "old", "reason": "tie"}],
        )

        planner.plan_bundle(digest)

        prompt_text = client.messages[1]["content"]
        self.assertIn("Failure clusters:", prompt_text)
        self.assertIn("case_id=case_2", prompt_text)
        self.assertNotIn("This prompt should never appear in planner input", prompt_text)

    def test_subset_planner_prompt_includes_tool_preference_guidance(self):
        client = RecordingClient(
            json.dumps(
                {
                    "target_family": "chartqa",
                    "target_cluster_ids": ["cluster_1"],
                    "representative_case_ids": ["case_2"],
                    "next_action": "generate_tool",
                    "tool_goal": "Crop around the relevant bar.",
                    "skill_update_note": "",
                    "rationale": "A reusable visual tool should help multiple failures.",
                    "expected_gain": "Improve train accuracy.",
                }
            )
        )
        planner = SubsetPlanner(client, LoopGeneratorStub(), Path("/tmp/skills"), tool_preference="prefer_tools")
        digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
            baseline_summary=TrainSetEvalSummary(
                total_cases=3,
                correct_cases=1,
                primary_score=1 / 3,
                per_dataset_scores={"chartqa": 1 / 3},
                per_family_scores={"chartqa": 1 / 3},
            ),
            failure_clusters=[
                __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                    cluster_id="cluster_1",
                    dataset_name="chartqa",
                    capability_family="chartqa",
                    cluster_key="chartqa::generic",
                    total_cases=2,
                    representative_case_ids=["case_2"],
                    summary_lines=["case_id=case_2; prompt=Read the right bar; expected=5; answer=wrong"],
                )
            ],
            representative_cases=[{"case_id": "case_2", "dataset_name": "chartqa", "capability_family": "chartqa", "prompt": "Read the right bar"}],
            recent_rejected_plans=[],
        )

        planner.plan_bundle(digest)

        prompt_text = client.messages[1]["content"]
        self.assertIn("Tool generation preference: prefer_tools", prompt_text)
        self.assertIn("prefer `generate_both` or `generate_tool`", prompt_text)

    def test_subset_planner_materialize_bundle_attaches_coverage_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planner = SubsetPlanner(DummyClient(), LoopGeneratorStub(), root / "skills")
            case = TaskCase(
                case_id="seed",
                problem_id="chartqa",
                prompt="Read the right bar",
                gold_answer="5",
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            )
            digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
                baseline_summary=TrainSetEvalSummary(
                    total_cases=1,
                    correct_cases=0,
                    primary_score=0.0,
                    per_dataset_scores={"chartqa": 0.0},
                    per_family_scores={"chartqa": 0.0},
                ),
                failure_clusters=[
                    __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                        cluster_id="cluster_1",
                        dataset_name="chartqa",
                        capability_family="chartqa",
                        cluster_key="chartqa::generic",
                        total_cases=1,
                        case_ids=["seed"],
                        representative_case_ids=["seed"],
                        summary_lines=["case_id=seed; prompt=Read the right bar"],
                    )
                ],
                representative_cases=[{"case_id": "seed", "dataset_name": "chartqa", "capability_family": "chartqa", "prompt": "Read the right bar"}],
                recent_rejected_plans=[],
            )

            bundle = planner.materialize_bundle(
                {
                    "target_family": "chartqa",
                    "target_cluster_ids": ["cluster_1"],
                    "representative_case_ids": ["seed"],
                    "next_action": "generate_skill",
                    "skill_update_note": "Improve chart SOP",
                    "rationale": "Cluster-level fix",
                    "expected_gain": "Improve train score",
                },
                digest,
                {"seed": case},
                root / "learned" / "active",
                root / "artifacts",
            )

            self.assertIsNotNone(bundle.coverage_contract)
            self.assertEqual(bundle.coverage_contract.problem_pattern, "shared family pattern")
            self.assertEqual(bundle.tools, [])
            self.assertEqual(len(bundle.skills), 1)

    def test_subset_loop_selects_up_to_three_cluster_smoke_cases(self):
        subset_loop = SubsetEvolutionLoop(
            subset_id="chartqa_refocus_smoke",
            learned_root=Path("/tmp/learned"),
            skills_dir=Path("/tmp/skills"),
            work_dir=Path("/tmp/artifacts"),
            vlm_client=DummyClient(),
            adapters={"chartqa": ChartQAAdapter()},
            max_planning_rounds=1,
        )
        bundle = CapabilityBundleProposal(
            run_id="round",
            target_family="chartqa",
            target_cluster_ids=["cluster_1"],
            representative_case_ids=["1", "2"],
        )
        digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
            baseline_summary=TrainSetEvalSummary(total_cases=3, correct_cases=0, primary_score=0.0),
            failure_clusters=[
                __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                    cluster_id="cluster_1",
                    dataset_name="chartqa",
                    capability_family="chartqa",
                    cluster_key="chartqa::generic",
                    total_cases=4,
                    case_ids=["1", "2", "3", "4"],
                    representative_case_ids=["1", "2"],
                    summary_lines=[],
                )
            ],
        )

        self.assertEqual(subset_loop._select_cluster_smoke_case_ids(bundle, digest), ["1", "2", "3"])

    def test_subset_loop_rejects_cluster_only_tool_after_family_smoke(self):
        subset_loop = SubsetEvolutionLoop(
            subset_id="chartqa_refocus_smoke",
            learned_root=Path("/tmp/learned"),
            skills_dir=Path("/tmp/skills"),
            work_dir=Path("/tmp/artifacts"),
            vlm_client=DummyClient(),
            adapters={"chartqa": ChartQAAdapter()},
            max_planning_rounds=1,
        )

        class ValidatorStub:
            def validate_tool(self, tool, origin_case, agent_factory, regression_cases=None, chain_context=None, attempt=None):
                return ValidationResult(passed=True, static_ok=True, origin_ok=True, regression_ok=True)

            def _run_tool_command(self, tool_name, image_path, project_root, problem_id, case_id, attempt, phase):
                if phase.startswith("family_smoke"):
                    return "STATUS: error\nANSWER:\n", 1
                return "STATUS: ok\nARTIFACTS: artifacts/out.png", 0

            def _extract_artifacts(self, output):
                return ["artifacts/out.png"] if "ARTIFACTS:" in output and "STATUS: error" not in output else []

            def _failure_result(self, base_result, reason, failure_type, evidence, rewrite_requirements, banned_patterns, retry_action):
                return ValidationResult(
                    passed=False,
                    reason=reason,
                    failure_type=failure_type,
                    revision_brief=RevisionBrief(
                        failure_type=failure_type,
                        reason=reason,
                        evidence=evidence,
                        rewrite_requirements=rewrite_requirements,
                        banned_patterns=banned_patterns,
                        retry_action=retry_action,
                    ),
                )

        tool = ToolProposal(
            name="chart_reader",
            description="desc",
            applicability_conditions="Use for chart reading.",
            code="",
            usage_example="python -m tools chart_reader <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=["artifacts/out.png"],
            primitive_category="chart_value_overlay",
        )
        cluster_case = TaskCase(case_id="1", problem_id="chartqa", prompt="Q1", gold_answer="1", image_path="/tmp/a.png", metadata={"dataset_name": "chartqa", "capability_family": "chartqa"})
        family_case = TaskCase(case_id="4", problem_id="chartqa", prompt="Q4", gold_answer="4", image_path="/tmp/b.png", metadata={"dataset_name": "chartqa", "capability_family": "chartqa"})
        result = subset_loop._validate_tool_across_cases(ValidatorStub(), object(), tool, [cluster_case], [family_case])

        self.assertFalse(result.passed)
        self.assertEqual(result.failure_type, "cluster_only_tool")

    def test_subset_planner_can_bias_next_action_toward_tools(self):
        planner = SubsetPlanner(DummyClient(), LoopGeneratorStub(), Path("/tmp/skills"), tool_preference="prefer_tools")
        proposal = planner._apply_tool_preference({"next_action": "generate_skill"})
        self.assertEqual(proposal["next_action"], "generate_both")

        blocked = planner._apply_tool_preference(
            {
                "next_action": "generate_skill",
                "primitive_category": "localized_text_zoom",
                "toolability_blocked": True,
            }
        )
        self.assertEqual(blocked["next_action"], "generate_skill")

        require_tool_planner = SubsetPlanner(DummyClient(), LoopGeneratorStub(), Path("/tmp/skills"), tool_preference="require_tools")
        proposal = require_tool_planner._apply_tool_preference({"next_action": "generate_skill"})
        self.assertEqual(proposal["next_action"], "generate_tool")

    def test_subset_planner_switches_to_skill_after_repeated_case_specific_rejections(self):
        planner = SubsetPlanner(DummyClient(), LoopGeneratorStub(), Path("/tmp/skills"), tool_preference="prefer_tools")
        digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
            baseline_summary=TrainSetEvalSummary(total_cases=1, correct_cases=0, primary_score=0.0),
            recent_rejected_plans=[
                {
                    "target_family": "chartqa",
                    "failure_type": "case_specific_logic",
                    "coverage_contract": {"primitive_category": "chart_value_overlay"},
                },
                {
                    "target_family": "chartqa",
                    "failure_type": "case_specific_logic",
                    "coverage_contract": {"primitive_category": "chart_value_overlay"},
                },
            ],
        )
        adjusted = planner._apply_rejection_strategy(
            {
                "target_family": "chartqa",
                "next_action": "generate_tool",
                "primitive_category": "chart_value_overlay",
            },
            digest,
        )
        self.assertEqual(adjusted["next_action"], "generate_skill")
        self.assertTrue(adjusted["toolability_blocked"])

    def test_subset_planner_materialize_bundle_normalizes_representative_case_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planner = SubsetPlanner(DummyClient(), LoopGeneratorStub(), root / "skills")
            cases_by_id = {
                "11": TaskCase(
                    case_id="11",
                    problem_id="mathvista",
                    prompt="What is the value?",
                    gold_answer="2",
                    image_path="",
                    metadata={"dataset_name": "mathvista", "capability_family": "mathvista_generic_free_form"},
                )
            }
            digest = __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
                baseline_summary=TrainSetEvalSummary(
                    total_cases=1,
                    correct_cases=0,
                    primary_score=0.0,
                    per_dataset_scores={"mathvista": 0.0},
                    per_family_scores={"mathvista_generic_free_form": 0.0},
                ),
                failure_clusters=[
                    __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                        cluster_id="cluster_1",
                        dataset_name="mathvista",
                        capability_family="mathvista_generic_free_form",
                        cluster_key="mathvista_generic_free_form::free_form::text",
                        total_cases=1,
                        representative_case_ids=["11"],
                        summary_lines=["case_id=11; prompt=What is the value?; expected=2; answer=wrong"],
                    )
                ],
                representative_cases=[],
                recent_rejected_plans=[],
            )
            proposal = {
                "target_family": "mathvista_generic_free_form",
                "target_cluster_ids": ["cluster_1"],
                "representative_case_ids": ["case_id=11", "case_id=126"],
                "next_action": "generate_skill",
                "tool_goal": "",
                "skill_update_note": "Keep answers concise.",
                "rationale": "Normalize id from cluster summary.",
                "expected_gain": "Improve train accuracy.",
            }

            bundle = planner.materialize_bundle(
                proposal,
                digest,
                cases_by_id,
                root / "active",
                root / "work",
            )

        self.assertEqual(bundle.representative_case_ids, ["11"])
        self.assertEqual(bundle.target_family, "mathvista_generic_free_form")
        self.assertEqual(bundle.tools, [])

    def test_evolution_loop_tool_snapshot_includes_builtin_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                max_attempts=1,
            )

            snapshot = loop._tool_availability_snapshot()

            self.assertIn("localized_text_zoom", snapshot.available_tools)
            self.assertIn("chart_value_overlay", snapshot.available_tools)
            self.assertIn("OCR", snapshot.available_tools)
            self.assertIn("Calculator", snapshot.available_tools)

    def test_execute_builtin_tool_returns_ok_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            Image.new("RGB", (24, 24), color=(240, 240, 240)).save(image_path)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                output = execute_builtin_tool("localized_text_zoom", str(image_path))
            finally:
                os.chdir(cwd)

            self.assertIn("STATUS: ok", output)
            self.assertTrue((root / "artifacts" / "localized_text_zoom_output.png").exists())

    def test_execute_gta_calculator_builtin_tool_returns_numeric_answer(self):
        output = execute_builtin_tool("Calculator", "expression=round(75 / 59 * 100)")
        self.assertIn("STATUS: ok", output)
        self.assertIn("127", output)

    def test_execute_gta_draw_box_builtin_tool_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            Image.new("RGB", (32, 32), color=(255, 255, 255)).save(image_path)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                output = execute_builtin_tool(
                    "DrawBox",
                    f"image={image_path}",
                    "bbox=(4, 4, 20, 20)",
                    "annotation=target",
                )
            finally:
                os.chdir(cwd)

            self.assertIn("STATUS: ok", output)
            self.assertIn("ARTIFACTS:", output)
            self.assertTrue((root / "artifacts" / "gta_draw_box_output.png").exists())

    def test_execute_gta_ocr_can_use_official_tool_server(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps("official ocr output").encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            Image.new("RGB", (24, 24), color=(255, 255, 255)).save(image_path)
            old_mode = os.environ.get("VISION_AGENT_GTA_TOOL_MODE")
            old_server = os.environ.get("VISION_AGENT_GTA_TOOL_SERVER")
            os.environ["VISION_AGENT_GTA_TOOL_MODE"] = "official_server"
            os.environ["VISION_AGENT_GTA_TOOL_SERVER"] = "http://official-tool-server"
            try:
                with mock.patch("tools.implementations.shared.gta_official_bridge.request.urlopen", return_value=FakeResponse()):
                    output = execute_builtin_tool("OCR", f"image={image_path}")
            finally:
                if old_mode is None:
                    os.environ.pop("VISION_AGENT_GTA_TOOL_MODE", None)
                else:
                    os.environ["VISION_AGENT_GTA_TOOL_MODE"] = old_mode
                if old_server is None:
                    os.environ.pop("VISION_AGENT_GTA_TOOL_SERVER", None)
                else:
                    os.environ["VISION_AGENT_GTA_TOOL_SERVER"] = old_server

        self.assertIn("STATUS: ok", output)
        self.assertIn("official ocr output", output)

    def test_execute_gta_add_text_can_decode_official_server_image_output(self):
        png_bytes = BytesIO()
        Image.new("RGB", (12, 12), color=(10, 20, 30)).save(png_bytes, format="PNG")
        payload = base64.b64encode(png_bytes.getvalue()).decode("utf-8")

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            Image.new("RGB", (24, 24), color=(255, 255, 255)).save(image_path)
            cwd = Path.cwd()
            old_mode = os.environ.get("VISION_AGENT_GTA_TOOL_MODE")
            old_server = os.environ.get("VISION_AGENT_GTA_TOOL_SERVER")
            os.environ["VISION_AGENT_GTA_TOOL_MODE"] = "official_server"
            os.environ["VISION_AGENT_GTA_TOOL_SERVER"] = "http://official-tool-server"
            try:
                os.chdir(root)
                with mock.patch("tools.implementations.shared.gta_official_bridge.request.urlopen", return_value=FakeResponse()):
                    output = execute_builtin_tool("AddText", f"image={image_path}", "text=hi", "position=mt")
            finally:
                os.chdir(cwd)
                if old_mode is None:
                    os.environ.pop("VISION_AGENT_GTA_TOOL_MODE", None)
                else:
                    os.environ["VISION_AGENT_GTA_TOOL_MODE"] = old_mode
                if old_server is None:
                    os.environ.pop("VISION_AGENT_GTA_TOOL_SERVER", None)
                else:
                    os.environ["VISION_AGENT_GTA_TOOL_SERVER"] = old_server

            artifacts = [path for path in (root / "artifacts").glob("gta_official_addtext_*.png")]

        self.assertIn("STATUS: ok", output)
        self.assertTrue(artifacts)

    def test_loop_records_failed_direction_only_for_actual_failed_evolve_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                max_attempts=1,
                subset_id="chartqa_refocus_v1",
                answer_checker=lambda answer, case: answer == case.gold_answer,
            )
            loop.analyzer_decider = LoopAnalyzerStub()
            loop.generator = LoopGeneratorStub()
            loop.validator = LoopValidatorStub()

            answers = SequenceAgent(["wrong", "still wrong"])
            loop._create_agent = lambda *args, **kwargs: answers

            case = TaskCase(
                case_id="case_1",
                problem_id="chartqa",
                prompt="What is the value?",
                gold_answer="19.31",
            )
            solved = loop.run_single_case(case)
            directions = loop.store.list_failed_directions("chartqa", limit=5)

            self.assertFalse(solved)
            self.assertEqual(len(directions), 1)
            self.assertEqual(directions[0].source, "retry_failed")
            self.assertEqual(directions[0].retry_answer, "still wrong")
            self.assertIn("stored_failed_direction", loop.last_case_report["attempts"][0])
            self.assertFalse(loop.last_case_report["attempts"][0]["direction_duplicate"])

            clean_loop = EvolutionLoop(
                work_dir=root / "work2",
                learned_dir=root / "learned2",
                skills_dir=root / "skills2",
                vlm_client=DummyClient(),
                max_attempts=1,
                subset_id="chartqa_refocus_v2",
                answer_checker=lambda answer, task_case: answer == task_case.gold_answer,
            )
            clean_loop._create_agent = lambda *args, **kwargs: SequenceAgent(["19.31"])
            clean_loop.validator = LoopValidatorStub()
            solved_clean = clean_loop.run_single_case(case)
            self.assertTrue(solved_clean)
            self.assertEqual(clean_loop.store.list_failed_directions("chartqa", limit=5), [])

    def test_textvqa_agent_prompt_adds_short_answer_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                max_attempts=1,
                subset_id=None,
            )
            case = TaskCase(
                case_id="t1",
                problem_id="textvqa",
                prompt="what brand of phone?",
                gold_answer="nokia",
                metadata={"dataset_name": "textvqa", "capability_family": "textvqa_ocr"},
            )

            agent = loop._create_agent(case, attempt=1, phase="solve")

        self.assertIn("Task-specific instructions for OCR / short-answer VQA", agent.system_prompt)
        self.assertIn("Final Answer: <shortest exact answer string>", agent.system_prompt)
        self.assertIn("skip bash and complete immediately", agent.system_prompt)

    def test_vstar_agent_prompt_adds_visual_grounding_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                max_attempts=1,
                subset_id=None,
            )
            case = TaskCase(
                case_id="v1",
                problem_id="vstar",
                prompt="Is the bell above or below the clock?\n(A) above\n(B) below",
                gold_answer="B",
                metadata={"dataset_name": "vstar", "capability_family": "vstar_relative_position"},
            )

            agent = loop._create_agent(case, attempt=1, phase="solve")

        self.assertIn("Task-specific instructions for VStar fine-grained VQA", agent.system_prompt)
        self.assertIn("Visual grounding:", agent.system_prompt)
        self.assertIn("No tools available.", agent.system_prompt)
        self.assertIn("compare their image-plane centers", agent.system_prompt)
        self.assertIn("Final Answer: <option letter and short option text>", agent.system_prompt)

    def test_tool_code_normalization_decodes_literal_newlines(self):
        generator = Generator(DummyClient())
        proposal = generator._normalize_tool_proposal(
            {
                "name": "generic_visual_focus",
                "description": "desc",
                "applicability_conditions": "Use for generic focus.",
                "code": "from core.types import ToolResult\\n\\ndef run(image_path: str) -> ToolResult:\\n    return ToolResult(status=\"ok\", answer=\"\", artifacts=[])\\n",
            }
        )

        self.assertIn("\ndef run", proposal.code)
        compile(proposal.code, "<tool>", "exec")

    def test_validator_allows_generic_opencv_constants_but_rejects_numeric_tables(self):
        validator = Validator(Path("/tmp/work"), Path("/tmp/learned"))
        generic_code = """
from core.types import ToolResult
import cv2
import numpy as np

def run(image_path: str) -> ToolResult:
    edges = cv2.Canny(np.zeros((32, 32), dtype=np.uint8), 50, 150)
    _ = cv2.GaussianBlur(edges, (5, 5), 0)
    return ToolResult(status="ok", answer="", artifacts=[])
"""
        table_code = """
from core.types import ToolResult

FIXED_BOXES = [(1, 2, 3, 4), (10, 20, 30, 40)]

def run(image_path: str) -> ToolResult:
    return ToolResult(status="ok", answer="", artifacts=[])
"""
        origin = TaskCase(case_id="case_1", problem_id="vstar", prompt="Q", gold_answer="A", image_path="/tmp/input.png")
        numeric_origin = TaskCase(case_id="100", problem_id="vstar", prompt="Q", gold_answer="A", image_path="/tmp/input.png")
        generic = ToolProposal(
            name="generic_focus",
            description="desc",
            applicability_conditions="Use generically.",
            code=generic_code,
            usage_example="python -m tools generic_focus <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=[],
        )
        table = ToolProposal(
            name="fixed_focus",
            description="desc",
            applicability_conditions="Use generically.",
            code=table_code,
            usage_example="python -m tools fixed_focus <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=[],
        )

        self.assertEqual(validator._detect_case_specific_tool(generic, origin), "")
        self.assertEqual(validator._detect_case_specific_tool(generic, numeric_origin), "")
        generic.description = "Generated for case_id=100 only."
        self.assertIn("case id", validator._detect_case_specific_tool(generic, numeric_origin))
        self.assertIn("fixed numeric table", validator._detect_case_specific_tool(table, origin))

    def test_dynamic_loader_normalizes_work_dir_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_dir = root / "artifacts" / "run_1"
            artifact_dir.mkdir(parents=True)
            before = _snapshot_artifacts(artifact_dir)
            (artifact_dir / "localized_color_focus_output.png").write_bytes(b"png")

            output = _normalize_artifact_output(
                "STATUS: ok\nARTIFACTS: artifacts/localized_color_focus_output.png",
                artifact_dir,
                before,
                root,
            )

        self.assertIn("ARTIFACTS: artifacts/run_1/localized_color_focus_output.png", output)

    def test_dynamic_loader_accepts_image_key_for_simple_run_tools(self):
        self.assertEqual(_normalize_run_args(["image=/tmp/example.png"]), ["/tmp/example.png"])
        self.assertEqual(_normalize_run_args(["image_path=/tmp/example.png"]), ["/tmp/example.png"])
        self.assertEqual(_normalize_run_args(["/tmp/example.png"]), ["/tmp/example.png"])

    def test_artifact_repair_brief_adds_concrete_protocol_requirements(self):
        tool = ToolProposal(
            name="generic_visual_focus",
            description="desc",
            applicability_conditions="Use generically.",
            code="from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=[])\n",
            usage_example="python -m tools generic_visual_focus <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=[],
        )
        brief = RevisionBrief(
            failure_type="no_artifact",
            reason="Tool did not produce any artifacts",
            rewrite_requirements=["Save at least one real artifact under artifacts/."],
            banned_patterns=["status-only tools"],
            retry_action="revise_tool",
        )

        repaired = SubsetEvolutionLoop._artifact_aware_revision_brief(brief, tool)

        joined = "\n".join(repaired.rewrite_requirements)
        self.assertIn("processed_img numpy ndarray", joined)
        self.assertIn('artifacts/generic_visual_focus_output.png', joined)
        self.assertIn("save_image(processed_img, output_path)", joined)
        self.assertIn("ToolResult(status='ok', answer='', artifacts=[output_path])", joined)

    def test_fallback_artifact_wrapper_preserves_empty_answer_and_compiles(self):
        tool = ToolProposal(
            name="generic_visual_focus",
            description="desc",
            applicability_conditions="Use generically.",
            code=(
                "from core.types import ToolResult\n"
                "from tools.implementations.shared import load_image, save_image\n\n"
                "def run(image_path: str) -> ToolResult:\n"
                "    return ToolResult(status='ok', answer='', artifacts=[])\n"
            ),
            usage_example="python -m tools generic_visual_focus <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=[],
        )

        wrapped = SubsetEvolutionLoop._with_fallback_artifact_wrapper(tool)

        compile(wrapped.code, "<wrapped_tool>", "exec")
        self.assertIn("_original_run_before_artifact_fallback", wrapped.code)
        self.assertIn("artifacts/generic_visual_focus_fallback.png", wrapped.code)
        self.assertNotIn("answer='A'", wrapped.code)
        self.assertIn('answer=""', wrapped.code)

    def test_artifact_fallback_waits_for_repeated_failures(self):
        validation = ValidationResult(
            passed=False,
            failure_type="no_artifact",
            reason="Tool did not produce any artifacts",
        )

        self.assertFalse(
            SubsetEvolutionLoop._should_apply_fallback_artifact_wrapper(
                [{"failure_type": "no_artifact"}],
                validation,
                repair_attempt=1,
            )
        )
        self.assertFalse(
            SubsetEvolutionLoop._should_apply_fallback_artifact_wrapper(
                [{"failure_type": "no_artifact"}, {"failure_type": "runtime_error"}],
                validation,
                repair_attempt=2,
            )
        )
        self.assertTrue(
            SubsetEvolutionLoop._should_apply_fallback_artifact_wrapper(
                [{"failure_type": "no_artifact"}, {"failure_type": "no_artifact"}, {"failure_type": "no_artifact"}],
                validation,
                repair_attempt=3,
            )
        )

    def test_gta_agent_prompt_includes_gta_tool_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                max_attempts=1,
                subset_id=None,
            )
            case = TaskCase(
                case_id="g1",
                problem_id="gta_perception",
                prompt="What number is on the sign?",
                gold_answer="12",
                metadata={"dataset_name": "gta", "capability_family": "gta_perception"},
            )

            agent = loop._create_agent(case, attempt=1, phase="solve")

        self.assertIn("Task-specific instructions for GTA tool-using cases", agent.system_prompt)
        self.assertIn("Fill in concrete arguments such as query=..., expression=..., bbox=...", agent.system_prompt)
        self.assertIn("usage: python -m tools OCR image=<image_path>", agent.system_prompt)

    def test_benchmark_adapters_load_and_score_generic_datasets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            normalized = root / "normalized"
            (normalized / "vstar").mkdir(parents=True, exist_ok=True)
            (normalized / "hrbench").mkdir(parents=True, exist_ok=True)
            (normalized / "vstar" / "train.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "v1",
                            "problem_id": "vstar_reasoning",
                            "prompt": "What label is highlighted?",
                            "answer": "A",
                            "image_path": "a.png",
                            "metadata": {"dataset_name": "vstar", "split": "train", "source_id": "v1", "capability_family": "vstar_reasoning"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (normalized / "hrbench" / "train.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "h1",
                            "problem_id": "hrbench_layout",
                            "prompt": "How many boxes?",
                            "answer": "4",
                            "image_path": "b.png",
                            "metadata": {"dataset_name": "hrbench", "split": "train", "source_id": "h1", "capability_family": "hrbench_layout"},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            vstar_cases = VStarAdapter().load_cases(normalized, "train")
            hrbench_cases = HRBenchAdapter().load_cases(normalized, "train")

            self.assertEqual(vstar_cases[0].capability_family(), "vstar_reasoning")
            self.assertEqual(hrbench_cases[0].capability_family(), "hrbench_layout")
            self.assertTrue(VStarAdapter().check_answer("A", vstar_cases[0]))
            self.assertTrue(HRBenchAdapter().check_answer("The answer is 4.", hrbench_cases[0]))

    def test_subset_loop_accepts_candidate_when_total_score_improves_even_if_seed_case_stays_wrong(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subset_loop = SubsetEvolutionLoop(
                subset_id="chartqa_refocus_v1",
                learned_root=root / "learned",
                skills_dir=root / "skills",
                work_dir=root / "artifacts",
                vlm_client=DummyClient(),
                adapters={"chartqa": ChartQAAdapter()},
                max_planning_rounds=1,
            )
            cases = [
                TaskCase(case_id="seed", problem_id="chartqa", prompt="Q1", gold_answer="A", metadata={"dataset_name": "chartqa", "capability_family": "chartqa"}),
                TaskCase(case_id="other", problem_id="chartqa", prompt="Q2", gold_answer="B", metadata={"dataset_name": "chartqa", "capability_family": "chartqa"}),
            ]
            baseline_summary = TrainSetEvalSummary(total_cases=2, correct_cases=0, primary_score=0.0, per_dataset_scores={"chartqa": 0.0}, per_family_scores={"chartqa": 0.0})
            candidate_summary = TrainSetEvalSummary(total_cases=2, correct_cases=1, primary_score=0.5, per_dataset_scores={"chartqa": 0.5}, per_family_scores={"chartqa": 0.5})
            baseline_records = [
                TrainSetEvalRecord(case_id="seed", dataset_name="chartqa", capability_family="chartqa", prompt="Q1", expected="A", answer="wrong", correct=False),
                TrainSetEvalRecord(case_id="other", dataset_name="chartqa", capability_family="chartqa", prompt="Q2", expected="B", answer="wrong", correct=False),
            ]
            candidate_records = [
                TrainSetEvalRecord(case_id="seed", dataset_name="chartqa", capability_family="chartqa", prompt="Q1", expected="A", answer="wrong", correct=False),
                TrainSetEvalRecord(case_id="other", dataset_name="chartqa", capability_family="chartqa", prompt="Q2", expected="B", answer="B", correct=True),
            ]
            evaluation_queue = [
                (baseline_summary, baseline_records),
                (candidate_summary, candidate_records),
                (candidate_summary, candidate_records),
            ]
            subset_loop.evaluator.evaluate = lambda *args, **kwargs: evaluation_queue.pop(0)
            subset_loop.evaluator.build_digest = lambda *args, **kwargs: __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
                baseline_summary=baseline_summary,
                failure_clusters=[
                    __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                        cluster_id="cluster_1",
                        dataset_name="chartqa",
                        capability_family="chartqa",
                        cluster_key="chartqa::generic",
                        total_cases=2,
                        representative_case_ids=["seed"],
                        summary_lines=["case_id=seed; prompt=Q1"],
                    )
                ],
                representative_cases=[{"case_id": "seed", "dataset_name": "chartqa", "capability_family": "chartqa", "prompt": "Q1"}],
                recent_rejected_plans=[],
            )
            subset_loop.planner.plan_bundle = lambda digest: {
                "target_family": "chartqa",
                "target_cluster_ids": ["cluster_1"],
                "representative_case_ids": ["seed"],
                "next_action": "generate_skill",
                "skill_update_note": "Improve the chartqa SOP.",
                "rationale": "Try a better family-level SOP.",
                "expected_gain": "Improve total training accuracy.",
            }
            subset_loop.planner.materialize_bundle = lambda *args, **kwargs: CapabilityBundleProposal(
                run_id="round_accept",
                target_family="chartqa",
                target_cluster_ids=["cluster_1"],
                representative_case_ids=["seed"],
                skills=[
                    SkillProposal(
                        name="chartqa",
                        description="Improved chart skill",
                        applicability_conditions="Use on chartqa",
                        content="## SOP\n1. Read carefully.",
                        level="mid",
                        depends_on=[],
                    )
                ],
            )
            subset_loop._smoke_validate = lambda *args, **kwargs: (True, "smoke passed")

            report = subset_loop.run(cases)

            self.assertEqual(len(report.round_results), 1)
            self.assertTrue(report.round_results[0].accepted)
            self.assertTrue((root / "learned" / "chartqa_refocus_v1" / "active" / "skills" / "chartqa" / "SKILL.md").exists())

    def test_subset_loop_rejects_tied_candidate_and_keeps_active_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subset_loop = SubsetEvolutionLoop(
                subset_id="chartqa_refocus_v2",
                learned_root=root / "learned",
                skills_dir=root / "skills",
                work_dir=root / "artifacts",
                vlm_client=DummyClient(),
                adapters={"chartqa": ChartQAAdapter()},
                max_planning_rounds=1,
            )
            subset_loop.active_store.promote_skill(
                "chartqa",
                SkillProposal(
                    name="chartqa",
                    description="Baseline skill",
                    applicability_conditions="Use on chartqa",
                    content="## SOP\n1. Baseline.",
                    level="mid",
                    depends_on=[],
                ),
            )
            baseline_summary = TrainSetEvalSummary(total_cases=1, correct_cases=1, primary_score=1.0, per_dataset_scores={"chartqa": 1.0}, per_family_scores={"chartqa": 1.0})
            baseline_records = [TrainSetEvalRecord(case_id="1", dataset_name="chartqa", capability_family="chartqa", prompt="Q", expected="A", answer="A", correct=True)]
            evaluation_queue = [
                (baseline_summary, baseline_records),
                (baseline_summary, baseline_records),
                (baseline_summary, baseline_records),
            ]
            subset_loop.evaluator.evaluate = lambda *args, **kwargs: evaluation_queue.pop(0)
            subset_loop.evaluator.build_digest = lambda *args, **kwargs: __import__("evolution.types", fromlist=["TrainingSetDigest"]).TrainingSetDigest(
                baseline_summary=baseline_summary,
                failure_clusters=[
                    __import__("evolution.types", fromlist=["FailureCluster"]).FailureCluster(
                        cluster_id="cluster_1",
                        dataset_name="chartqa",
                        capability_family="chartqa",
                        cluster_key="chartqa::generic",
                        total_cases=1,
                        representative_case_ids=["1"],
                        summary_lines=["case_id=1; prompt=Q"],
                    )
                ],
                representative_cases=[{"case_id": "1", "dataset_name": "chartqa", "capability_family": "chartqa", "prompt": "Q"}],
                recent_rejected_plans=[],
            )
            subset_loop.planner.plan_bundle = lambda digest: {
                "target_family": "chartqa",
                "target_cluster_ids": ["cluster_1"],
                "representative_case_ids": ["1"],
                "next_action": "generate_skill",
                "skill_update_note": "Try a new SOP.",
                "rationale": "Test tie rejection.",
                "expected_gain": "Tie score.",
            }
            subset_loop.planner.materialize_bundle = lambda *args, **kwargs: CapabilityBundleProposal(
                run_id="round_reject",
                target_family="chartqa",
                target_cluster_ids=["cluster_1"],
                representative_case_ids=["1"],
                skills=[
                    SkillProposal(
                        name="chartqa",
                        description="Rejected skill",
                        applicability_conditions="Use on chartqa",
                        content="## SOP\n1. Rejected.",
                        level="mid",
                        depends_on=[],
                    )
                ],
            )
            subset_loop._smoke_validate = lambda *args, **kwargs: (True, "smoke passed")

            report = subset_loop.run([TaskCase(case_id="1", problem_id="chartqa", prompt="Q", gold_answer="A", metadata={"dataset_name": "chartqa", "capability_family": "chartqa"})])

            self.assertFalse(report.round_results[0].accepted)
            active_skill = subset_loop.active_store.get_skill("chartqa")
            self.assertIn("Baseline.", active_skill.content)
            self.assertEqual(len(subset_loop.active_store.list_recent_rejected_plans()), 1)

    def test_make_frozen_loop_prefers_active_workspace_over_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v3",
            )
            runner = StructuredBenchmarkRunner(config, root, vlm_client=DummyClient())
            active_dir = root / "learned" / "chartqa_refocus_v3" / "active"
            candidate_dir = root / "learned" / "chartqa_refocus_v3" / "candidate" / "round_1"
            active_dir.mkdir(parents=True, exist_ok=True)
            candidate_dir.mkdir(parents=True, exist_ok=True)

            loop = runner._make_frozen_loop(subset_id="chartqa_refocus_v3")

            self.assertEqual(loop.learned_dir, active_dir)

    def test_run_frozen_inference_respects_held_out_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            self._write_image(chart_dir / "2.png")
            rows = [
                {
                    "id": "1",
                    "problem_id": "chartqa",
                    "prompt": "Q1",
                    "answer": "A",
                    "image_path": str(chart_dir / "1.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "1", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
                {
                    "id": "2",
                    "problem_id": "chartqa",
                    "prompt": "Q2",
                    "answer": "B",
                    "image_path": str(chart_dir / "2.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "2", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
            ]
            self._write_normalized_chartqa(root / "normalized", "val", rows)

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v4",
                held_out_limit=1,
            )
            online_loop = FakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            records = runner.run_frozen_inference(subset_id=config.subset_id)

            self.assertEqual(len(records), 1)

    def test_record_from_agent_result_counts_prechain_tools_as_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v5",
            )
            runner = StructuredBenchmarkRunner(config, root, vlm_client=DummyClient())
            case = TaskCase(
                case_id="1",
                problem_id="chartqa",
                prompt="Q",
                gold_answer="A",
                image_path="img.png",
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            )
            result = AgentResult(task="Q", final_answer="A", steps=[], total_turns=1, success=True, all_artifacts=[])

            record = runner._record_from_agent_result(
                setting="frozen_inference",
                split="val",
                case=case,
                result=result,
                correct=True,
                chain_trace=["chart_bar_approximation_tool"],
            )

            self.assertTrue(record.used_tool)
            self.assertEqual(record.tool_names, ["chart_bar_approximation_tool"])

    def test_run_frozen_inference_resumes_existing_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            self._write_image(chart_dir / "2.png")
            rows = [
                {
                    "id": "1",
                    "problem_id": "chartqa",
                    "prompt": "Q1",
                    "answer": "A",
                    "image_path": str(chart_dir / "1.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "1", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
                {
                    "id": "2",
                    "problem_id": "chartqa",
                    "prompt": "Q2",
                    "answer": "B",
                    "image_path": str(chart_dir / "2.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "2", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
            ]
            self._write_normalized_chartqa(root / "normalized", "val", rows)

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_resume_v1",
                held_out_limit=2,
            )
            online_loop = FakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)
            runner.records_path.parent.mkdir(parents=True, exist_ok=True)
            runner.records_path.write_text(
                json.dumps(
                    {
                        "setting": "frozen_inference",
                        "split": "val",
                        "case_id": "1",
                        "problem_id": "chartqa",
                        "expected": "A",
                        "answer": "A",
                        "correct": True,
                        "score": 1.0,
                        "turns": 1,
                        "tool_count": 0,
                        "tool_names": [],
                        "used_tool": False,
                        "artifact_paths": [],
                        "chain_trace": [],
                        "image_path": str(chart_dir / "1.png"),
                        "metadata": {"dataset_name": "chartqa", "capability_family": "chartqa"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            records = runner.run_frozen_inference(subset_id=config.subset_id)

            self.assertEqual([row.case_id for row in records], ["1", "2"])
            self.assertEqual(records[0].answer, "A")
            persisted = runner.records_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(persisted), 2)

    def test_run_frozen_inference_reruns_bad_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            (root / "learned").mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "1.png")
            rows = [
                {
                    "id": "1",
                    "problem_id": "chartqa",
                    "prompt": "Q1",
                    "answer": "A",
                    "image_path": str(chart_dir / "1.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "1", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
            ]
            self._write_normalized_chartqa(root / "normalized", "val", rows)

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_resume_v2",
                held_out_limit=1,
            )
            online_loop = FakeLoop(root / "learned" / config.subset_id)
            frozen_loop = FrozenLoop(root / "learned" / config.subset_id)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)
            runner.records_path.parent.mkdir(parents=True, exist_ok=True)
            runner.records_path.write_text(
                json.dumps(
                    {
                        "setting": "frozen_inference",
                        "split": "val",
                        "case_id": "1",
                        "problem_id": "chartqa",
                        "expected": "A",
                        "answer": "",
                        "correct": False,
                        "score": 0.0,
                        "turns": 1,
                        "tool_count": 0,
                        "tool_names": [],
                        "used_tool": False,
                        "artifact_paths": [],
                        "chain_trace": [],
                        "image_path": str(chart_dir / "1.png"),
                        "metadata": {"dataset_name": "chartqa", "capability_family": "chartqa", "runtime_error": "timeout"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            records = runner.run_frozen_inference(subset_id=config.subset_id)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].case_id, "1")
            self.assertEqual(records[0].answer, "A")
            persisted = [json.loads(line) for line in runner.records_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(persisted), 2)
            self.assertEqual(persisted[-1]["answer"], "A")

    def test_rebuild_summary_includes_existing_frozen_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_refocus_v6",
            )
            runner = StructuredBenchmarkRunner(config, root, vlm_client=DummyClient())
            runner.records_path.parent.mkdir(parents=True, exist_ok=True)
            runner.records_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "setting": "agent_train_adaptive",
                                "split": "train",
                                "case_id": "t1",
                                "problem_id": "chartqa",
                                "expected": "A",
                                "answer": "A",
                                "correct": True,
                                "score": 1.0,
                                "turns": 1,
                                "tool_count": 1,
                                "tool_names": ["focus_chart"],
                                "used_tool": True,
                                "artifact_paths": [],
                                "chain_trace": ["focus_chart"],
                                "image_path": "",
                                "metadata": {"dataset_name": "chartqa", "capability_family": "chartqa"},
                            }
                        ),
                        json.dumps(
                            {
                                "setting": "frozen_inference",
                                "split": "val",
                                "case_id": "v1",
                                "problem_id": "chartqa",
                                "expected": "A",
                                "answer": "A",
                                "correct": True,
                                "score": 1.0,
                                "turns": 1,
                                "tool_count": 1,
                                "tool_names": ["focus_chart"],
                                "used_tool": True,
                                "artifact_paths": [],
                                "chain_trace": ["focus_chart"],
                                "image_path": "",
                                "metadata": {"dataset_name": "chartqa", "capability_family": "chartqa"},
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            summary = runner.rebuild_summary(snapshot_name="chartqa_refocus_v6_train_snapshot")

            self.assertAlmostEqual(summary["settings"]["frozen_inference"]["accuracy"], 1.0)
            self.assertAlmostEqual(summary["frozen_inference_accuracy"], 1.0)

    def test_agent_train_checkpoint_writes_partial_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_checkpoint_v1",
            )
            runner = StructuredBenchmarkRunner(config, root, vlm_client=DummyClient())
            case = TaskCase(
                case_id="1",
                problem_id="chartqa",
                prompt="Q",
                gold_answer="A",
                image_path="img.png",
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            )
            baseline = TrainSetEvalRecord(
                case_id="1",
                dataset_name="chartqa",
                capability_family="chartqa",
                prompt="Q",
                expected="A",
                answer="wrong",
                correct=False,
                turns=1,
                tool_names=[],
                artifact_paths=[],
                chain_trace=[],
            )
            final = TrainSetEvalRecord(
                case_id="1",
                dataset_name="chartqa",
                capability_family="chartqa",
                prompt="Q",
                expected="A",
                answer="A",
                correct=True,
                turns=1,
                tool_names=["chart_value_overlay"],
                artifact_paths=["artifacts/focus.png"],
                chain_trace=["chart_value_overlay"],
            )
            round_result = CandidateEvalResult(
                run_id="round_1",
                accepted=True,
                reason="Accepted candidate",
                baseline_score=0.0,
                candidate_score=1.0,
                score_delta=1.0,
                smoke_passed=True,
                target_family="chartqa",
                target_cluster_ids=["cluster_1"],
                representative_case_ids=["1"],
                activated_snapshot="chartqa_checkpoint_v1_round_1_accepted",
                baseline_summary=TrainSetEvalSummary(total_cases=1, correct_cases=0, primary_score=0.0),
                candidate_summary=TrainSetEvalSummary(total_cases=1, correct_cases=1, primary_score=1.0),
            )

            runner._checkpoint_agent_train_adaptive(
                cases=[case],
                baseline_records=[baseline],
                current_records=[final],
                round_results=[round_result],
                snapshot_name="chartqa_checkpoint_v1_round_1_accepted",
            )

            rows = [json.loads(line) for line in runner.records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["setting"], "agent_train_adaptive")
            self.assertEqual(rows[0]["answer"], "A")
            summary = json.loads(runner.summary_path.read_text(encoding="utf-8"))
            self.assertAlmostEqual(summary["settings"]["agent_train_adaptive"]["accuracy"], 1.0)
            self.assertEqual(summary["snapshot_name"], "chartqa_checkpoint_v1_round_1_accepted")

    def test_agent_train_final_write_replaces_checkpointed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_checkpoint_v2",
            )
            runner = StructuredBenchmarkRunner(config, root, vlm_client=DummyClient())
            case = TaskCase(
                case_id="1",
                problem_id="chartqa",
                prompt="Q",
                gold_answer="A",
                image_path="img.png",
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            )
            baseline = TrainSetEvalRecord(
                case_id="1",
                dataset_name="chartqa",
                capability_family="chartqa",
                prompt="Q",
                expected="A",
                answer="wrong",
                correct=False,
                turns=1,
                tool_names=[],
                artifact_paths=[],
                chain_trace=[],
            )
            final = TrainSetEvalRecord(
                case_id="1",
                dataset_name="chartqa",
                capability_family="chartqa",
                prompt="Q",
                expected="A",
                answer="A",
                correct=True,
                turns=1,
                tool_names=["chart_value_overlay"],
                artifact_paths=["artifacts/focus.png"],
                chain_trace=["chart_value_overlay"],
            )
            report = SubsetEvolutionRunReport(
                baseline_summary=TrainSetEvalSummary(total_cases=1, correct_cases=0, primary_score=0.0),
                final_summary=TrainSetEvalSummary(total_cases=1, correct_cases=1, primary_score=1.0),
                baseline_records=[baseline],
                final_records=[final],
                round_results=[],
                snapshot_name="chartqa_checkpoint_v2_train_snapshot",
            )
            subset_loop = FakeSubsetLoop(report)
            runner = TestStructuredRunner(config, root, online_loop=FakeLoop(root / "learned"), frozen_loop=FrozenLoop(root / "learned"), subset_loop=subset_loop)

            runner._checkpoint_agent_train_adaptive(
                cases=[case],
                baseline_records=[baseline],
                current_records=[final],
                round_results=[],
                snapshot_name="chartqa_checkpoint_v2_round_1_accepted",
            )
            records, _ = runner._run_agent_train_adaptive([case])

            self.assertEqual(len(records), 1)
            rows = [json.loads(line) for line in runner.records_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["answer"], "A")

    def test_run_preset_tools_only_disables_evolved_skill_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills").mkdir(parents=True, exist_ok=True)
            subset_dir = root / "learned" / "chartqa_mastery_v1"
            subset_dir.mkdir(parents=True, exist_ok=True)
            chart_dir = root / "charts"
            self._write_image(chart_dir / "2.png")
            rows = [
                {
                    "id": "2",
                    "problem_id": "chartqa",
                    "prompt": "Q2",
                    "answer": "B",
                    "image_path": str(chart_dir / "2.png"),
                    "metadata": {"dataset_name": "chartqa", "split": "val", "source_id": "2", "question_type": "generic", "answer_type": "string", "capability_family": "chartqa"},
                },
            ]
            self._write_normalized_chartqa(root / "normalized", "val", rows)
            CapabilityStore(subset_dir).promote_skill(
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

            config = StructuredExperimentConfig(
                dataset="chartqa",
                raw_data_root=root / "raw",
                normalized_data_root=root / "normalized",
                subset_id="chartqa_mastery_v1",
                held_out_limit=1,
            )
            online_loop = FakeLoop(subset_dir)
            frozen_loop = FrozenLoop(subset_dir)
            runner = TestStructuredRunner(config, root, online_loop, frozen_loop)

            records = runner.run_frozen_inference(subset_id=config.subset_id, use_skill=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].setting, "preset_tools_only")
            self.assertEqual(records[0].answer, "wrong")
            summary = runner.rebuild_summary(snapshot_name="chartqa_mastery_v1_train_snapshot")
            self.assertAlmostEqual(summary["settings"]["preset_tools_only"]["accuracy"], 0.0)
            self.assertAlmostEqual(summary["preset_tools_only_accuracy"], 0.0)

    def test_run_preset_tools_only_still_keeps_builtin_tools_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                subset_id="chartqa_mastery_v2",
            )
            case = TaskCase(
                case_id="1",
                problem_id="chartqa",
                prompt="Q",
                gold_answer="A",
                image_path="img.png",
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            )

            _ = loop._create_agent(case, include_learned_skills=False)
            snapshot = loop._tool_availability_snapshot()

            self.assertIn("localized_text_zoom", snapshot.available_tools)
            self.assertIn("chart_value_overlay", snapshot.available_tools)

    def test_gta_same_tool_mode_filters_to_case_tools_and_hides_learned_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned_dir = root / "learned"
            subset_dir = learned_dir / "gta_same_tool_v1"
            (subset_dir / "tools").mkdir(parents=True, exist_ok=True)
            (subset_dir / "tools" / "focus_chart.py").write_text("def run(*args, **kwargs):\n    return 'ok'\n", encoding="utf-8")
            loop = EvolutionLoop(
                work_dir=root / "work",
                learned_dir=learned_dir,
                skills_dir=root / "skills",
                vlm_client=DummyClient(),
                subset_id="gta_same_tool_v1",
                capability_mode="skill_only_same_tools",
            )
            case = TaskCase(
                case_id="g1",
                problem_id="gta_perception",
                prompt="Read the price.",
                gold_answer="12",
                image_path="img.png",
                metadata={"dataset_name": "gta", "capability_family": "gta_perception", "gt_tools": ["OCR", "Calculator"]},
            )

            snapshot = loop._tool_availability_snapshot(case=case)
            agent = loop._create_agent(case, include_learned_skills=False)

            self.assertEqual(snapshot.available_tools, ["Calculator", "OCR"])
            self.assertEqual(agent.config.allowed_tool_names, ["Calculator", "OCR"])
            self.assertTrue(agent.config.require_python_tool_command)
            self.assertNotIn("focus_chart", agent.system_prompt)
            self.assertNotIn("ImageDescription", agent.system_prompt)

    def test_gta_same_tool_mode_agent_blocks_non_tool_and_non_whitelisted_commands(self):
        agent = ReActAgent(
            client=DummyClient(),
            config=AgentConfig(
                work_dir=Path(tempfile.mkdtemp()),
                allowed_tool_names=["OCR"],
                require_python_tool_command=True,
            ),
            tool_definitions="Use: python -m tools <tool_name> [args]",
        )

        self.assertIn("only allows tool invocations", agent._run_bash("echo hi"))
        self.assertIn("not allowed for this task", agent._run_bash('python -m tools Calculator expression="1+1"'))

    def test_same_tool_frozen_setting_name_variants(self):
        self.assertEqual(
            StructuredBenchmarkRunner._frozen_setting_name("skill_only_same_tools", force_skill=False, use_skill=True),
            "skill_only_frozen_inference",
        )
        self.assertEqual(
            StructuredBenchmarkRunner._frozen_setting_name("skill_only_same_tools", force_skill=False, use_skill=False),
            "same_tool_preset_tools_only",
        )

    def test_subset_summary_tracks_multiple_dataset_scores(self):
        rows = [
            StructuredCaseRecord(
                setting="agent_train_adaptive",
                split="train",
                case_id="c1",
                problem_id="chartqa",
                expected="A",
                answer="A",
                correct=True,
                turns=1,
                tool_count=0,
                metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
            ),
            StructuredCaseRecord(
                setting="agent_train_adaptive",
                split="train",
                case_id="h1",
                problem_id="hrbench",
                expected="B",
                answer="wrong",
                correct=False,
                turns=1,
                tool_count=0,
                metadata={"dataset_name": "hrbench", "capability_family": "hrbench_layout"},
            ),
        ]

        summary = _aggregate_records(rows)["agent_train_adaptive"]

        self.assertEqual(summary["total"], 2)
        self.assertAlmostEqual(summary["accuracy"], 0.5)
        self.assertAlmostEqual(summary["per_dataset_accuracy"]["chartqa"], 1.0)
        self.assertAlmostEqual(summary["per_dataset_accuracy"]["hrbench"], 0.0)
        self.assertAlmostEqual(summary["per_family_accuracy"]["chartqa"], 1.0)
        self.assertAlmostEqual(summary["per_family_accuracy"]["hrbench_layout"], 0.0)

    def test_aggregate_records_uses_partial_scores_when_available(self):
        rows = [
            StructuredCaseRecord(
                setting="frozen_inference",
                split="val",
                case_id="t1",
                problem_id="textvqa",
                expected="openai",
                answer="open ai",
                correct=False,
                score=2 / 3,
                turns=1,
                tool_count=0,
                metadata={"dataset_name": "textvqa", "capability_family": "textvqa_ocr"},
            ),
            StructuredCaseRecord(
                setting="frozen_inference",
                split="val",
                case_id="t2",
                problem_id="textvqa",
                expected="42",
                answer="42",
                correct=True,
                score=1.0,
                turns=1,
                tool_count=0,
                metadata={"dataset_name": "textvqa", "capability_family": "textvqa_ocr"},
            ),
        ]

        summary = _aggregate_records(rows)["frozen_inference"]

        self.assertAlmostEqual(summary["accuracy"], 5 / 6)
        self.assertAlmostEqual(summary["per_dataset_accuracy"]["textvqa"], 5 / 6)

    def test_run_settings_normalize_self_evolve_alias(self):
        self.assertEqual(_normalize_settings(["self_evolve"]), ["agent_train_adaptive"])
        self.assertEqual(
            _normalize_settings(["direct_vlm", "self_evolve"]),
            ["direct_vlm", "agent_train_adaptive"],
        )
        self.assertEqual(_normalize_settings(["frozen_transfer"]), ["frozen_inference"])
        self.assertEqual(_normalize_settings(["preset_tools_only"]), ["preset_tools_only"])
        self.assertEqual(_normalize_settings(["skill_only_train_adaptive"]), ["skill_only_train_adaptive"])
        self.assertEqual(_normalize_settings(["same_tool_preset_tools_only"]), ["same_tool_preset_tools_only"])
        self.assertEqual(_normalize_settings(["skill_only_frozen_inference"]), ["skill_only_frozen_inference"])
        self.assertEqual(_normalize_settings(["scratch_skill_train_adaptive"]), ["scratch_skill_train_adaptive"])
        self.assertEqual(_normalize_settings(["agent_train_batch_evolve"]), ["agent_train_batch_evolve"])

    def test_skill_from_mastery_strategy_builds_branching_sop(self):
        loop = SubsetEvolutionLoop.__new__(SubsetEvolutionLoop)
        strategy = MasteryStrategyCandidate(
            name="text_zoom_then_chart",
            tool_sequence=["localized_text_zoom", "chart_value_overlay"],
            trigger_conditions=["small labels or crowded chart text"],
            avoid_conditions=["direct value is already obvious"],
            fallback_action="answer_directly",
            rationale="Chain zoom before chart overlay when labels are hard to read.",
        )

        skill = loop._skill_from_mastery_strategy("chartqa", strategy)

        self.assertEqual(skill.name, "chartqa")
        self.assertIn("## SOP", skill.content)
        self.assertIn("localized_text_zoom", skill.content)
        self.assertIn("chart_value_overlay", skill.content)
        self.assertIn("avoid condition", skill.content)

    def test_skill_from_mastery_strategy_uses_gta_argument_templates(self):
        loop = SubsetEvolutionLoop.__new__(SubsetEvolutionLoop)
        strategy = MasteryStrategyCandidate(
            name="ocr_then_calculate",
            tool_sequence=["OCR", "Calculator"],
            trigger_conditions=["text in image must be read and then computed"],
            avoid_conditions=["answer is visually obvious"],
            fallback_action="answer_directly",
            rationale="Use OCR before arithmetic when the image contains the inputs.",
        )

        skill = loop._skill_from_mastery_strategy("gta_perception", strategy)

        self.assertIn("python -m tools OCR image=<image_path>", skill.content)
        self.assertIn('python -m tools Calculator expression="numeric expression"', skill.content)

    def test_digest_payload_includes_mastery_profiles(self):
        evaluator = SubsetEvaluator.__new__(SubsetEvaluator)
        digest = TrainingSetDigest(
            baseline_summary=TrainSetEvalSummary(total_cases=1, correct_cases=1, primary_score=1.0),
            family_memories=[
                FamilyMemory(
                    capability_family="chartqa",
                    mastery_profiles=[
                        MasteryProfile(
                            capability_family="chartqa",
                            primary_tool="chart_value_overlay",
                            best_strategy_name="chart_overlay_primary",
                            coverage=0.75,
                            precision=0.8,
                            score_delta=0.1,
                        )
                    ],
                )
            ],
        )

        payload = evaluator.digest_payload(digest)

        self.assertIn("mastery_profiles", payload)
        self.assertIn("chartqa", payload["mastery_profiles"])
        self.assertEqual(payload["mastery_profiles"]["chartqa"][0]["primary_tool"], "chart_value_overlay")

    def test_eval_diff_tracks_fixed_and_regressed_cases(self):
        def row(case_id: str, correct: bool, answer: str) -> TrainSetEvalRecord:
            return TrainSetEvalRecord(
                case_id=case_id,
                dataset_name="vstar",
                capability_family="vstar_direct_attributes",
                prompt="question",
                expected="A",
                answer=answer,
                correct=correct,
            )

        diff = SubsetEvolutionLoop._eval_diff(
            [
                row("fixed", False, "B"),
                row("regressed", True, "A"),
                row("still_wrong", False, "C"),
            ],
            [
                row("fixed", True, "A"),
                row("regressed", False, "B"),
                row("still_wrong", False, "D"),
            ],
        )

        self.assertEqual(diff["fixed_count"], 1)
        self.assertEqual(diff["regressed_count"], 1)
        self.assertEqual(diff["net_fixed_count"], 0)
        self.assertEqual(diff["fixed_cases"][0]["case_id"], "fixed")
        self.assertEqual(diff["regressed_cases"][0]["case_id"], "regressed")
        self.assertEqual(diff["unchanged_wrong_case_ids"], ["still_wrong"])

    def test_learned_tool_artifact_gate_requires_artifact_when_tool_used(self):
        bundle = CapabilityBundleProposal(
            run_id="r1",
            target_family="vstar_direct_attributes",
            tools=[
                ToolProposal(
                    name="localized_color_focus",
                    description="desc",
                    applicability_conditions="use",
                    code="",
                    usage_example="python -m tools localized_color_focus <image_path>",
                    expected_inputs=["image_path"],
                    expected_outputs=["artifact"],
                )
            ],
        )
        missing = TrainSetEvalRecord(
            case_id="c1",
            dataset_name="vstar",
            capability_family="vstar_direct_attributes",
            prompt="q",
            expected="A",
            answer="A",
            correct=True,
            tool_names=["localized_color_focus"],
            artifact_paths=[],
        )
        ok = TrainSetEvalRecord(
            case_id="c1",
            dataset_name="vstar",
            capability_family="vstar_direct_attributes",
            prompt="q",
            expected="A",
            answer="A",
            correct=True,
            tool_names=["localized_color_focus"],
            artifact_paths=["artifacts/out.png"],
        )

        self.assertFalse(SubsetEvolutionLoop._learned_tool_artifact_gate(bundle, [missing])[0])
        self.assertTrue(SubsetEvolutionLoop._learned_tool_artifact_gate(bundle, [ok])[0])


if __name__ == "__main__":
    unittest.main()
