"""Main evolution loop - focused on single case until solved."""

from __future__ import annotations
from datetime import datetime
import inspect
import json
from pathlib import Path
from typing import Callable

from core.types import TaskCase, AgentResult
from core.agent import ReActAgent, AgentConfig
from core.vlm_client import VLMClient, UsageStats
from skills import Skill, render_skills
from tools.builtin_tools import list_builtin_tools
from .types import EvolutionStep, FailedDirection, ToolChainContext, ToolAvailabilitySnapshot
from .roles import AnalyzerDecider, Generator
from .validator import Validator
from .store import CapabilityStore


class EvolutionLoop:
    """Self-evolution loop focused on single case."""

    def __init__(
        self,
        work_dir: Path,
        learned_dir: Path,
        skills_dir: Path,
        vlm_client: VLMClient,
        max_attempts: int = 10,
        subset_id: str | None = None,
        answer_checker: Callable[[str, TaskCase], bool] | None = None,
        capability_mode: str = "persistent_tools",
        fixed_builtin_tools: list[str] | None = None,
        disable_generated_tools: bool = False,
    ):
        self.work_dir = work_dir
        self.skills_dir = skills_dir
        self.vlm_client = vlm_client
        self.max_attempts = max_attempts
        self.subset_id = subset_id
        self.answer_checker = answer_checker
        self.capability_mode = capability_mode
        self.fixed_builtin_tools = list(fixed_builtin_tools or [])
        self.disable_generated_tools = disable_generated_tools

        # Subset-specific learned directory
        if subset_id:
            self.learned_dir = learned_dir / subset_id
            self.learned_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.learned_dir = learned_dir

        # Components
        self.analyzer_decider = AnalyzerDecider(vlm_client, self.learned_dir / "analyzer_logs")
        self.generator = Generator(vlm_client)
        self.validator = Validator(work_dir, self.learned_dir)
        self.store = CapabilityStore(self.learned_dir)
        self.family_examples: dict[str, list[TaskCase]] = {}
        self.last_case_report: dict | None = None

    def run_single_case(self, case: TaskCase) -> bool:
        """
        Focus on single case until solved or max attempts reached.

        Returns:
            True if solved, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Evolution Loop: {case.case_id}")
        if self.subset_id:
            print(f"Subset: {self.subset_id}")
            print(f"Learned Dir: {self.learned_dir}")
        print(f"Task: {case.prompt}")
        print(f"Capability Mode: {self.capability_mode}")
        print(f"{'='*60}\n")

        # Reset token counters
        self.analyzer_decider.total_usage = UsageStats()
        self.generator.total_usage = UsageStats()
        previous_attempts: list[str] = []
        carried_artifacts: list[str] = []
        duplicate_direction_streak = 0
        family_examples = self._family_examples_for_review(case)
        case_report = self._new_case_report(case)
        self.last_case_report = case_report

        for attempt in range(1, self.max_attempts + 1):
            print(f"\n--- Attempt {attempt}/{self.max_attempts} ---")
            existing_skill = self.store.get_skill(case.capability_family())
            capability_snapshot = self._tool_availability_snapshot()
            chain_context = self.validator.build_chain_context(
                case,
                self._usable_skill_content(existing_skill, capability_snapshot),
                attempt=attempt,
            )

            # Create agent with current capabilities
            agent = self._create_agent(case, attempt=attempt, phase="solve")

            # Try to solve
            print(f"Solving with current capabilities...")
            self._log_phase(case.case_id, attempt, "solve", "start")
            result = agent.run(
                case.prompt,
                case.image_path,
                initial_observations=self._chain_observations_for_agent(chain_context),
            )
            self._log_phase(case.case_id, attempt, "solve", "end")

            # Check if solved
            if self._check_success(result, case):
                print(f"✓ SOLVED! Answer: {result.final_answer}")
                self._print_token_summary(attempt)
                self._log_success(case, attempt)
                case_report["attempts"].append(
                    {
                        "attempt": attempt,
                        "initial_result": self._result_summary(result),
                        "initial_correct": True,
                        "chain_trace": list(chain_context.tool_sequence),
                    }
                )
                self._finalize_case_report(case_report, solved=True, final_result=result, attempts_used=attempt)
                return True

            print(f"✗ Failed. Answer: {result.final_answer} (expected: {case.gold_answer})")

            # Show artifacts info
            if result.all_artifacts:
                print(f"  Artifacts generated: {len(result.all_artifacts)}")
                for art in result.all_artifacts[:3]:  # Show first 3
                    print(f"    - {art}")
                if len(result.all_artifacts) > 3:
                    print(f"    ... and {len(result.all_artifacts) - 3} more")

            # Analyze failure and decide next action
            print(f"Analyzing failure with visual context...")
            if case.image_path:
                print(f"  → Original image: {case.image_path}")
            image_artifacts = result.get_image_artifacts()
            if image_artifacts:
                print(f"  → Processing {len(image_artifacts)} artifact images for analysis")
            recent_failed_directions = self.store.list_failed_directions(case.capability_family(), limit=8)
            if recent_failed_directions:
                print(f"  → Loaded {len(recent_failed_directions)} recent failed directions")
            self._log_phase(case.case_id, attempt, "analyzer", "start")
            analyze_kwargs = {
                "case": case,
                "result": result,
                "current_capabilities": capability_snapshot.capability_lines(),
                "previous_attempts": previous_attempts,
                "attempt": attempt,
                "extra_artifacts": self._merge_analysis_artifacts(chain_context.artifacts, carried_artifacts),
                "chain_context": chain_context,
                "capability_snapshot": capability_snapshot.summary(),
                "known_failure_lessons": self.store.list_failure_skills(case.capability_family(), limit=3),
            }
            if "failed_directions" in inspect.signature(self.analyzer_decider.analyze_and_decide).parameters:
                analyze_kwargs["failed_directions"] = recent_failed_directions
            if "capability_mode" in inspect.signature(self.analyzer_decider.analyze_and_decide).parameters:
                analyze_kwargs["capability_mode"] = self.capability_mode
            analysis = self.analyzer_decider.analyze_and_decide(**analyze_kwargs)
            self._log_phase(case.case_id, attempt, "analyzer", "end")
            analysis = self._normalize_analysis_for_mode(analysis)

            matched_failed_directions = self.store.find_similar_failed_directions(
                case.capability_family(),
                analysis,
                limit=3,
            )
            direction_duplicate = bool(matched_failed_directions)
            duplicate_direction_streak = duplicate_direction_streak + 1 if direction_duplicate else 0
            direction_stuck = duplicate_direction_streak >= 2

            print(f"Analysis: {analysis.root_cause}")
            self._print_analysis_details(analysis)
            self._print_failed_direction_matches(matched_failed_directions)
            print(f"Next action: {analysis.next_action}")
            attempt_report = {
                "attempt": attempt,
                "initial_result": self._result_summary(result),
                "initial_correct": False,
                "chain_trace": list(chain_context.tool_sequence),
                "analysis": self._analysis_summary(analysis),
                "matched_failed_directions": matched_failed_directions,
                "direction_duplicate": direction_duplicate,
                "direction_stuck": direction_stuck,
            }
            if direction_stuck:
                case_report["direction_stuck"] = True

            # Give up if recommended
            if analysis.next_action == "give_up":
                print(f"Giving up on this case: {analysis.rationale}")
                self._save_failure_lesson(case, analysis, result, chain_context)
                stored_direction = self._record_failed_direction(
                    case=case,
                    attempt=attempt,
                    analysis=analysis,
                    chain_context=chain_context,
                    used_tool=None,
                    retry_answer=None,
                    failure_reason=analysis.rationale or "Analyzer chose give_up.",
                    source="give_up",
                )
                self._log_give_up(case, attempt, analysis)
                attempt_report["decision"] = "give_up"
                attempt_report["stored_failed_direction"] = stored_direction
                case_report["attempts"].append(attempt_report)
                self._finalize_case_report(case_report, solved=False, final_result=result, attempts_used=attempt)
                return False

            # Generate capabilities based on decision
            step = EvolutionStep(iteration=attempt, case_id=case.case_id, analysis=analysis)

            # Step 1: generate and validate tool first
            staged_tool = None
            if self.capability_mode != "scratch_code_skill" and analysis.next_action in ["generate_tool", "generate_both"]:
                print(f"Generating tool...")
                self._log_phase(case.case_id, attempt, "tool_generation", "start")
                step.tool_proposal = self.generator.generate_tool(case, analysis, chain_context=chain_context)
                self._log_phase(case.case_id, attempt, "tool_generation", "end")
                print(f"Generated: {step.tool_proposal.name}")
                attempt_report["tool_proposal"] = self._tool_summary(step.tool_proposal)

                print(f"Validating tool...")
                step.validation = self.validator.validate_tool(
                    step.tool_proposal,
                    origin_case=case,
                    agent_factory=lambda: self._create_agent(case, attempt=attempt, phase="validate_regression"),
                    regression_cases=None,
                    chain_context=chain_context,
                    attempt=attempt,
                )

                if step.validation.passed:
                    print(f"✓ Tool runtime validation passed. Staging for immediate retry...")
                    staged_tool = step.tool_proposal
                    attempt_report["tool_validation"] = self._validation_summary(step.validation)
                else:
                    print(f"✗ Validation failed: {step.validation.reason}")
                    step.decision = "discard"
                    attempt_report["tool_validation"] = self._validation_summary(step.validation)

            # Step 2: generate skill only after we know which tools are actually available
            # Pass the staged tool (may be None) so skill references only usable tools
            skill_validation = None
            skill_for_retry = None
            if analysis.next_action in ["generate_skill", "generate_both", "generate_code_skill"] or staged_tool:
                print(f"Generating skill...")
                self._log_phase(case.case_id, attempt, "skill_generation", "start")
                if analysis.next_action == "generate_code_skill" and hasattr(self.generator, "generate_code_writing_skill"):
                    step.skill_proposal = self.generator.generate_code_writing_skill(
                        case,
                        analysis,
                        existing_skill_content=existing_skill.content if existing_skill else None,
                        chain_context=chain_context,
                    )
                else:
                    step.skill_proposal = self.generator.generate_skill(
                        case,
                        analysis,
                        staged_tool,
                        existing_skill_content=existing_skill.content if existing_skill else None,
                        chain_context=chain_context,
                    )
                print(f"Generated: {step.skill_proposal.name}")
                self._print_skill_content("Generated skill draft", step.skill_proposal.content)
                attempt_report["skill_proposal"] = self._skill_summary(step.skill_proposal)
                should_review_skill = hasattr(self.generator, "review_skill") and analysis.next_action != "generate_code_skill"
                if should_review_skill:
                    print("Reviewing generated skill with full context...")
                    step.skill_proposal = self.generator.review_skill(
                        case,
                        analysis,
                        step.skill_proposal,
                        staged_tool,
                        existing_skill.content if existing_skill else None,
                        chain_context,
                        family_examples,
                        self.store.list_failure_skills(case.capability_family(), limit=3),
                    )
                    self._print_skill_content("Reviewed skill draft", step.skill_proposal.content)
                    attempt_report["reviewed_skill_proposal"] = self._skill_summary(step.skill_proposal)
                self._log_phase(case.case_id, attempt, "skill_generation", "end")

                print(f"Validating skill...")
                skill_validation = self.validator.validate_skill(step.skill_proposal, case.capability_family())

                if skill_validation.passed:
                    print(f"✓ Skill valid. Retrying current case with the new rule...")
                    skill_for_retry = Skill(
                        name=case.capability_family(),
                        description=step.skill_proposal.description,
                        content=step.skill_proposal.content,
                        level=step.skill_proposal.level,
                        depends_on=step.skill_proposal.depends_on,
                    )
                    attempt_report["skill_validation"] = self._validation_summary(skill_validation)
                else:
                    print(f"✗ Skill invalid: {skill_validation.reason}")
                    attempt_report["skill_validation"] = self._validation_summary(skill_validation)

            if staged_tool or skill_for_retry:
                retry_agent = self._create_agent(
                    case,
                    task_skill_override=skill_for_retry,
                    required_tool_name=staged_tool.name if staged_tool else None,
                    required_skill_name=case.capability_family() if self.capability_mode == "scratch_code_skill" and skill_for_retry else None,
                    require_bash_action_before_complete=bool(self.capability_mode == "scratch_code_skill" and skill_for_retry),
                    required_image_artifact_before_complete=bool(self.capability_mode == "scratch_code_skill" and skill_for_retry),
                    attempt=attempt,
                    phase="retry",
                )
                self._log_phase(case.case_id, attempt, "retry", "start")
                retry_result = retry_agent.run(
                    case.prompt,
                    case.image_path,
                    initial_observations=self._chain_observations_for_agent(chain_context),
                )
                self._log_phase(case.case_id, attempt, "retry", "end")
                if self._check_success(retry_result, case):
                    print(f"✓ SOLVED after learning. Answer: {retry_result.final_answer}")
                    if staged_tool and step.validation and self.capability_mode != "scratch_code_skill":
                        self.store.promote_tool(staged_tool, step.validation)
                        self.validator.clear_preserved_tool(staged_tool.name)
                    if skill_for_retry and skill_validation and skill_validation.passed:
                        self.store.promote_skill(case.capability_family(), step.skill_proposal)
                    step.decision = "keep"
                    self._log_step(step)
                    self._print_token_summary(attempt)
                    self._log_success(case, attempt)
                    self._remember_family_example(case)
                    attempt_report["retry_result"] = self._result_summary(retry_result)
                    attempt_report["decision"] = "keep"
                    case_report["attempts"].append(attempt_report)
                    self._finalize_case_report(case_report, solved=True, final_result=retry_result, attempts_used=attempt)
                    return True

                print(f"✗ Retry with learned capability still failed: {retry_result.final_answer}")
                if staged_tool and self.capability_mode != "scratch_code_skill":
                    if step.validation and step.validation.replaced_existing_tool:
                        self.validator.restore_preserved_tool(staged_tool.name)
                    else:
                        self.store.remove_tool(staged_tool.name)
                step.decision = "discard"
                attempt_report["retry_result"] = self._result_summary(retry_result)
                attempt_report["decision"] = "discard"
                carried_artifacts = self._merge_analysis_artifacts(
                    result.get_image_artifacts(),
                    retry_result.get_image_artifacts(),
                    step.validation.artifacts if step.validation else [],
                )
                attempt_report["stored_failed_direction"] = self._record_failed_direction(
                    case=case,
                    attempt=attempt,
                    analysis=analysis,
                    chain_context=chain_context,
                    used_tool=staged_tool.name if staged_tool else None,
                    retry_answer=retry_result.final_answer,
                    failure_reason="Retry with generated capability still failed.",
                    source="retry_failed",
                )

                previous_attempts.append(
                    self._summarize_attempt(
                        attempt,
                        result.final_answer,
                        analysis.next_action,
                        used_tool=staged_tool.name if staged_tool else None,
                        retry_answer=retry_result.final_answer,
                        chain_trace=chain_context.tool_sequence,
                    )
                )
            else:
                previous_attempts.append(
                    self._summarize_attempt(
                        attempt,
                        result.final_answer,
                        analysis.next_action,
                        used_tool=None,
                        retry_answer=None,
                        chain_trace=chain_context.tool_sequence,
                    )
                )
                carried_artifacts = self._merge_analysis_artifacts(
                    result.get_image_artifacts(),
                    [],
                    step.validation.artifacts if step.validation else [],
                )
                attempt_report["decision"] = step.decision
                attempt_report["stored_failed_direction"] = self._record_failed_direction(
                    case=case,
                    attempt=attempt,
                    analysis=analysis,
                    chain_context=chain_context,
                    used_tool=step.tool_proposal.name if step.tool_proposal else None,
                    retry_answer=None,
                    failure_reason=self._validation_failure_reason(step),
                    source="validation_failed",
                )

            # Log step
            self._log_step(step)
            case_report["attempts"].append(attempt_report)

            # Continue to next attempt

        # Max attempts reached
        print(f"\n✗ Max attempts ({self.max_attempts}) reached without solving.")
        final_analysis = step.analysis if "step" in locals() else None
        final_result = retry_result if "retry_result" in locals() else result if "result" in locals() else AgentResult(
            task=case.prompt,
            final_answer="",
            steps=[],
            total_turns=0,
            success=False,
        )
        final_chain = chain_context if "chain_context" in locals() else None
        self._save_failure_lesson(case, final_analysis, final_result, final_chain)
        self._print_token_summary(self.max_attempts)
        self._finalize_case_report(case_report, solved=False, final_result=final_result, attempts_used=self.max_attempts)
        return False

    def _family_examples_for_review(self, case: TaskCase) -> list[TaskCase]:
        """Return prior solved family examples plus the current case for SOP review."""
        examples = list(self.family_examples.get(case.capability_family(), []))
        if all(existing.case_id != case.case_id for existing in examples):
            examples.append(case)
        return examples

    def _remember_family_example(self, case: TaskCase) -> None:
        """Remember solved family examples so later skill reviews can generalize across them."""
        examples = self.family_examples.setdefault(case.capability_family(), [])
        if all(existing.case_id != case.case_id for existing in examples):
            examples.append(case)

    def _create_agent(
        self,
        case: TaskCase,
        task_skill_override: Skill | None = None,
        include_learned_skills: bool = True,
        include_learned_tools: bool = True,
        required_tool_name: str | None = None,
        required_skill_name: str | None = None,
        require_bash_action_before_complete: bool = False,
        required_image_artifact_before_complete: bool = False,
        attempt: int | None = None,
        phase: str = "solve",
    ) -> ReActAgent:
        """Create agent with current capabilities."""
        capability_snapshot = self._tool_availability_snapshot(
            include_learned_tools=include_learned_tools,
            case=case,
        )
        all_skills = []
        if task_skill_override is not None:
            all_skills.append(task_skill_override)
        elif include_learned_skills:
            task_skill = self.store.get_skill(case.capability_family())
            if task_skill is not None and self._skill_uses_only_available_tools(task_skill.content, capability_snapshot):
                all_skills.append(task_skill)
        if include_learned_skills:
            all_skills.extend(self.store.list_failure_skills(case.capability_family(), limit=3))

        # Render skills and task-specific prompting hints.
        skill_text = render_skills(all_skills)
        task_prompt_hints = self._task_specific_agent_instructions(case, capability_snapshot)
        extra_instructions = "\n\n".join(
            part.strip() for part in [skill_text, task_prompt_hints] if part and part.strip()
        )

        # Build tool_definitions listing actually available learned tools
        available_tools = []
        builtin_specs = {tool.name: tool for tool in list_builtin_tools()}
        for tool_name in capability_snapshot.available_tools:
            if tool_name in builtin_specs:
                spec = builtin_specs[tool_name]
                available_tools.append(
                    f"  - {tool_name}: {spec.description} | applies when: {spec.applicability} | usage: {spec.usage_example}"
                )
                continue
            tool_file = self.learned_dir / "tools" / f"{tool_name}.py"
            meta_file = self.learned_dir / "tools" / f"{tool_name}.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text())
                applicability = meta.get("applicability_conditions", "")
                applicability_text = f" | applies when: {applicability}" if applicability else ""
                available_tools.append(
                    f"  - {tool_name}: {meta.get('description', '')}{applicability_text} | usage: {meta.get('usage_example', f'python -m tools {tool_name} <image_path>')}"
                )
            elif tool_file.exists():
                available_tools.append(f"  - {tool_name}: python -m tools {tool_name} <image_path>")

        if available_tools:
            tool_definitions = "Use: python -m tools <tool_name> [args]\n\nAvailable tools:\n" + "\n".join(available_tools)
        else:
            tool_definitions = "Use: python -m tools <tool_name> [args]\n\nNo tools available."

        # Create agent
        config = AgentConfig(
            max_turns=20,
            work_dir=self._agent_work_dir(case, attempt, phase),
            required_tool_name=required_tool_name,
            required_skill_name=required_skill_name,
            require_bash_action_before_complete=require_bash_action_before_complete,
            required_image_artifact_before_complete=required_image_artifact_before_complete,
            learned_dir=self.learned_dir,
            allowed_tool_names=self._case_allowed_tool_names(case, capability_snapshot),
            require_python_tool_command=self._requires_strict_tool_commands(case),
        )
        agent = ReActAgent(
            client=self.vlm_client,
            config=config,
            tool_definitions=tool_definitions,
            extra_instructions=extra_instructions,
        )

        return agent

    def _task_specific_agent_instructions(
        self,
        case: TaskCase,
        snapshot: ToolAvailabilitySnapshot,
    ) -> str:
        dataset_name = case.dataset_name().strip().lower()
        family = case.capability_family().strip().lower()

        if dataset_name == "gta" or family.startswith("gta"):
            gta_tools = [tool for tool in snapshot.available_tools if tool in {"OCR", "ImageDescription", "Calculator", "GoogleSearch", "CountGivenObject", "TextToBbox", "MathOCR", "DrawBox", "AddText", "Plot", "Solver", "ImageStylization", "TextToImage", "RegionAttributeDescription"}]
            tool_hint = ", ".join(gta_tools[:8]) if gta_tools else "the available GTA-compatible tools"
            return (
                "Task-specific instructions for GTA tool-using cases:\n"
                "- Prefer GTA-compatible preset tools when the question requires OCR, counting, external knowledge, symbolic solving, localization, or image editing.\n"
                f"- Available GTA-style tools in this run include: {tool_hint}.\n"
                "- Use the exact tool usage examples shown in the system tool list. Fill in concrete arguments such as query=..., expression=..., bbox=..., text=..., or instruction=... as needed.\n"
                "- If a prior tool produced an image artifact, you may pass that artifact to a later image tool using the current artifact path.\n"
                "- Keep the final answer short and exact. Do not add explanation unless the task explicitly asks for it.\n"
                "- For edit/generation tasks, produce the requested image artifact first, then answer with the final short response."
            )

        if dataset_name == "textvqa" or family.startswith("textvqa"):
            return (
                "Task-specific instructions for OCR / short-answer VQA:\n"
                "- Read the relevant text or attribute directly from the image before deciding to act.\n"
                "- No learned tool is required for most OCR-style questions here; if the answer is visible, skip bash and complete immediately.\n"
                "- Use bash only when a preset tool is clearly necessary to enlarge or clarify local evidence; otherwise answer directly from the image.\n"
                "- On your first valid completion, use exactly this format:\n"
                "  Final Answer: <shortest exact answer string>\n"
                "  ACTION: TASK_COMPLETE\n"
                "- Do not output a full sentence when a short span is sufficient.\n"
                "- Do not add explanation, prefixes, suffixes, or quotes unless the text itself contains them.\n"
                "- For names, brands, words, letters, or numbers, return only the target span, not a sentence about it."
            )

        if dataset_name == "chartqa" or family.startswith("chartqa"):
            x_values_bbox = case.metadata.get("x_values_bbox") if isinstance(case.metadata.get("x_values_bbox"), dict) else {}
            y_values_bbox = case.metadata.get("y_values_bbox") if isinstance(case.metadata.get("y_values_bbox"), dict) else {}
            x_labels = list(x_values_bbox.keys())[:12]
            y_labels = list(y_values_bbox.keys())[:12]
            if x_values_bbox or y_values_bbox:
                return (
                    "Task-specific instructions for same-tool ChartQA comparisons:\n"
                    f"- Available x-axis labels from metadata: {x_labels}\n"
                    f"- Available y-axis labels from metadata: {y_labels}\n"
                    "- The VTool-style chart tools expect JSON arguments.\n"
                    "- For x-axis tools, pass a JSON list of selected labels and a JSON object for `x_values_bbox`.\n"
                    "- For y-axis tools, pass a JSON list of selected labels and a JSON object for `y_values_bbox`.\n"
                    "- Example:\n"
                    "  python -m tools focus_on_x_values_with_highlight <image_path> '[\"2019\"]' '<x_values_bbox_json>'\n"
                    "- Prefer these tools only when narrowing the visual field will improve the final answer."
                )

        if dataset_name == "refocus_tablevqa" or family.startswith("refocus_tablevqa"):
            columns_bbox = case.metadata.get("columns_bbox") if isinstance(case.metadata.get("columns_bbox"), dict) else {}
            row_starters = case.metadata.get("row_starters") if isinstance(case.metadata.get("row_starters"), dict) else {}
            column_labels = list(columns_bbox.keys())[:12]
            row_labels = list(row_starters.keys())[:12]
            if columns_bbox or row_starters:
                return (
                    "Task-specific instructions for same-tool TableVQA comparisons:\n"
                    f"- Available column labels from metadata: {column_labels}\n"
                    f"- Available row labels from metadata: {row_labels}\n"
                    "- The VTool-style table tools expect JSON arguments.\n"
                    "- For column tools, pass a JSON list of selected columns and a JSON object for `columns_bbox`.\n"
                    "- For row tools, pass a JSON list of selected rows and a JSON object for `row_starters`.\n"
                    "- Example:\n"
                    "  python -m tools focus_on_columns_with_mask <image_path> '[\"Year\",\"Score\"]' '<columns_bbox_json>'\n"
                    "- Prefer these tools only when narrowing the table visually will improve the final answer."
                )

        return ""

    def _tool_availability_snapshot(
        self,
        include_learned_tools: bool = True,
        case: TaskCase | None = None,
    ) -> ToolAvailabilitySnapshot:
        """Build the fail-closed tool inventory for the current subset."""
        if self.capability_mode == "skill_only_same_tools":
            include_learned_tools = False
        snapshot = ToolAvailabilitySnapshot()
        builtin_names = [tool.name for tool in list_builtin_tools()]
        if self.fixed_builtin_tools:
            allowed = set(self.fixed_builtin_tools)
            builtin_names = [name for name in builtin_names if name in allowed]
        snapshot.available_tools.extend(builtin_names)
        if case is not None and self._requires_strict_tool_commands(case):
            allowed = self._allowed_gta_tool_names(case)
            snapshot.available_tools = [tool for tool in snapshot.available_tools if tool in allowed]

        if not include_learned_tools:
            return snapshot

        if self.disable_generated_tools:
            return snapshot

        tools_dir = self.learned_dir / "tools"
        if not tools_dir.exists():
            return snapshot

        py_names = {path.stem for path in tools_dir.glob("*.py")}
        manifest_names = {path.stem for path in tools_dir.glob("*.json")}

        for tool_name in sorted(py_names):
            tool_path = tools_dir / f"{tool_name}.py"
            code = tool_path.read_text(encoding="utf-8")
            if self.validator.is_untrusted_tool_code(code):
                snapshot.untrusted_tools.append(tool_name)
            else:
                if tool_name not in snapshot.available_tools:
                    snapshot.available_tools.append(tool_name)

        for tool_name in sorted(manifest_names - py_names):
            snapshot.manifest_only_tools.append(tool_name)

        return snapshot

    def _case_allowed_tool_names(
        self,
        case: TaskCase,
        snapshot: ToolAvailabilitySnapshot,
    ) -> list[str] | None:
        if not self._requires_strict_tool_commands(case):
            return None
        return list(snapshot.available_tools)

    def _requires_strict_tool_commands(self, case: TaskCase) -> bool:
        dataset_name = case.dataset_name().strip().lower()
        return self.capability_mode == "skill_only_same_tools" and dataset_name == "gta"

    @staticmethod
    def _allowed_gta_tool_names(case: TaskCase) -> set[str]:
        raw_tools = case.metadata.get("gt_tools")
        if isinstance(raw_tools, list):
            return {
                str(tool).strip()
                for tool in raw_tools
                if str(tool).strip()
            }
        return set()

    def _skill_uses_only_available_tools(self, skill_content: str, snapshot: ToolAvailabilitySnapshot) -> bool:
        """Fail closed when a skill references tools that are not executable in this subset."""
        required_tools = self.validator._extract_tool_sequence(skill_content)
        return all(tool_name in snapshot.available_tools for tool_name in required_tools)

    def _usable_skill_content(self, skill: Skill | None, snapshot: ToolAvailabilitySnapshot) -> str | None:
        """Return skill content only when all referenced tools are currently usable."""
        if skill is None:
            return None
        return skill.content if self._skill_uses_only_available_tools(skill.content, snapshot) else None

    def _agent_work_dir(self, case: TaskCase, attempt: int | None, phase: str) -> Path:
        """Create a unique artifact directory per case/attempt/phase."""
        return (
            self.work_dir
            / f"problem_{self._slug(case.problem_id)}"
            / f"case_{case.case_id}"
            / f"attempt_{attempt or 'unknown'}"
            / phase
        )

    def _check_success(self, result: AgentResult, case: TaskCase) -> bool:
        """Check if agent successfully solved the case, using LLM as judge."""
        if not result.success:
            return False

        if self.answer_checker is not None:
            return self.answer_checker(result.final_answer, case)

        prompt = f"""You are a strict answer judge. Determine if the agent's answer matches the expected answer.

Expected answer: {case.gold_answer}
Agent's answer: {result.final_answer}

The agent's answer may be verbose. Extract the final answer the agent committed to and check if it is semantically equivalent to the expected answer (e.g. "3:20", "3:20 PM", "15:20" are all equivalent).

Reply with only one word: CORRECT or INCORRECT"""

        messages = [
            {"role": "user", "content": prompt},
        ]

        from core.vlm_client import ModelSettings
        response, _ = self.vlm_client.chat(messages, ModelSettings(temperature=0.0, max_tokens=4000))
        upper = response.upper()
        return "INCORRECT" not in upper and "CORRECT" in upper

    def _log_success(self, case: TaskCase, attempts: int):
        """Log successful solve."""
        self.store.log_step({
            "case_id": case.case_id,
            "solve_success": True,
            "attempts": attempts,
        })

    def _log_give_up(self, case: TaskCase, attempts: int, analysis):
        """Log giving up."""
        self.store.log_step({
            "case_id": case.case_id,
            "solve_success": False,
            "gave_up": True,
            "attempts": attempts,
            "reason": analysis.rationale,
        })

    def _log_step(self, step: EvolutionStep):
        """Log evolution step."""
        self.store.log_step({
            "iteration": step.iteration,
            "case_id": step.case_id,
            "analysis": {
                "root_cause": step.analysis.root_cause if step.analysis else None,
                "next_action": step.analysis.next_action if step.analysis else None,
            },
            "tool_generated": step.tool_proposal.name if step.tool_proposal else None,
            "skill_generated": step.skill_proposal.name if step.skill_proposal else None,
            "validation_input_image": step.validation.input_image if step.validation else None,
            "validation_chain_trace": step.validation.chain_trace if step.validation else [],
            "decision": step.decision,
        })

    def _print_token_summary(self, attempts: int):
        """Print token usage summary."""
        total = self.analyzer_decider.total_usage + self.generator.total_usage

        print(f"\n{'='*60}")
        print(f"Token Usage Summary (after {attempts} attempts)")
        print(f"{'='*60}")
        print(f"AnalyzerDecider: {self.analyzer_decider.total_usage.total_tokens:,} tokens")
        print(f"  - Prompt: {self.analyzer_decider.total_usage.prompt_tokens:,}")
        print(f"  - Completion: {self.analyzer_decider.total_usage.completion_tokens:,}")
        print(f"Generator: {self.generator.total_usage.total_tokens:,} tokens")
        print(f"  - Prompt: {self.generator.total_usage.prompt_tokens:,}")
        print(f"  - Completion: {self.generator.total_usage.completion_tokens:,}")
        print(f"{'='*60}")
        print(f"TOTAL: {total.total_tokens:,} tokens")
        print(f"  - Prompt: {total.prompt_tokens:,}")
        print(f"  - Completion: {total.completion_tokens:,}")
        print(f"{'='*60}\n")

    def _save_failure_lesson(
        self,
        case: TaskCase,
        analysis,
        result: AgentResult,
        chain_context: ToolChainContext | None,
    ) -> None:
        """Persist a non-promoted failure lesson for later inspection."""
        if not hasattr(self.generator, "generate_failure_skill"):
            return
        existing_skill = self.store.get_skill(case.capability_family())
        proposal = self.generator.generate_failure_skill(
            case,
            analysis,
            result,
            existing_skill_content=existing_skill.content if existing_skill else None,
            chain_context=chain_context,
            family_examples=self._family_examples_for_review(case),
        )
        self.store.save_failure_skill(case.capability_family(), case.case_id, proposal)

    def _log_phase(self, case_id: str, attempt: int, phase: str, status: str) -> None:
        """Emit lightweight per-phase markers for hang diagnosis."""
        self.store.log_step({
            "type": "phase",
            "case_id": case_id,
            "attempt": attempt,
            "phase": phase,
            "status": status,
        })

    @staticmethod
    def _slug(value: str) -> str:
        """Normalize identifiers used in artifact directory names."""
        import re

        return re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()) or "unknown"

    @staticmethod
    def _merge_analysis_artifacts(*artifact_groups: list[str]) -> list[str]:
        merged: list[str] = []
        for group in artifact_groups:
            for artifact in group:
                if artifact and artifact not in merged:
                    merged.append(artifact)
        return merged

    @staticmethod
    def _summarize_attempt(
        attempt: int,
        answer: str,
        next_action: str,
        used_tool: str | None,
        retry_answer: str | None,
        chain_trace: list[str] | None = None,
    ) -> str:
        """Summarize one failed evolve attempt for later analyzer context."""
        summary = f"Attempt {attempt}: initial answer={answer!r}; analyzer chose {next_action}"
        if chain_trace:
            summary += f"; prior chain={' -> '.join(chain_trace)}"
        if used_tool:
            summary += f"; staged tool={used_tool}"
        if retry_answer is not None:
            summary += f"; retry answer={retry_answer!r}"
        return summary

    @staticmethod
    def _chain_observations_for_agent(chain_context: ToolChainContext) -> list[tuple[str, list[str]]]:
        """Convert an existing tool chain into initial observations for retry."""
        if not chain_context.tool_sequence:
            return []

        observations: list[tuple[str, list[str]]] = []
        for index, tool_name in enumerate(chain_context.tool_sequence):
            observation = chain_context.observations[index] if index < len(chain_context.observations) else ""
            artifact = chain_context.artifacts[index] if index < len(chain_context.artifacts) else ""
            combined = f"Validated prior tool chain step {index + 1}: {tool_name}\n{observation}".strip()
            artifacts = [artifact] if artifact else []
            observations.append((combined, artifacts))
        return observations

    @staticmethod
    def _print_skill_content(label: str, content: str) -> None:
        """Print the generated skill content for real-time debugging."""
        print(f"{label}:")
        print("--- SKILL START ---")
        print(content.strip() or "(empty)")
        print("--- SKILL END ---")

    @staticmethod
    def _print_analysis_details(analysis) -> None:
        """Print the analyzer's structured reasoning in a readable way."""
        details = [
            ("Observed", getattr(analysis, "rationale", "")),
            ("Missing step", getattr(analysis, "missing_step", "")),
            ("Tool goal", getattr(analysis, "tool_goal", "")),
            ("Skill note", getattr(analysis, "skill_update_note", "")),
            ("Differentiation", getattr(analysis, "differentiation_note", "")),
            ("Confidence", f"{getattr(analysis, 'confidence', 0.0):.2f}" if hasattr(analysis, "confidence") else ""),
        ]
        for label, value in details:
            text = str(value).strip()
            if not text:
                continue
            print(f"  {label}: {text}")

    def _normalize_analysis_for_mode(self, analysis):
        """Coerce analyzer actions into ones supported by the current capability mode."""
        if self.disable_generated_tools and analysis.next_action in {"generate_tool", "generate_both"}:
            analysis.next_action = "generate_skill"
            if not analysis.skill_update_note:
                analysis.skill_update_note = (
                    analysis.tool_goal
                    or analysis.missing_step
                    or "Improve the solver policy using the fixed tool pool only."
                )
            if not analysis.differentiation_note:
                analysis.differentiation_note = (
                    "Comparison mode disables new tool generation and converts tool requests into strategy updates."
                )
            return analysis

        if self.capability_mode == "skill_only_same_tools":
            if analysis.next_action in {"generate_tool", "generate_both", "generate_code_skill"}:
                analysis.next_action = "generate_skill"
                if not analysis.skill_update_note:
                    analysis.skill_update_note = (
                        analysis.missing_step
                        or analysis.tool_goal
                        or "Improve tool selection and ordering without adding new tools."
                    )
                if not analysis.differentiation_note:
                    analysis.differentiation_note = (
                        "Same-tool mode only allows SOP updates with the existing approved tool set."
                    )
            return analysis

        if self.capability_mode != "scratch_code_skill":
            return analysis

        if analysis.next_action in {"generate_tool", "generate_both"}:
            analysis.next_action = "generate_code_skill"
            if not analysis.skill_update_note:
                analysis.skill_update_note = (
                    analysis.tool_goal
                    or analysis.missing_step
                    or "Write temporary Python code to create an edited image before answering."
                )
            if not analysis.differentiation_note:
                analysis.differentiation_note = "Scratch-code mode converts persistent tool requests into code-writing skill updates."
        return analysis

    @staticmethod
    def _print_failed_direction_matches(matches: list[dict]) -> None:
        """Print the closest historical failed directions for debugging."""
        if not matches:
            return
        print(f"  Similar failed directions: {len(matches)}")
        for match in matches[:3]:
            missing_step = str(match.get("missing_step", "")).strip() or "N/A"
            similarity = float(match.get("similarity", 0.0))
            print(
                f"    - case={match.get('case_id')} attempt={match.get('attempt')} "
                f"action={match.get('next_action')} similarity={similarity:.2f} "
                f"missing_step={missing_step}"
            )

    @staticmethod
    def _new_case_report(case: TaskCase) -> dict:
        """Initialize a detailed per-case evolve report."""
        return {
            "case_id": case.case_id,
            "problem_id": case.problem_id,
            "capability_family": case.capability_family(),
            "prompt": case.prompt,
            "gold_answer": case.gold_answer,
            "image_path": case.image_path,
            "metadata": dict(case.metadata),
            "attempts": [],
            "direction_stuck": False,
        }

    @staticmethod
    def _finalize_case_report(case_report: dict, solved: bool, final_result: AgentResult, attempts_used: int) -> None:
        """Store the final outcome for the current case report."""
        case_report["solved"] = solved
        case_report["attempts_used"] = attempts_used
        case_report["final_result"] = EvolutionLoop._result_summary(final_result)

    @staticmethod
    def _result_summary(result: AgentResult) -> dict:
        """Compact result summary that is easy to inspect later."""
        return {
            "final_answer": result.final_answer,
            "success": result.success,
            "turns": result.total_turns,
            "artifacts": list(result.all_artifacts),
            "image_artifacts": result.get_image_artifacts(),
            "steps": [
                {
                    "turn": step.turn,
                    "action": None if step.action is None else {
                        "name": step.action.name,
                        "arguments": step.action.arguments,
                    },
                    "observation": step.observation,
                    "artifacts": list(step.artifacts),
                    "is_final": step.is_final,
                    "is_format_error": step.is_format_error,
                }
                for step in result.steps
            ],
        }

    @staticmethod
    def _analysis_summary(analysis) -> dict:
        """Structured analyzer summary for saved reports."""
        return {
            "root_cause": analysis.root_cause,
            "next_action": analysis.next_action,
            "confidence": analysis.confidence,
            "missing_step": analysis.missing_step,
            "tool_goal": analysis.tool_goal,
            "skill_update_note": analysis.skill_update_note,
            "rationale": analysis.rationale,
            "differentiation_note": analysis.differentiation_note,
        }

    @staticmethod
    def _tool_summary(proposal) -> dict:
        """Structured tool summary for saved reports."""
        return {
            "name": proposal.name,
            "description": proposal.description,
            "applicability_conditions": proposal.applicability_conditions,
            "usage_example": proposal.usage_example,
            "expected_inputs": list(proposal.expected_inputs),
            "expected_outputs": list(proposal.expected_outputs),
            "code": proposal.code,
        }

    @staticmethod
    def _skill_summary(proposal) -> dict:
        """Structured skill summary for saved reports."""
        return {
            "name": proposal.name,
            "description": proposal.description,
            "applicability_conditions": proposal.applicability_conditions,
            "content": proposal.content,
            "level": proposal.level,
            "depends_on": list(proposal.depends_on),
        }

    @staticmethod
    def _validation_summary(validation) -> dict:
        """Structured validation summary for saved reports."""
        return {
            "passed": validation.passed,
            "static_ok": validation.static_ok,
            "origin_ok": validation.origin_ok,
            "regression_ok": validation.regression_ok,
            "reason": validation.reason,
            "leakage_detected": validation.leakage_detected,
            "failed_cases": list(validation.failed_cases),
            "artifacts": list(validation.artifacts),
            "input_image": validation.input_image,
            "chain_trace": list(validation.chain_trace),
            "replaced_existing_tool": validation.replaced_existing_tool,
        }

    def _record_failed_direction(
        self,
        case: TaskCase,
        attempt: int,
        analysis,
        chain_context: ToolChainContext | None,
        used_tool: str | None,
        retry_answer: str | None,
        failure_reason: str,
        source: str,
    ) -> dict:
        """Persist one tried-and-failed direction and return a compact summary."""
        direction = FailedDirection(
            case_id=case.case_id,
            attempt=attempt,
            created_at=datetime.now().isoformat(),
            root_cause=analysis.root_cause,
            missing_step=analysis.missing_step,
            next_action=analysis.next_action,
            tool_goal=analysis.tool_goal,
            skill_update_note=analysis.skill_update_note,
            chain_trace=list(chain_context.tool_sequence) if chain_context else [],
            used_tool=used_tool,
            retry_answer=retry_answer,
            failure_reason=failure_reason,
            source=source,
        )
        saved = self.store.save_failed_direction(case.capability_family(), direction)
        summary = dict(saved.get("stored_direction", {}))
        summary["deduped"] = bool(saved.get("deduped"))
        summary["similarity"] = round(float(saved.get("similarity", 0.0)), 3)
        return summary

    @staticmethod
    def _validation_failure_reason(step: EvolutionStep) -> str:
        """Summarize why this attempted direction failed before retry."""
        reasons: list[str] = []
        if step.validation and step.validation.reason:
            reasons.append(step.validation.reason)
        if step.skill_proposal is not None and step.validation is None:
            reasons.append("Skill was generated but no runtime retry occurred.")
        if not reasons:
            reasons.append("Generated capability did not reach a successful retry.")
        return " ".join(reasons)
