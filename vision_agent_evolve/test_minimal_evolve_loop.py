"""Tests for the minimal task-specific evolve loop."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path
from time import sleep
import sys
import os

from PIL import Image

from core.types import AgentResult
from core.types import TaskCase
from core.types import ToolResult
from core.agent import AgentConfig, ReActAgent
from core.parser import ReActParser
from evolution.loop import EvolutionLoop
from evolution.roles import AnalyzerDecider, Generator
from evolution.store import CapabilityStore
from evolution.types import FailureAnalysis, MasteryProfile, SkillProposal, SkillReferenceProposal, ToolProposal, ValidationResult
from evolution.validator import Validator
from tools.builtin_tools import execute_builtin_tool, list_builtin_tools
from tools.dynamic_loader import execute_learned_tool
from run import _build_cases


class DummyVLMClient:
    def chat(self, messages, settings=None):
        return "CORRECT", None


class DummyUsage:
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0


class SkillGeneratorClient:
    def __init__(self, payload: str):
        self.payload = payload
        self.last_messages = None

    def chat(self, messages, settings=None):
        self.last_messages = messages
        return self.payload, DummyUsage()


class FakeAgent:
    def __init__(self, answer: str):
        self.answer = answer

    def run(self, task: str, image_path: str = "", initial_observations=None) -> AgentResult:
        return AgentResult(
            task=task,
            final_answer=self.answer,
            steps=[],
            total_turns=1,
            success=True,
            all_artifacts=[],
        )


class ScriptedClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0

    def chat(self, messages, settings=None):
        response = self.responses[self.index]
        self.index += 1
        return response, DummyUsage()


class AnalyzerClient:
    def __init__(self, payload: str):
        self.payload = payload

    def chat(self, messages, settings=None):
        return self.payload, DummyUsage()


class FakeReActAgent(ReActAgent):
    def _run_bash(self, command: str) -> str:
        Path("artifacts").mkdir(exist_ok=True)
        out = Path("artifacts") / "forced_tool.png"
        out.write_text("ok", encoding="utf-8")
        return "ANSWER: restored\nSTATUS: ok\nARTIFACTS: artifacts/forced_tool.png"


class FakeNoArtifactReActAgent(ReActAgent):
    def _run_bash(self, command: str) -> str:
        return "STATUS: ok\nANSWER: edited"


class StubAnalyzer:
    def __init__(self):
        self.total_usage = type("Usage", (), {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})()

    def analyze_and_decide(self, case, result, current_capabilities, previous_attempts=None, attempt=None, extra_artifacts=None, chain_context=None, capability_snapshot="", known_failure_lessons=None):
        return FailureAnalysis(
            root_cause="Mirror needs restoration before reading",
            next_action="generate_tool",
            confidence=0.9,
            missing_step="restore the mirrored clock",
            tool_goal="flip the image horizontally and output the restored clock",
            skill_update_note="For mirrored clocks, use the restore tool before answering.",
            rationale="Restoring the clock is the smallest useful next step.",
        )


class StubGenerator:
    def __init__(self):
        self.total_usage = type("Usage", (), {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0})()

    def generate_tool(self, case, analysis, chain_context=None):
        code = textwrap.dedent(
            """
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parents[2]))

            from core.types import ToolResult

            def main():
                Path("artifacts").mkdir(exist_ok=True)
                out = Path("artifacts") / "restored.png"
                out.write_text("ok", encoding="utf-8")
                print(ToolResult(status="ok", answer="restored", artifacts=[str(out)]))

            if __name__ == "__main__":
                main()
            """
        ).strip()
        return ToolProposal(
            name="mirror_restore",
            description="Restore mirrored clock images",
            applicability_conditions="Use when the clock image is mirrored and needs horizontal reflection correction.",
            code=code,
            usage_example="python -m tools mirror_restore <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=["artifacts/restored.png"],
        )

    def generate_skill(self, case, analysis, tool_proposal=None, existing_skill_content=None, chain_context=None):
        return SkillProposal(
            name=case.problem_id,
            description="Use the mirror restore tool before answering mirrored clocks.",
            applicability_conditions="Use when the clock image is mirrored and can be solved by a single horizontal flip.",
            content=textwrap.dedent(
                """
                ## When this applies
                - The image is a mirrored analog clock.

                ## Do this first
                - Run `python -m tools mirror_restore <image_path>`.

                ## Then
                - Inspect the restored image and answer the question.

                ## If still failing
                - Analyze which extra transformation is still missing.
                """
            ).strip(),
            level="mid",
            depends_on=["reasoning", "vision_analysis"],
        )


class StubValidator:
    def __init__(self, store: CapabilityStore):
        self.store = store

    def build_chain_context(self, case, skill_content, attempt=None):
        from evolution.types import ToolChainContext
        return ToolChainContext(latest_input_image=case.image_path)

    def validate_tool(self, proposal, origin_case, agent_factory, regression_cases=None, chain_context=None, attempt=None):
        tool_file = self.store.tools_dir / f"{proposal.name}.py"
        tool_file.write_text(proposal.code, encoding="utf-8")
        return ValidationResult(
            passed=True,
            static_ok=True,
            origin_ok=True,
            regression_ok=True,
            input_image=chain_context.latest_artifact if chain_context and chain_context.latest_artifact else origin_case.image_path,
            chain_trace=list(chain_context.tool_sequence) if chain_context else [],
        )

    def validate_skill(self, proposal, problem_id):
        return ValidationResult(passed=True, static_ok=True, origin_ok=True, regression_ok=True)

    def restore_preserved_tool(self, tool_name: str):
        return None

    def clear_preserved_tool(self, tool_name: str):
        return None


class MinimalLoop(EvolutionLoop):
    def __init__(self, work_dir: Path, learned_dir: Path, skills_dir: Path):
        super().__init__(
            work_dir=work_dir,
            learned_dir=learned_dir,
            skills_dir=skills_dir,
            vlm_client=DummyVLMClient(),
            max_attempts=1,
        )
        self.created_agent_skills: list[str | None] = []

    def _check_success(self, result, case):
        return case.gold_answer in result.final_answer

    def _create_agent(self, case, task_skill_override=None, required_tool_name=None, required_skill_name=None, require_bash_action_before_complete=False, required_image_artifact_before_complete=False, attempt=None, phase="solve"):
        skill = task_skill_override or self.store.get_skill(case.problem_id)
        self.created_agent_skills.append(skill.content if skill else None)
        if task_skill_override is None and not self.store.has_skill(case.problem_id):
            return FakeAgent("wrong answer")
        return FakeAgent(case.gold_answer)

    def _print_token_summary(self, attempts: int):
        return None


class MinimalEvolveLoopTests(unittest.TestCase):
    def _write_skill(self, root: Path, name: str, content: str) -> None:
        skill_dir = root / "library" / "foundation"
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_dir.joinpath(f"{name}.md").write_text(content, encoding="utf-8")

    def test_problem_skill_overwrites_previous_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            learned_dir = Path(tmp) / "learned"
            store = CapabilityStore(learned_dir)

            first = SkillProposal(
                name="mirror_clock",
                description="First rule",
                applicability_conditions="Use when the clock is mirrored.",
                content="## Do this first\n- Use restore.",
                level="mid",
                depends_on=["reasoning"],
            )
            second = SkillProposal(
                name="mirror_clock",
                description="Updated rule",
                applicability_conditions="Use when the clock is mirrored and may need a second correction step.",
                content="## Do this first\n- Use restore.\n\n## Then\n- Rotate if needed.",
                level="mid",
                depends_on=["reasoning", "vision_analysis"],
            )

            store.promote_skill("mirror_clock", first)
            store.promote_skill("mirror_clock", second)

            content = (learned_dir / "skills" / "mirror_clock" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("Rotate if needed.", content)
            self.assertNotIn("Previous Knowledge", content)
            self.assertNotIn("New Additions", content)
            self.assertIn("applicability_conditions:", content)

    def test_failure_skill_is_saved_without_overwriting_main_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            learned_dir = Path(tmp) / "learned"
            store = CapabilityStore(learned_dir)
            proposal = SkillProposal(
                name="mirror_clock",
                description="Failure lesson",
                applicability_conditions="Use when a prior mirror_clock SOP still failed on a new visual variation.",
                content="## SOP\n1. Re-check whether an added step or added condition is needed.",
                level="low",
                depends_on=[],
            )

            store.save_failure_skill("mirror_clock", "18", proposal)

            lesson = learned_dir / "skills" / "mirror_clock" / "failure_skills" / "case_18.md"
            self.assertTrue(lesson.exists())
            text = lesson.read_text(encoding="utf-8")
            self.assertIn("kind: failure_lesson", text)
            self.assertIn("Failure lesson", text)

    def test_store_lists_recent_failure_lessons_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            learned_dir = Path(tmp) / "learned"
            store = CapabilityStore(learned_dir)
            for case_id in ["1", "2", "3", "4"]:
                store.save_failure_skill(
                    "mirror_clock",
                    case_id,
                    SkillProposal(
                        name="mirror_clock",
                        description=f"Lesson {case_id}",
                        applicability_conditions="Use when a prior SOP still failed.",
                        content=f"## SOP\n1. Lesson {case_id}",
                        level="low",
                        depends_on=[],
                    ),
                )
                sleep(0.01)

            lessons = store.list_failure_skills("mirror_clock", limit=3)
            self.assertEqual(len(lessons), 3)
            self.assertEqual([lesson.description for lesson in lessons], ["Lesson 4", "Lesson 3", "Lesson 2"])

    def test_generate_failure_skill_prefers_solver_useful_lesson_over_tool_registration_noise(self):
        client = SkillGeneratorClient(
            textwrap.dedent(
                """
                {
                  "name": "billiards",
                  "description": "Failure lesson for unavailable tool issues.",
                  "applicability_conditions": "When the tool was not registered.",
                  "content": "## SOP\\n1. Helpful method: The agent failed because it tried to use a tool that wasn't registered.\\n2. Common mistake: The agent attempted to call a non-existent tool 'billiards_path_tracer'.\\n3. Next time: Use a valid tool.",
                  "level": "low",
                  "depends_on": []
                }
                """
            ).strip()
        )
        generator = Generator(client)
        case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
            case_id="11",
            problem_id="billiards",
            prompt="Which pocket will the ball enter?",
            gold_answer="3",
            image_path="datasets/mira/billiards/images/11.png",
            metadata={
                "dense_caption": "The blue ball and the muted green arrow indicate the initial direction, and only the first dark inner rail is a reflection boundary."
            },
        )
        analysis = FailureAnalysis(
            root_cause="The agent attempted to use a tool that wasn't registered.",
            next_action="give_up",
            confidence=0.1,
            missing_step="Verify the initial direction and each bounce against the inner rail boundary before naming the pocket.",
            rationale="Start from the blue ball, the arrow direction cue, and the true inner rail boundary, then trace each segment step by step.",
        )
        lesson = generator.generate_failure_skill(
            case,
            analysis,
            AgentResult(
                task=case.prompt,
                final_answer="4",
                steps=[],
                total_turns=1,
                success=False,
            ),
            existing_skill_content="## SOP\n1. Run `python -m tools billiards_path_tracer <image_path>`.\n2. Answer the final pocket.",
            chain_context=__import__("evolution.types", fromlist=["ToolChainContext"]).ToolChainContext(
                tool_sequence=["billiards_path_tracer"],
                failed=True,
                reason="tool was not registered",
            ),
            family_examples=[
                __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                    case_id="2",
                    problem_id="billiards",
                    prompt="Which pocket?",
                    gold_answer="2",
                    metadata={"dense_caption": "A billiards table with a blue ball and a muted green directional arrow."},
                ),
                case,
            ],
        )

        self.assertIsNotNone(client.last_messages)
        prompt = client.last_messages[1]["content"]
        self.assertIn("Ignore temporary tool registration, loading, promotion, or availability issues", prompt)
        self.assertIn("Task-family examples seen so far", prompt)
        self.assertNotIn("wasn't registered", lesson.content.lower())
        self.assertNotIn("non-existent tool", lesson.content.lower())
        self.assertIn("stable visual anchors", lesson.content.lower())
        self.assertIn("inner rail boundary", lesson.content.lower())
        self.assertNotIn("billiards_path_tracer", lesson.content)

    def test_build_cases_reads_dense_caption_and_solver_text(self):
        cases = _build_cases(Path(__file__).resolve().parent / "datasets/mira/mirror_clock/example_001.json")

        self.assertEqual(cases[0].dense_caption(), "This is a mirrored analog clock.")
        self.assertEqual(cases[1].dense_caption(), "This is a mirrored analog clock that is also upside down.")
        self.assertEqual(
            cases[0].prompt,
            "This is what a clock looks like in a mirror. What time will it be in 8 hours and 10 minutes?",
        )

    def test_create_agent_excludes_try_direct_first_and_loads_task_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            learned_dir = root / "learned"
            work_dir = root / "artifacts"

            self._write_skill(
                skills_dir,
                "reasoning",
                "---\nname: reasoning\ndescription: neutral\nlevel: foundation\ndepends_on: []\n---\n\n# Reasoning\n",
            )
            self._write_skill(
                skills_dir,
                "try_direct_first",
                "---\nname: try_direct_first\ndescription: direct\nlevel: foundation\ndepends_on: []\n---\n\n# Try Direct First\nAlways attempt direct solve.\n",
            )

            loop = EvolutionLoop(
                work_dir=work_dir,
                learned_dir=learned_dir,
                skills_dir=skills_dir,
                vlm_client=DummyVLMClient(),
                max_attempts=1,
            )
            loop.store.promote_skill(
                "mirror_clock",
                SkillProposal(
                    name="mirror_clock",
                    description="Mirror rule",
                    applicability_conditions="Use when the clock is mirrored.",
                    content="## Do this first\n- Use the mirror restore tool.",
                    level="mid",
                    depends_on=["reasoning"],
                ),
            )
            (learned_dir / "tools").mkdir(parents=True, exist_ok=True)
            (learned_dir / "tools" / "mirror_restore.py").write_text(
                "from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/restored.png'])\n",
                encoding="utf-8",
            )
            loop.store.save_failure_skill(
                "mirror_clock",
                "18",
                SkillProposal(
                    name="mirror_clock",
                    description="Failure lesson",
                    applicability_conditions="Use when the corrected image may still need an orientation check.",
                    content="## SOP\n1. Verify whether the corrected image still needs an extra orientation step.",
                    level="low",
                    depends_on=[],
                ),
            )

            from core.types import TaskCase

            agent = loop._create_agent(
                TaskCase(
                    case_id="1",
                    problem_id="mirror_clock",
                    prompt="What time?",
                    gold_answer="3:20",
                )
            )

            self.assertNotIn("Try Direct First", agent.system_prompt)
            self.assertNotIn("## Available Skills", agent.system_prompt)
            self.assertIn("## Current Task SOP", agent.system_prompt)
            self.assertIn("Do not output `ACTION: TASK_COMPLETE` before you have executed the required SOP steps and produced a final answer.", agent.system_prompt)
            self.assertIn("Final Answer: <your answer>", agent.system_prompt)
            self.assertNotIn("## General Guidance", agent.system_prompt)
            self.assertIn("Use the mirror restore tool.", agent.system_prompt)
            self.assertIn("## Failure Lessons / Things To Watch", agent.system_prompt)
            self.assertIn("Verify whether the corrected image still needs an extra orientation step.", agent.system_prompt)

    def test_render_skills_renders_failure_lessons_as_separate_section(self):
        from skills.base import Skill
        from skills import render_skills

        rendered = render_skills(
            [
                Skill(
                    name="billiards",
                    description="Main SOP",
                    content="## SOP\n1. Run the solver.",
                    applicability_conditions="When the table and arrow are visible.",
                ),
                Skill(
                    name="billiards_case_2_failure_lesson",
                    description="Watch arrow direction ambiguity",
                    content="## SOP\n1. Re-check the initial direction before trusting the final pocket.",
                    applicability_conditions="When the arrow body and head can be confused.",
                    kind="failure_lesson",
                    level="low",
                ),
            ]
        )
        self.assertIn("## Current Task SOP", rendered)
        self.assertIn("## Failure Lessons / Things To Watch", rendered)
        self.assertIn("Watch arrow direction ambiguity", rendered)
        self.assertIn("Re-check the initial direction", rendered)

    def test_render_skills_expands_only_explicit_references(self):
        from skills import load_skill, render_skills

        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "chartqa"
            refs_dir = skill_dir / "references"
            refs_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                textwrap.dedent(
                    """
                    ---
                    name: chartqa
                    description: "Router"
                    level: mid
                    depends_on: []
                    ---

                    ## Router
                    1. See reference: references/tool_branch.md
                    2. Ignore unrelated branches.
                    """
                ).strip(),
                encoding="utf-8",
            )
            (refs_dir / "tool_branch.md").write_text("## SOP\n1. Use chart overlay.", encoding="utf-8")
            (refs_dir / "unused_branch.md").write_text("## SOP\n1. This should not be rendered.", encoding="utf-8")

            skill = load_skill(skill_dir / "SKILL.md")
            rendered = render_skills([skill])

            self.assertEqual([path.name for path in skill.references], ["tool_branch.md"])
            self.assertIn("Branch Detail", rendered)
            self.assertIn("Use chart overlay.", rendered)
            self.assertNotIn("This should not be rendered.", rendered)

    def test_store_writes_skill_package_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            learned_dir = Path(tmp) / "learned"
            store = CapabilityStore(learned_dir)
            proposal = SkillProposal(
                name="chartqa",
                description="Router skill",
                applicability_conditions="Use on labeled chart questions.",
                content="## Router\n1. See reference: references/tool_branch.md",
                level="mid",
                depends_on=[],
                references=[
                    SkillReferenceProposal(
                        path="references/tool_branch.md",
                        description="Primary branch",
                        content="## SOP\n1. Use `chart_value_overlay` first.",
                    )
                ],
            )

            store.promote_skill("chartqa", proposal)

            reference_file = learned_dir / "skills" / "chartqa" / "references" / "tool_branch.md"
            self.assertTrue(reference_file.exists())
            loaded = store.get_skill("chartqa")
            self.assertEqual([path.name for path in loaded.references], ["tool_branch.md"])

    def test_distill_mastery_skill_falls_back_to_skill_package(self):
        client = SkillGeneratorClient(
            '{"name":"chartqa","description":"router","applicability_conditions":"when chart labels are visible","content":"## SOP\\n1. Be careful.","level":"mid","depends_on":[]}'
        )
        generator = Generator(client)
        case = TaskCase(
            case_id="1",
            problem_id="chartqa",
            prompt="What value is shown for 2019?",
            gold_answer="7",
            metadata={"dataset_name": "chartqa", "capability_family": "chartqa"},
        )
        analysis = FailureAnalysis(root_cause="needs tool routing", next_action="generate_skill", confidence=0.9)
        profile = MasteryProfile(
            capability_family="chartqa",
            primary_tool="chart_value_overlay",
            tool_sequence=["chart_value_overlay", "localized_text_zoom"],
            recommended_trigger_conditions=["single labeled value for one series/category"],
            negative_trigger_conditions=["needs combining multiple chart elements"],
            common_success_signals=["visible value annotations"],
            common_failure_signals=["annotation unreadable or absent"],
        )

        proposal = generator.distill_mastery_skill(case, analysis, profile)

        self.assertIn("references/tool_branch.md", proposal.content)
        self.assertGreaterEqual(len(proposal.references), 2)
        self.assertEqual(proposal.references[0].path, "references/tool_branch.md")

    def test_create_agent_skips_untrusted_learned_tools_with_hardcoded_answers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            learned_dir = root / "learned"
            work_dir = root / "artifacts"

            self._write_skill(
                skills_dir,
                "reasoning",
                "---\nname: reasoning\ndescription: neutral\nlevel: foundation\ndepends_on: []\n---\n\n# Reasoning\n",
            )

            loop = EvolutionLoop(
                work_dir=work_dir,
                learned_dir=learned_dir,
                skills_dir=skills_dir,
                vlm_client=DummyVLMClient(),
                max_attempts=1,
            )
            (learned_dir / "tools").mkdir(parents=True, exist_ok=True)
            (learned_dir / "tools" / "leaky_tool.py").write_text(
                "from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='2', artifacts=['artifacts/out.png'])\n",
                encoding="utf-8",
            )
            (learned_dir / "tools" / "leaky_tool.json").write_text(
                '{"name": "leaky_tool", "description": "bad", "usage_example": "python -m tools leaky_tool <image_path>"}',
                encoding="utf-8",
            )

            from core.types import TaskCase

            agent = loop._create_agent(
                TaskCase(
                    case_id="2",
                    problem_id="billiards",
                    prompt="Which pocket?",
                    gold_answer="2",
                )
            )

            self.assertNotIn("leaky_tool", agent.system_prompt)

    def test_run_single_case_retries_immediately_and_persists_skill_and_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            learned_dir = root / "learned"
            work_dir = root / "artifacts"

            self._write_skill(
                skills_dir,
                "reasoning",
                "---\nname: reasoning\ndescription: neutral\nlevel: foundation\ndepends_on: []\n---\n\n# Reasoning\nStay structured.\n",
            )
            self._write_skill(
                skills_dir,
                "vision_analysis",
                "---\nname: vision_analysis\ndescription: vision\nlevel: foundation\ndepends_on: []\n---\n\n# Vision Analysis\nInspect images first.\n",
            )

            loop = MinimalLoop(work_dir=work_dir, learned_dir=learned_dir, skills_dir=skills_dir)
            loop.analyzer_decider = StubAnalyzer()
            loop.generator = StubGenerator()
            loop.validator = StubValidator(loop.store)

            from core.types import TaskCase

            case = TaskCase(
                case_id="1",
                problem_id="mirror_clock",
                prompt="Mirror clock question",
                gold_answer="3:20",
                image_path="datasets/mira/images/2.png",
            )

            solved = loop.run_single_case(case)

            self.assertTrue(solved)
            self.assertTrue(loop.store.has_skill("mirror_clock"))
            self.assertTrue((loop.store.tools_dir / "mirror_restore.py").exists())
            self.assertTrue((loop.store.tools_dir / "mirror_restore.json").exists())
            manifest = (loop.store.tools_dir / "mirror_restore.json").read_text(encoding="utf-8")
            self.assertIn("applicability_conditions", manifest)
            self.assertEqual(loop.created_agent_skills[0], None)
            self.assertIn("Run `python -m tools mirror_restore <image_path>`.", loop.created_agent_skills[1])

    def test_execute_learned_tool_returns_main_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_path = Path(tmp) / "echo_tool.py"
            tool_path.write_text(
                textwrap.dedent(
                    """
                    from core.types import ToolResult

                    def main():
                        print(ToolResult(status="ok", answer="done", artifacts=["artifacts/out.png"]))
                    """
                ).strip(),
                encoding="utf-8",
            )

            output = execute_learned_tool(tool_path, ["dummy.png"])

            self.assertIn("ANSWER: done", output)
            self.assertIn("ARTIFACTS: artifacts/out.png", output)

    def test_tool_result_omits_empty_answer_line(self):
        rendered = str(ToolResult(status="ok", answer="", artifacts=["artifacts/out.png"]))
        self.assertNotIn("ANSWER:", rendered)
        self.assertIn("STATUS: ok", rendered)
        self.assertIn("ARTIFACTS: artifacts/out.png", rendered)

    def test_execute_learned_tool_supports_top_level_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            tool_path = Path(tmp) / "run_tool.py"
            tool_path.write_text(
                textwrap.dedent(
                    """
                    from core.types import ToolResult

                    def run(image_path: str) -> ToolResult:
                        return ToolResult(
                            status="ok",
                            answer=f"processed {image_path}",
                            artifacts=["artifacts/run_tool_output.png"],
                        )
                    """
                ).strip(),
                encoding="utf-8",
            )

            output = execute_learned_tool(tool_path, ["dummy.png"])

            self.assertIn("ANSWER: processed dummy.png", output)
            self.assertIn("ARTIFACTS: artifacts/run_tool_output.png", output)

    def test_execute_learned_tool_infers_artifacts_from_written_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_path = root / "infer_tool.py"
            tool_path.write_text(
                textwrap.dedent(
                    """
                    from pathlib import Path

                    def main():
                        out = Path("artifacts") / "inferred.png"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text("ok", encoding="utf-8")
                        print("ANSWER: restored")
                        print("STATUS: ok")
                    """
                ).strip(),
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            try:
                import os
                os.chdir(root)
                output = execute_learned_tool(tool_path, ["dummy.png"])
            finally:
                os.chdir(old_cwd)

            self.assertIn("STATUS: ok", output)
            self.assertIn("ARTIFACTS: artifacts/inferred.png", output)

    def test_execute_learned_tool_rewrites_reported_artifacts_to_unique_run_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool_path = root / "unique_tool.py"
            tool_path.write_text(
                textwrap.dedent(
                    """
                    from core.types import ToolResult
                    import os
                    from pathlib import Path

                    def run(image_path: str) -> ToolResult:
                        out = Path(os.environ["VISION_AGENT_WORK_DIR"]) / "fixed_name.png"
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text("ok", encoding="utf-8")
                        return ToolResult(status="ok", answer="done", artifacts=["artifacts/fixed_name.png"])
                    """
                ).strip(),
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            old_env = os.environ.copy()
            try:
                os.chdir(root)
                scoped = root / "artifacts" / "case_18" / "attempt_2" / "retry"
                os.environ["VISION_AGENT_WORK_DIR"] = str(scoped)
                output = execute_learned_tool(tool_path, ["dummy.png"])
            finally:
                os.chdir(old_cwd)
                os.environ.clear()
                os.environ.update(old_env)

            self.assertIn("ARTIFACTS: artifacts/case_18/attempt_2/retry/fixed_name.png", output)

    def test_generate_skill_with_tool_forces_exact_command_into_rule(self):
        client = SkillGeneratorClient(
            textwrap.dedent(
                """
                {
                  "name": "mirror_clock",
                  "description": "Use the learned mirror tool.",
                  "content": "## When this applies\\n- Mirrored clock, then add 8 hours and 10 minutes.\\n\\n## Do this first\\n- Run `python -m tools flip_image_horizontal datasets/mira/images/2.png`.\\n\\n## Then\\n- Read the clock and answer 3:20.\\n\\n## If still failing\\n- Check datasets/mira/images/2.png again.",
                  "level": "mid",
                  "depends_on": ["reasoning", "vision_analysis"]
                }
                """
            ).strip()
        )
        generator = Generator(client)
        analysis = FailureAnalysis(
            root_cause="Mirror transform missing",
            next_action="generate_both",
            confidence=0.9,
            missing_step="mirror correction",
            skill_update_note="Answer from the corrected image, not the original mirror.",
            rationale="Use the validated tool before answering.",
        )
        tool = ToolProposal(
            name="rotate_clock",
            description="Rotate the corrected clock image",
            applicability_conditions="Use after the first mirror-correction tool if the artifact is still upside down.",
            code="",
            usage_example="python -m tools rotate_clock <image_path>",
            expected_inputs=["image_path"],
            expected_outputs=["artifacts/rotate_clock_output.png"],
        )

        from core.types import TaskCase

        proposal = generator.generate_skill(
            TaskCase(
                case_id="1",
                problem_id="mirror_clock",
                prompt="What time?",
                gold_answer="3:20",
                image_path="datasets/mira/images/2.png",
            ),
            analysis,
            tool,
            existing_skill_content="## SOP\n1. Run `python -m tools flip_image_horizontal <image_path>`.\n2. Answer from the corrected image.",
        )

        self.assertEqual(proposal.name, "mirror_clock")
        self.assertTrue(proposal.applicability_conditions)
        self.assertIn("## SOP", proposal.content)
        self.assertIn("Run the existing tool chain in order: `python -m tools flip_image_horizontal <image_path>`", proposal.content)
        self.assertIn("`python -m tools rotate_clock <artifact_path>`", proposal.content)
        self.assertIn("Wait for the Observation again, then answer the original question using the final tool output instead of the raw image.", proposal.content)
        self.assertNotIn("datasets/mira/images/2.png", proposal.content)
        self.assertNotIn("8 hours and 10 minutes", proposal.content)
        self.assertNotIn("3:20", proposal.content)
        self.assertIsNotNone(client.last_messages)
        prompt = client.last_messages[1]["content"]
        self.assertIn("Existing task-family SOP:", prompt)
        self.assertIn("works for some examples", prompt)
        self.assertIn("preserves the previously useful behavior", prompt)
        self.assertIn("<artifact_path>", prompt)

    def test_generate_skill_prompt_includes_preset_tool_catalog(self):
        client = SkillGeneratorClient(
            textwrap.dedent(
                """
                {
                  "name": "mirror_clock",
                  "description": "Use preset tools when local evidence is hard to read.",
                  "applicability_conditions": "Use when small local visual evidence needs clarification.",
                  "content": "## SOP\\n1. If the evidence is a small text label, run `python -m tools localized_text_zoom <image_path>`.\\n2. Otherwise if the evidence is a small local region, run `python -m tools localized_region_zoom <image_path>`.\\n3. Wait for the Observation and inspect the artifact.\\n4. Answer the original question from the improved view.",
                  "level": "mid",
                  "depends_on": []
                }
                """
            ).strip()
        )
        generator = Generator(client)
        analysis = FailureAnalysis(
            root_cause="Small evidence is hard to inspect.",
            next_action="generate_skill",
            confidence=0.8,
            missing_step="Use a preset zoom tool before answering.",
            skill_update_note="Branch between text zoom and generic region zoom.",
            rationale="Preset tools should be orchestrated in the SOP.",
        )

        proposal = generator.generate_skill(
            __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="9",
                problem_id="mirror_clock",
                prompt="What year is written on the sign?",
                gold_answer="1998",
                image_path="datasets/mira/images/9.png",
            ),
            analysis,
            None,
        )

        self.assertEqual(proposal.name, "mirror_clock")
        prompt = client.last_messages[1]["content"]
        self.assertIn("Preset built-in tools are available for this rule:", prompt)
        self.assertIn("localized_text_zoom", prompt)
        self.assertIn("localized_region_zoom", prompt)
        self.assertIn("Do not invent any new tool names.", prompt)

    def test_builtin_tools_catalog_is_nonempty(self):
        tool_names = [tool.name for tool in list_builtin_tools()]
        self.assertIn("localized_text_zoom", tool_names)
        self.assertIn("localized_region_zoom", tool_names)
        self.assertIn("OCR", tool_names)
        self.assertIn("Calculator", tool_names)

    def test_execute_builtin_tool_writes_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            image = Image.new("RGB", (32, 32), color=(255, 255, 255))
            image.save(image_path)

            cwd = Path.cwd()
            try:
                os.chdir(root)
                output = execute_builtin_tool("localized_region_zoom", str(image_path))
            finally:
                os.chdir(cwd)

            self.assertIn("STATUS: ok", output)
            self.assertIn("ARTIFACTS:", output)
            artifact_path = root / "artifacts" / "localized_region_zoom_output.png"
            self.assertTrue(artifact_path.exists())

    def test_review_skill_receives_existing_sop_and_draft(self):
        client = SkillGeneratorClient(
            textwrap.dedent(
                """
                {
                  "name": "mirror_clock",
                  "description": "Reviewed SOP",
                  "applicability_conditions": "Use mirror_flip first; add rotate_clock only when the mirrored artifact is still upside down.",
                  "content": "## SOP\\n1. Confirm this applies: Use mirror_flip first; add rotate_clock only when the mirrored artifact is still upside down.\\n2. Run the existing tool chain in order: `python -m tools mirror_flip <image_path>`.\\n3. Wait for the Observation, then use the newest artifact as the input to `python -m tools rotate_clock <artifact_path>`.\\n4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image.",
                  "level": "mid",
                  "depends_on": []
                }
                """
            ).strip()
        )
        generator = Generator(client)
        analysis = FailureAnalysis(
            root_cause="A second step is needed on some examples.",
            next_action="generate_both",
            confidence=0.9,
            missing_step="add a rotation step only for upside-down artifacts",
            skill_update_note="Branch between mirror-only and mirror-then-rotate.",
            rationale="The family needs clearer conditions.",
        )
        draft = SkillProposal(
            name="mirror_clock",
            description="Draft SOP",
            applicability_conditions="Use on mirror_clock tasks.",
            content="## SOP\n1. Run `python -m tools mirror_flip <image_path>`.\n2. Run `python -m tools rotate_clock <artifact_path>`.\n3. Answer.\n4. Done.",
            level="mid",
            depends_on=[],
        )
        reviewed = generator.review_skill(
            __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="18",
                problem_id="mirror_clock",
                prompt="What time will it be later?",
                gold_answer="1:40",
                image_path="datasets/mira/images/18.png",
            ),
            analysis,
            draft,
            ToolProposal(
                name="rotate_clock",
                description="Rotate the artifact 180 degrees",
                applicability_conditions="Use after mirror_flip when the artifact is still upside down.",
                code="",
                usage_example="python -m tools rotate_clock <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/rotate_clock_output.png"],
            ),
            existing_skill_content="## SOP\n1. Run `python -m tools mirror_flip <image_path>`.\n2. Answer from the corrected image.",
            family_examples=[
                __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                    case_id="2",
                    problem_id="mirror_clock",
                    prompt="What time will it be in 8 hours and 10 minutes?",
                    gold_answer="3:20",
                    image_path="datasets/mira/images/2.png",
                    metadata={"dense_caption": "This is a mirrored analog clock."},
                ),
                __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                    case_id="18",
                    problem_id="mirror_clock",
                    prompt="What time will it be in 9 hours and 35 minutes?",
                    gold_answer="1:40",
                    image_path="datasets/mira/images/18.png",
                    metadata={"dense_caption": "This is a mirrored analog clock that is also upside down."},
                ),
            ],
        )

        self.assertTrue(reviewed.applicability_conditions)
        self.assertIsNotNone(client.last_messages)
        prompt = client.last_messages[1]["content"]
        self.assertIn("Existing task-family SOP", prompt)
        self.assertIn("Draft SOP to review", prompt)
        self.assertIn("should branch", prompt)
        self.assertIn("Task-family examples seen so far", prompt)
        self.assertIn("1. case_id=2; dense_caption=This is a mirrored analog clock.", prompt)
        self.assertIn("2. case_id=18; dense_caption=This is a mirrored analog clock that is also upside down.", prompt)

    def test_validator_chains_new_tool_from_latest_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned_dir = root / "learned"
            tools_dir = learned_dir / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            (tools_dir / "mirror_flip.py").write_text(
                "from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/mirror_flip_output.png'])\n",
                encoding="utf-8",
            )
            validator = Validator(root, learned_dir)
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="18",
                problem_id="mirror_clock",
                prompt="What time?",
                gold_answer="1:40",
                image_path="datasets/mira/images/18.png",
            )
            existing_skill = "## SOP\n1. Run `python -m tools mirror_flip <image_path>`.\n2. Answer from the corrected image."
            prior_artifact = root / "mirror_flip_output.png"
            prior_artifact.write_text("prior", encoding="utf-8")
            new_artifact = root / "rotate_output.png"
            new_artifact.write_text("new", encoding="utf-8")
            proposal = ToolProposal(
                name="rotate_clock",
                description="Rotate the corrected clock",
                applicability_conditions="Use after mirror_flip when the corrected artifact is still upside down.",
                code="from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/rotate_output.png'])\n",
                usage_example="python -m tools rotate_clock <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/rotate_output.png"],
            )

            def fake_run(command, cwd, capture_output, text, timeout, env=None):
                input_path = command[-1]
                if command[3] == "mirror_flip":
                    self.assertEqual(input_path, "datasets/mira/images/18.png")
                    return mock.Mock(
                        stdout=f"ANSWER: ok\nSTATUS: ok\nARTIFACTS: {prior_artifact}\n",
                        stderr="",
                        returncode=0,
                    )
                self.assertEqual(command[3], "rotate_clock")
                self.assertEqual(input_path, str(prior_artifact))
                return mock.Mock(
                    stdout=f"ANSWER: ok\nSTATUS: ok\nARTIFACTS: {new_artifact}\n",
                    stderr="",
                    returncode=0,
                )

            with mock.patch("evolution.validator.subprocess.run", side_effect=fake_run):
                chain_context = validator.build_chain_context(case, existing_skill)
                result = validator.validate_tool(
                    proposal,
                    origin_case=case,
                    agent_factory=lambda: FakeAgent(""),
                    regression_cases=None,
                    chain_context=chain_context,
                )

            self.assertTrue(result.passed)
            self.assertEqual(result.input_image, str(prior_artifact))
            self.assertEqual(result.chain_trace, ["mirror_flip"])

    def test_agent_run_includes_initial_chain_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "chain.png"
            artifact.write_bytes(b"png")

            class CaptureClient:
                def __init__(self):
                    self.messages = None

                def chat(self, messages, settings=None):
                    self.messages = messages
                    return "Final Answer: ok\nACTION: TASK_COMPLETE", DummyUsage()

            client = CaptureClient()
            agent = ReActAgent(client)
            agent.run(
                "What time?",
                "",
                initial_observations=[("ANSWER: prior\nSTATUS: ok\nARTIFACTS: " + str(artifact), [str(artifact)])],
            )

            self.assertIsNotNone(client.messages)
            self.assertGreaterEqual(len(client.messages), 3)
            user_messages = [message for message in client.messages if message["role"] == "user"]
            self.assertGreaterEqual(len(user_messages), 2)
            self.assertIsInstance(user_messages[-1]["content"], list)

    def test_analyzer_logs_prompt_and_raw_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "analyzer_logs"
            analyzer = AnalyzerDecider(
                AnalyzerClient(
                    textwrap.dedent(
                        """
                        {
                          "root_cause": "existing tool still insufficient",
                          "missing_step": "an additional normalization step",
                          "next_action": "generate_both",
                          "tool_goal": "normalize the intermediate image further",
                          "skill_update_note": "use the second tool after the first one when needed",
                          "confidence": 0.9,
                          "rationale": "a second tool is needed"
                        }
                        """
                    ).strip()
                ),
                log_dir,
            )

            from core.types import TaskCase

            result = AgentResult(
                task="What time?",
                final_answer="wrong",
                steps=[],
                total_turns=1,
                success=True,
                all_artifacts=["artifacts/flipped.png"],
            )
            case = TaskCase(
                case_id="18",
                problem_id="mirror_clock",
                prompt="This is what a clock looks like in a mirror. What time will it be in 9 hours and 35 minutes?",
                gold_answer="1:40",
                image_path="datasets/mira/images/18.png",
            )

            analysis = analyzer.analyze_and_decide(
                case=case,
                result=result,
                current_capabilities=["tool:mirror_flip", "skill:mirror_clock"],
                previous_attempts=["Attempt 1: initial answer='4:45'; analyzer chose generate_skill"],
                attempt=2,
                extra_artifacts=["artifacts/validator_flip.png"],
                capability_snapshot="Available tools:\n- tool:mirror_flip\nIgnored tools:\n- tool:broken_tool (missing source file)",
            )

            self.assertEqual(analysis.next_action, "generate_both")
            log_file = log_dir / "case_18_attempt_2.json"
            self.assertTrue(log_file.exists())
            payload = log_file.read_text(encoding="utf-8")
            self.assertIn("Current Capabilities", payload)
            self.assertIn("capability_snapshot", payload)
            self.assertIn("broken_tool", payload)
            self.assertIn("generate_both", payload)
            self.assertIn("datasets/mira/images/18.png", payload)
            self.assertIn("artifacts/flipped.png", payload)
            self.assertIn("artifacts/validator_flip.png", payload)

    def test_generate_tool_receives_dense_caption_and_original_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            image_path.write_bytes(
                bytes.fromhex(
                    "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000C49444154789C63606060000000040001F61738550000000049454E44AE426082"
                )
            )

            client = SkillGeneratorClient(
                textwrap.dedent(
                    """
                    {
                      "name": "sample_tool",
                      "description": "desc",
                      "applicability_conditions": "when needed",
                      "code": "from core.types import ToolResult\\nfrom tools.implementations.shared import load_image, save_image\\n\\ndef run(image_path: str) -> ToolResult:\\n    return ToolResult(status='ok', answer='ok', artifacts=['artifacts/out.png'])",
                      "usage_example": "python -m tools sample_tool <image_path>",
                      "expected_inputs": ["image_path"],
                      "expected_outputs": ["artifacts/out.png"]
                    }
                    """
                ).strip()
            )
            generator = Generator(client)
            analysis = FailureAnalysis(
                root_cause="Need a tool",
                next_action="generate_tool",
                confidence=0.9,
                missing_step="extract the path",
                tool_goal="process the image",
                rationale="image inspection is needed",
            )

            from core.types import TaskCase

            generator.generate_tool(
                TaskCase(
                    case_id="2",
                    problem_id="billiards",
                    prompt="Which pocket?",
                    gold_answer="2",
                    image_path=str(image_path),
                    metadata={"dense_caption": "Unique muted green arrow."},
                ),
                analysis,
            )

            self.assertIsNotNone(client.last_messages)
            self.assertEqual(client.last_messages[0]["role"], "system")
            user_content = client.last_messages[1]["content"]
            self.assertIsInstance(user_content, list)
            text_part = next(part for part in user_content if part["type"] == "text")
            self.assertIn("Dense Caption: Unique muted green arrow.", text_part["text"])
            self.assertIn("the code must include real detection/extraction steps that use those cues", text_part["text"])
            self.assertIn("Do not skip those cues by hardcoding image-specific coordinates", text_part["text"])
            self.assertIn("Scaffold Code Template:", text_part["text"])
            self.assertIn("def run(image_path: str) -> ToolResult", text_part["text"])
            self.assertNotIn("Expected Answer:", text_part["text"])
            self.assertIn("Do not output the task's final answer from the tool itself.", text_part["text"])
            self.assertTrue(any(part["type"] == "image_url" for part in user_content))

    def test_validator_rejects_tool_code_that_hardcodes_gold_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validator = Validator(root, root / "learned")
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="2",
                problem_id="billiards",
                prompt="Which pocket?",
                gold_answer="2",
                image_path="datasets/mira/billiards/images/2.png",
            )
            proposal = ToolProposal(
                name="leaky_tool",
                description="Leaks the answer",
                applicability_conditions="never",
                code="from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='2', artifacts=['artifacts/out.png'])\n",
                usage_example="python -m tools leaky_tool <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/out.png"],
            )

            result = validator.validate_tool(
                proposal,
                origin_case=case,
                agent_factory=lambda: FakeAgent(""),
                regression_cases=None,
            )

            self.assertFalse(result.passed)
            self.assertTrue(result.leakage_detected)
            self.assertIn("hardcodes the current case answer", result.reason)

    def test_validator_rejects_runtime_output_that_leaks_gold_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned_dir = root / "learned"
            validator = Validator(root, learned_dir)
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="2",
                problem_id="billiards",
                prompt="Which pocket?",
                gold_answer="2",
                image_path="datasets/mira/billiards/images/2.png",
            )
            proposal = ToolProposal(
                name="runtime_leak",
                description="Leaks at runtime",
                applicability_conditions="never",
                code="from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/out.png'])\n",
                usage_example="python -m tools runtime_leak <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/out.png"],
            )

            artifact = root / "artifacts" / "out.png"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text("ok", encoding="utf-8")

            with mock.patch(
                "evolution.validator.subprocess.run",
                return_value=mock.Mock(
                    stdout="ANSWER: 2\nSTATUS: ok\nARTIFACTS: artifacts/out.png\n",
                    stderr="",
                    returncode=0,
                ),
            ):
                result = validator.validate_tool(
                    proposal,
                    origin_case=case,
                    agent_factory=lambda: FakeAgent(""),
                    regression_cases=None,
                )

            self.assertFalse(result.passed)
            self.assertTrue(result.leakage_detected)
            self.assertIn("runtime output leaked", result.reason)
            self.assertEqual(result.failure_type, "answer_leakage")
            self.assertIsNotNone(result.revision_brief)

    def test_validator_restores_existing_tool_after_failed_same_name_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned_dir = root / "learned"
            tools_dir = learned_dir / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            validator = Validator(root, learned_dir)
            original_code = "from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/original.png'])\n"
            (tools_dir / "shared_tool.py").write_text(original_code, encoding="utf-8")
            (tools_dir / "shared_tool.json").write_text('{"name":"shared_tool"}', encoding="utf-8")
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="2",
                problem_id="billiards",
                prompt="Which pocket?",
                gold_answer="2",
                image_path="datasets/mira/billiards/images/2.png",
            )
            proposal = ToolProposal(
                name="shared_tool",
                description="Broken replacement",
                applicability_conditions="never",
                code="from core.types import ToolResult\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/out.png'])\n",
                usage_example="python -m tools shared_tool <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/out.png"],
            )

            with mock.patch(
                "evolution.validator.subprocess.run",
                return_value=mock.Mock(stdout="STATUS: error\n", stderr="", returncode=0),
            ):
                result = validator.validate_tool(
                    proposal,
                    origin_case=case,
                    agent_factory=lambda: FakeAgent(""),
                    regression_cases=None,
                )

            self.assertFalse(result.passed)
            self.assertTrue(result.replaced_existing_tool)
            self.assertEqual((tools_dir / "shared_tool.py").read_text(encoding="utf-8"), original_code)

    def test_validator_rejects_case_specific_tool_with_revision_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            validator = Validator(root, root / "learned")
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="case_100",
                problem_id="vstar",
                prompt="Which side?",
                gold_answer="A",
                image_path="datasets/vstar/example_100.png",
            )
            proposal = ToolProposal(
                name="left_right_relation_checker",
                description="Case specific relation checker",
                applicability_conditions="Use on this exact image",
                code="from core.types import ToolResult\nX=100\nY=120\nZ=140\nW=160\nQ=180\nR=200\nS=220\nT=240\nU=260\nV=280\nA=300\nB=320\n\ndef run(image_path: str) -> ToolResult:\n    return ToolResult(status='ok', answer='', artifacts=['artifacts/out.png'])\n",
                usage_example="python -m tools left_right_relation_checker <image_path>",
                expected_inputs=["image_path"],
                expected_outputs=["artifacts/out.png"],
            )

            result = validator.validate_tool(
                proposal,
                origin_case=case,
                agent_factory=lambda: FakeAgent(""),
                regression_cases=None,
            )

            self.assertFalse(result.passed)
            self.assertEqual(result.failure_type, "case_specific_logic")
            self.assertIsNotNone(result.revision_brief)
            self.assertEqual(result.revision_brief.retry_action, "revise_tool")

    def test_build_chain_context_fails_closed_for_manifest_only_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            learned_dir = root / "learned"
            tools_dir = learned_dir / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            (tools_dir / "ghost_tool.json").write_text('{"name":"ghost_tool"}', encoding="utf-8")
            validator = Validator(root, learned_dir)
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="11",
                problem_id="billiards",
                prompt="Which pocket?",
                gold_answer="3",
                image_path="datasets/mira/billiards/images/11.png",
            )

            context = validator.build_chain_context(case, "## SOP\n1. Run `python -m tools ghost_tool <image_path>`.", attempt=1)

            self.assertTrue(context.failed)
            self.assertIn("manifest exists but source file is missing", context.reason)

    def test_create_agent_skips_task_skill_when_referenced_tool_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills_dir = root / "skills"
            learned_dir = root / "learned"
            work_dir = root / "artifacts"

            self._write_skill(
                skills_dir,
                "reasoning",
                "---\nname: reasoning\ndescription: neutral\nlevel: foundation\ndepends_on: []\n---\n\n# Reasoning\n",
            )
            loop = EvolutionLoop(
                work_dir=work_dir,
                learned_dir=learned_dir,
                skills_dir=skills_dir,
                vlm_client=DummyVLMClient(),
                max_attempts=1,
            )
            loop.store.promote_skill(
                "billiards",
                SkillProposal(
                    name="billiards",
                    description="Path tracer rule",
                    applicability_conditions="Use for billiards trajectory tasks.",
                    content="## SOP\n1. Run `python -m tools ghost_tool <image_path>`.\n2. Wait for the Observation.",
                    level="mid",
                    depends_on=[],
                ),
            )

            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="11",
                problem_id="billiards",
                prompt="Which pocket?",
                gold_answer="3",
            )
            agent = loop._create_agent(case)

            self.assertNotIn("ghost_tool", agent.system_prompt)
            self.assertIn("localized_text_zoom", agent.system_prompt)

    def test_required_tool_blocks_premature_task_complete(self):
        client = ScriptedClient([
            "ACTION: TASK_COMPLETE",
            textwrap.dedent(
                """
                Action:
                {
                  "name": "bash",
                  "arguments": {"command": "python -m tools flip_image_horizontal datasets/mira/images/2.png"}
                }
                """
            ).strip(),
            "Final Answer: solved\nACTION: TASK_COMPLETE",
        ])
        agent = FakeReActAgent(
            client=client,
            config=AgentConfig(max_turns=3, required_tool_name="flip_image_horizontal"),
            tool_definitions="Use: python -m tools <tool_name> [args]",
            extra_instructions="## Current Task Rule\nRun the validated tool first.",
        )

        result = agent.run("What time?", "")

        self.assertEqual(result.final_answer, "solved")
        self.assertGreaterEqual(len(result.steps), 3)
        self.assertTrue(any(step.action for step in result.steps))
        self.assertIn("Completion is missing a final answer", result.steps[0].observation or "")

    def test_required_skill_blocks_premature_task_complete_until_bash_step_runs(self):
        client = ScriptedClient([
            "Final Answer: shortcut\nACTION: TASK_COMPLETE",
            textwrap.dedent(
                """
                Action:
                {
                  "name": "bash",
                  "arguments": {"command": "python scratch_edit.py"}
                }
                """
            ).strip(),
            "Final Answer: solved\nACTION: TASK_COMPLETE",
        ])
        agent = FakeReActAgent(
            client=client,
            config=AgentConfig(
                max_turns=3,
                required_skill_name="chartqa_visual_edit",
                require_bash_action_before_complete=True,
            ),
            tool_definitions="Use: python -m tools <tool_name> [args]",
            extra_instructions="## Current Task SOP\n1. Run a visual editing bash step before answering.",
        )

        result = agent.run("What value?", "")

        self.assertEqual(result.final_answer, "solved")
        self.assertGreaterEqual(len(result.steps), 3)
        self.assertIn("execute at least one bash step required by skill", result.steps[0].observation or "")

    def test_required_skill_can_also_require_image_artifact_before_complete(self):
        client = ScriptedClient([
            textwrap.dedent(
                """
                Action:
                {
                  "name": "bash",
                  "arguments": {"command": "python scratch_edit.py"}
                }
                """
            ).strip(),
            "Final Answer: shortcut\nACTION: TASK_COMPLETE",
        ])
        agent = FakeReActAgent(
            client=client,
            config=AgentConfig(
                max_turns=2,
                required_skill_name="chartqa_visual_edit",
                require_bash_action_before_complete=True,
                required_image_artifact_before_complete=True,
            ),
            tool_definitions="Use: python -m tools <tool_name> [args]",
            extra_instructions="## Current Task SOP\n1. Run a visual editing bash step before answering.",
        )

        result = agent.run("What value?", "")

        self.assertEqual(result.final_answer, "shortcut")
        self.assertTrue(any(step.artifacts for step in result.steps))

    def test_missing_image_artifact_blocks_completion_in_forced_scratch_mode(self):
        client = ScriptedClient([
            textwrap.dedent(
                """
                Action:
                {
                  "name": "bash",
                  "arguments": {"command": "python scratch_edit.py"}
                }
                """
            ).strip(),
            "Final Answer: shortcut\nACTION: TASK_COMPLETE",
            "Final Answer: still shortcut\nACTION: TASK_COMPLETE",
        ])
        agent = FakeNoArtifactReActAgent(
            client=client,
            config=AgentConfig(
                max_turns=3,
                required_skill_name="chartqa_visual_edit",
                require_bash_action_before_complete=True,
                required_image_artifact_before_complete=True,
            ),
            tool_definitions="Use: python -m tools <tool_name> [args]",
            extra_instructions="## Current Task SOP\n1. Produce an edited artifact before answering.",
        )

        result = agent.run("What value?", "")

        self.assertFalse(result.success)
        self.assertIn("must produce a new image artifact", result.steps[-1].observation or "")

    def test_parser_prefers_action_over_task_complete_when_both_present(self):
        parser = ReActParser()
        response = textwrap.dedent(
            """
            Thought: I can do this.
            Action:
            {
              "name": "bash",
              "arguments": {"command": "python -m tools flip_image datasets/mira/images/2.png"}
            }

            ACTION: TASK_COMPLETE
            """
        ).strip()

        parsed = parser.parse_response(response)

        self.assertFalse(parsed.is_task_complete)
        self.assertIsNotNone(parsed.action)
        self.assertEqual(parsed.action.name, "bash")
        self.assertEqual(
            parsed.action.arguments["command"],
            "python -m tools flip_image datasets/mira/images/2.png",
        )

    def test_parser_rejects_task_complete_without_final_answer(self):
        parser = ReActParser()

        parsed = parser.parse_response("ACTION: TASK_COMPLETE")

        self.assertTrue(parsed.is_format_error)
        self.assertIn("Completion is missing a final answer", parsed.error_message or "")

    def test_run_bash_rewrites_python_tools_to_current_interpreter(self):
        agent = ReActAgent(DummyVLMClient())

        with mock.patch("core.agent.subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(stdout="STATUS: ok\n", stderr="", returncode=0)

            output = agent._run_bash("python -m tools flip_image datasets/mira/images/2.png")

        self.assertIn("STATUS: ok", output)
        invoked_command = run_mock.call_args.args[0]
        self.assertTrue(invoked_command.startswith(f"{sys.executable} -m tools flip_image"))
        self.assertFalse(invoked_command.startswith("python -m tools"))

    def test_run_bash_rewrites_python3_tools_to_current_interpreter(self):
        agent = ReActAgent(DummyVLMClient())

        with mock.patch("core.agent.subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(stdout="STATUS: ok\n", stderr="", returncode=0)

            output = agent._run_bash("python3 -m tools flip_image datasets/mira/images/2.png")

        self.assertIn("STATUS: ok", output)
        invoked_command = run_mock.call_args.args[0]
        self.assertTrue(invoked_command.startswith(f"{sys.executable} -m tools flip_image"))
        self.assertFalse(invoked_command.startswith("python3 -m tools"))

    def test_run_bash_rewrites_input_file_alias_to_current_image_path(self):
        agent = ReActAgent(DummyVLMClient())
        agent._current_image_path = "datasets/mira/billiards/images/2.png"

        with mock.patch("core.agent.subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(stdout="STATUS: ok\n", stderr="", returncode=0)

            agent._run_bash("python -m tools billiards_reflection_solver input_file_0.png")

        invoked_command = run_mock.call_args.args[0]
        self.assertIn("datasets/mira/billiards/images/2.png", invoked_command)
        self.assertNotIn("input_file_0.png", invoked_command)

    def test_run_bash_scopes_tool_lookup_to_agent_learned_dir(self):
        learned_dir = Path("/tmp/fake_learned_dir")
        agent = ReActAgent(DummyVLMClient(), config=AgentConfig(learned_dir=learned_dir))

        with mock.patch("core.agent.subprocess.run") as run_mock:
            run_mock.return_value = mock.Mock(stdout="STATUS: ok\n", stderr="", returncode=0)
            agent._run_bash("python -m tools flip_image datasets/mira/images/2.png")

        env = run_mock.call_args.kwargs["env"]
        self.assertEqual(env["VISION_AGENT_LEARNED_DIR"], str(learned_dir))

    def test_agent_work_dir_includes_problem_id_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop = EvolutionLoop(
                work_dir=root / "artifacts",
                learned_dir=root / "learned",
                skills_dir=root / "skills",
                vlm_client=DummyVLMClient(),
                max_attempts=1,
            )
            case = __import__("core.types", fromlist=["TaskCase"]).TaskCase(
                case_id="18",
                problem_id="billiards",
                prompt="Pocket?",
                gold_answer="3",
            )

            path = loop._agent_work_dir(case, 2, "retry")

            self.assertEqual(
                path,
                root / "artifacts" / "problem_billiards" / "case_18" / "attempt_2" / "retry",
            )

    def test_tools_main_respects_scoped_learned_dir(self):
        import tools.__main__ as tools_main

        with tempfile.TemporaryDirectory() as tmp:
            scoped_dir = Path(tmp) / "subset"
            tools_dir = scoped_dir / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            (tools_dir / "scoped_tool.py").write_text("pass", encoding="utf-8")

            with mock.patch.dict(os.environ, {"VISION_AGENT_LEARNED_DIR": str(scoped_dir)}, clear=False):
                with mock.patch("tools.__main__.execute_learned_tool", return_value="STATUS: ok") as exec_mock:
                    with mock.patch.object(sys, "argv", ["python", "scoped_tool", "arg.png"]):
                        tools_main.main()

            exec_mock.assert_called_once()
            tool_path = exec_mock.call_args.args[0]
            self.assertEqual(tool_path, tools_dir / "scoped_tool.py")


if __name__ == "__main__":
    unittest.main()
