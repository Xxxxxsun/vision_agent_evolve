"""Validation engine for proposals (3-stage validation)."""

from __future__ import annotations
import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from core.types import TaskCase
from .types import RevisionBrief, ToolProposal, SkillProposal, ValidationResult, ToolChainContext

if TYPE_CHECKING:
    from core.agent import ReActAgent


class Validator:
    """3-stage validation: static, origin, regression."""

    def __init__(self, work_dir: Path, learned_dir: Path):
        self.work_dir = work_dir
        self.learned_dir = learned_dir

    def validate_tool(
        self,
        proposal: ToolProposal,
        origin_case: TaskCase,
        agent_factory,  # callable that creates agent
        regression_cases: list[TaskCase] | None = None,
        chain_context: ToolChainContext | None = None,
        attempt: int | None = None,
    ) -> ValidationResult:
        """Validate tool proposal."""

        result = ValidationResult(passed=False)

        # Stage 1: Static validation
        result.static_ok = self._validate_syntax(proposal.code)
        if not result.static_ok:
            return self._failure_result(
                result,
                reason="Syntax error in generated code",
                failure_type="syntax_error",
                evidence=["Tool code did not parse as valid Python."],
                rewrite_requirements=["Return syntactically valid Python.", "Keep a top-level run(image_path: str) function."],
                banned_patterns=["incomplete code blocks", "unterminated strings", "malformed JSON-to-code escaping"],
                retry_action="revise_tool",
            )

        leakage_reason = self._detect_static_answer_leakage(proposal.code, origin_case.gold_answer)
        if leakage_reason:
            result.leakage_detected = True
            return self._failure_result(
                result,
                reason=leakage_reason,
                failure_type="answer_leakage",
                evidence=["Static inspection found the current gold answer inside the tool proposal."],
                rewrite_requirements=["Remove the final answer from code and ToolResult.answer.", "Return only intermediate artifacts."],
                banned_patterns=[origin_case.gold_answer, "hardcoded final answer", "ToolResult.answer with the gold answer"],
                retry_action="revise_tool",
            )

        specificity_reason = self._detect_case_specific_tool(proposal, origin_case)
        if specificity_reason:
            return self._failure_result(
                result,
                reason=specificity_reason,
                failure_type="case_specific_logic",
                evidence=["Static inspection found image- or case-anchored logic in the tool proposal."],
                rewrite_requirements=[
                    "Replace case-specific thresholds or coordinates with relative or image-derived logic.",
                    "State applicability conditions for a family-level visual pattern.",
                ],
                banned_patterns=["current case id", "current image path", "fixed one-image thresholds"],
                retry_action="revise_tool",
            )

        # Stage 2: Runtime validation on the origin case
        project_root = Path(__file__).parents[1]
        learned_tools_dir = self.learned_dir / "tools"
        learned_tools_dir.mkdir(parents=True, exist_ok=True)
        tool_path = learned_tools_dir / f"{proposal.name}.py"
        manifest_path = learned_tools_dir / f"{proposal.name}.json"
        preserved = self._preserve_existing_tool(tool_path, manifest_path)
        tool_path.write_text(proposal.code, encoding="utf-8")
        result.replaced_existing_tool = preserved

        try:
            if chain_context and chain_context.tool_sequence:
                if not chain_context.latest_artifact:
                    self._rollback_staged_tool(tool_path, manifest_path, preserved)
                    return self._failure_result(
                        result,
                        reason=chain_context.reason or "Existing tool chain did not produce an artifact to chain from",
                        failure_type="runtime_error",
                        evidence=["The prior chain could not provide the expected artifact input."],
                        rewrite_requirements=["Make the tool work on the latest available artifact state.", "Handle missing chained artifacts safely."],
                        banned_patterns=["assuming a previous artifact always exists"],
                        retry_action="revise_tool",
                    )
                input_image = chain_context.latest_artifact
                result.chain_trace = list(chain_context.tool_sequence)
            else:
                input_image = origin_case.image_path

            result.input_image = input_image
            command = [
                sys.executable,
                "-m",
                "tools",
                proposal.name,
                input_image,
            ]
            runtime = subprocess.run(
                command,
                cwd=project_root,
                env=self._tool_env(project_root, origin_case.problem_id, origin_case.case_id, attempt, f"validate_{proposal.name}"),
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = runtime.stdout + runtime.stderr

            if runtime.returncode != 0:
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason=f"Tool command failed with exit code {runtime.returncode}: {output.strip()}",
                    failure_type="runtime_error",
                    evidence=[output.strip()[:240] or f"exit code {runtime.returncode}"],
                    rewrite_requirements=["Handle image inputs robustly.", "Return ToolResult(status='ok', ...) on valid inputs."],
                    banned_patterns=["uncaught OpenCV exceptions", "assuming fixed image shapes"],
                    retry_action="revise_tool",
                )

            if "STATUS: error" in output:
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason=f"Tool returned error status: {output.strip()}",
                    failure_type="runtime_error",
                    evidence=[output.strip()[:240]],
                    rewrite_requirements=["Avoid returning STATUS:error for representative cluster inputs.", "Produce a valid artifact before returning success."],
                    banned_patterns=["ToolResult(status='error') on normal inputs"],
                    retry_action="revise_tool",
                )

            runtime_leak_reason = self._detect_runtime_answer_leakage(output, origin_case.gold_answer)
            if runtime_leak_reason:
                result.leakage_detected = True
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason=runtime_leak_reason,
                    failure_type="answer_leakage",
                    evidence=[output.strip()[:240]],
                    rewrite_requirements=["Do not emit the final answer from runtime output.", "Return artifacts and optional short intermediate summaries only."],
                    banned_patterns=[origin_case.gold_answer, "ANSWER containing final answer"],
                    retry_action="revise_tool",
                )

            artifacts = self._extract_artifacts(output)
            if not artifacts:
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason="Tool did not produce any artifacts",
                    failure_type="no_artifact",
                    evidence=[output.strip()[:240] or "No ARTIFACTS line was emitted."],
                    rewrite_requirements=["Save at least one real artifact under artifacts/.", "Return the same artifact path in ToolResult.artifacts."],
                    banned_patterns=["status-only tools", "tools with no artifact output"],
                    retry_action="revise_tool",
                )

            missing_artifacts = [artifact for artifact in artifacts if not (project_root / artifact).exists()]
            if missing_artifacts:
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason=f"Tool reported missing artifacts: {', '.join(missing_artifacts)}",
                    failure_type="no_artifact",
                    evidence=missing_artifacts,
                    rewrite_requirements=["Write the artifact file before returning.", "Keep ToolResult.artifacts aligned with real relative file paths."],
                    banned_patterns=["nonexistent artifact paths"],
                    retry_action="revise_tool",
                )

            result.origin_ok = True
            result.artifacts = artifacts

        except Exception as e:
            self._rollback_staged_tool(tool_path, manifest_path, preserved)
            return self._failure_result(
                result,
                reason=f"Error testing origin case: {e}",
                failure_type="runtime_error",
                evidence=[str(e)],
                rewrite_requirements=["Guard runtime exceptions.", "Handle normal origin-case inputs without crashing."],
                banned_patterns=["uncaught exceptions"],
                retry_action="revise_tool",
            )

        # Stage 3: Regression validation (optional)
        if regression_cases:
            result.regression_ok, failed = self._test_regression(
                regression_cases,
                agent_factory,
            )
            if not result.regression_ok:
                result.failed_cases = failed
                self._rollback_staged_tool(tool_path, manifest_path, preserved)
                return self._failure_result(
                    result,
                    reason=f"Breaks {len(failed)} previously solved cases",
                    failure_type="case_specific_logic",
                    evidence=failed[:3],
                    rewrite_requirements=["Generalize across multiple cases in the same family.", "Avoid assumptions that only hold for the origin case."],
                    banned_patterns=["origin-only logic"],
                    retry_action="switch_to_skill",
                )
        else:
            result.regression_ok = True

        # All validations passed
        result.passed = True
        return result

    def build_chain_context(self, case: TaskCase, skill_content: str | None, attempt: int | None = None) -> ToolChainContext:
        """Execute the currently learned SOP tool chain for this case and capture its latest artifact."""
        context = ToolChainContext(latest_input_image=case.image_path)
        tool_sequence = self._extract_tool_sequence(skill_content or "")
        if not tool_sequence:
            return context

        project_root = Path(__file__).parents[1]
        current_input = case.image_path

        for tool_name in tool_sequence:
            context.tool_sequence.append(tool_name)
            context.commands.append(f"python -m tools {tool_name} {current_input}")
            tool_path = self.learned_dir / "tools" / f"{tool_name}.py"
            manifest_path = self.learned_dir / "tools" / f"{tool_name}.json"
            if not tool_path.exists():
                context.failed = True
                if manifest_path.exists():
                    context.reason = f"Tool chain blocked at {tool_name}: tool manifest exists but source file is missing"
                else:
                    context.reason = f"Tool chain failed at {tool_name}: source file is unavailable"
                return context
            if self.is_untrusted_tool_code(tool_path.read_text(encoding="utf-8")):
                context.failed = True
                context.reason = f"Tool chain blocked at {tool_name}: tool is marked untrusted due to hardcoded final answers"
                return context
            output, returncode = self._run_tool_command(
                tool_name,
                current_input,
                project_root,
                case.problem_id,
                case.case_id,
                attempt,
                f"chain_{len(context.tool_sequence)}_{tool_name}",
            )
            context.observations.append(output)

            if returncode != 0 or "STATUS: error" in output:
                context.failed = True
                context.reason = f"Tool chain failed at {tool_name}: {output.strip()}"
                return context

            artifacts = self._extract_artifacts(output)
            context.artifacts.extend([artifact for artifact in artifacts if artifact not in context.artifacts])
            if not artifacts:
                context.failed = True
                context.reason = f"Tool chain tool '{tool_name}' did not produce an artifact"
                return context

            latest_artifact = artifacts[-1]
            if not (project_root / latest_artifact).exists():
                context.failed = True
                context.reason = f"Tool chain artifact missing: {latest_artifact}"
                return context

            context.latest_input_image = current_input
            context.latest_artifact = latest_artifact
            current_input = latest_artifact

        return context

    def validate_skill(self, proposal: SkillProposal, problem_id: str) -> ValidationResult:
        """Validate skill proposal (simpler than tool)."""
        result = ValidationResult(passed=False)

        # Basic checks
        if not proposal.name or not proposal.content:
            return self._failure_result(
                result,
                reason="Missing name or content",
                failure_type="syntax_error",
                evidence=["Skill proposal omitted required fields."],
                rewrite_requirements=["Return a name and markdown SOP content."],
                banned_patterns=["empty skill content"],
                retry_action="revise_skill",
            )

        if proposal.name != problem_id:
            return self._failure_result(
                result,
                reason=f"Skill name must match problem_id '{problem_id}'",
                failure_type="weak_applicability",
                evidence=[proposal.name],
                rewrite_requirements=["Keep the skill name aligned with the capability family."],
                banned_patterns=["renaming the task family"],
                retry_action="revise_skill",
            )

        if proposal.content.lstrip().startswith("---"):
            return self._failure_result(
                result,
                reason="Skill content should not include frontmatter",
                failure_type="syntax_error",
                evidence=["Skill body included frontmatter instead of markdown-only SOP content."],
                rewrite_requirements=["Return markdown-only SOP content without frontmatter."],
                banned_patterns=["frontmatter in content"],
                retry_action="revise_skill",
            )

        specificity_reason = self._detect_case_specific_skill(proposal, problem_id)
        if specificity_reason:
            return self._failure_result(
                result,
                reason=specificity_reason,
                failure_type="case_specific_logic",
                evidence=["Skill content appears anchored to concrete example details."],
                rewrite_requirements=["Write family-level branch conditions.", "Keep placeholders generic and avoid concrete example values."],
                banned_patterns=["too many concrete numbers", "concrete image path", "one-example rule"],
                retry_action="revise_skill",
            )

        result.static_ok = True
        result.origin_ok = True  # Skills don't have runtime validation
        result.regression_ok = True
        result.passed = True

        return result

    def _validate_syntax(self, code: str) -> bool:
        """Check if Python code has valid syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _detect_static_answer_leakage(self, code: str, gold_answer: str) -> str:
        """Reject tools that hardcode the current case answer or an obvious final-answer literal."""
        gold_text = str(gold_answer).strip()
        hardcoded_ok_answers = self._extract_hardcoded_ok_answers(code)
        if any(self._check_answer(answer, gold_text) for answer in hardcoded_ok_answers):
            return "Tool code hardcodes the current case answer in ToolResult.answer"

        quoted_gold = re.compile(rf"['\"]{re.escape(gold_text)}['\"]")
        if gold_text and quoted_gold.search(code):
            return "Tool code contains the current case gold answer as a string literal"

        return ""

    def _detect_runtime_answer_leakage(self, output: str, gold_answer: str) -> str:
        """Reject tools that directly emit the current case answer at runtime."""
        tool_answer = self._extract_answer(output)
        if tool_answer and self._check_answer(tool_answer, gold_answer):
            return "Tool runtime output leaked the current case answer via ToolResult.answer"
        return ""

    def _failure_result(
        self,
        result: ValidationResult,
        reason: str,
        failure_type: str,
        evidence: list[str],
        rewrite_requirements: list[str],
        banned_patterns: list[str],
        retry_action: str,
    ) -> ValidationResult:
        result.reason = reason
        result.failure_type = failure_type
        result.revision_brief = RevisionBrief(
            failure_type=failure_type,
            reason=reason,
            evidence=[str(item) for item in evidence if str(item).strip()],
            rewrite_requirements=[str(item) for item in rewrite_requirements if str(item).strip()],
            banned_patterns=[str(item) for item in banned_patterns if str(item).strip()],
            retry_action=retry_action,  # type: ignore[arg-type]
        )
        return result

    def _detect_case_specific_tool(self, proposal: ToolProposal, origin_case: TaskCase) -> str:
        """Reject tool proposals that explicitly anchor to one case or image path."""
        combined = "\n".join(
            [
                proposal.description,
                proposal.applicability_conditions,
                proposal.code,
                proposal.usage_example,
            ]
        )
        if origin_case.case_id and origin_case.case_id in combined:
            return "Tool proposal references the current case id and looks case-specific"
        if origin_case.image_path and str(origin_case.image_path) in combined:
            return "Tool proposal references the current image path and looks case-specific"
        if self._count_numeric_literals(proposal.code) >= 12:
            return "Tool code contains too many numeric literals and looks overfit to one example"
        return ""

    def _detect_case_specific_skill(self, proposal: SkillProposal, problem_id: str) -> str:
        """Reject skills that are too tied to one example instead of the task family."""
        combined = "\n".join([proposal.description, proposal.applicability_conditions, proposal.content])
        if "<image_path>" not in proposal.content and "python -m tools" in proposal.content:
            return "Skill references a concrete tool command without generic <image_path> placeholder"
        if problem_id not in proposal.name:
            return "Skill name no longer matches the task family"
        if self._count_numeric_literals(combined) >= 8:
            return "Skill content contains too many concrete numbers and looks example-specific"
        return ""

    def _extract_hardcoded_ok_answers(self, code: str) -> list[str]:
        """Extract string literals used as ToolResult.answer when status='ok'."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        answers: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not self._is_tool_result_call(node):
                continue
            status_value = self._extract_constant_keyword(node, "status")
            answer_value = self._extract_constant_keyword(node, "answer")
            if status_value == "ok" and isinstance(answer_value, str) and answer_value.strip():
                answers.append(answer_value.strip())
        return answers

    def _count_numeric_literals(self, text: str) -> int:
        return len(re.findall(r"\b\d+(?:\.\d+)?\b", text or ""))

    def _is_tool_result_call(self, node: ast.Call) -> bool:
        func = node.func
        return isinstance(func, ast.Name) and func.id == "ToolResult"

    def _extract_constant_keyword(self, node: ast.Call, keyword_name: str) -> str | None:
        for keyword in node.keywords:
            if keyword.arg != keyword_name:
                continue
            value = keyword.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
        return None

    def _check_answer(self, actual: str, expected: str) -> bool:
        """Check if answer matches expected."""
        import re
        actual_norm = str(actual).strip().lower()
        expected_norm = str(expected).strip().lower()

        if actual_norm == expected_norm:
            return True

        # Word-boundary match to avoid "3:20" matching inside "13:20"
        return bool(re.search(r'(?<!\d)' + re.escape(expected_norm) + r'(?!\d)', actual_norm))

    def _test_regression(
        self,
        cases: list[TaskCase],
        agent_factory,
    ) -> tuple[bool, list[str]]:
        """Test on regression cases."""
        failed = []

        for case in cases:
            try:
                agent = agent_factory()
                result = agent.run(case.prompt, case.image_path)

                if not self._check_answer(result.final_answer, case.gold_answer):
                    failed.append(case.case_id)

            except Exception:
                failed.append(case.case_id)

        return len(failed) == 0, failed

    def _extract_artifacts(self, output: str) -> list[str]:
        """Extract artifact paths from ToolResult text output."""
        match = re.search(r"ARTIFACTS:\s*(.+)", output)
        if not match:
            return []
        return [artifact.strip() for artifact in match.group(1).split(",") if artifact.strip()]

    def _extract_answer(self, output: str) -> str:
        """Extract ToolResult answer text if present."""
        match = re.search(r"ANSWER:\s*(.+)", output)
        if not match:
            return ""
        return match.group(1).strip()

    def is_untrusted_tool_code(self, code: str) -> bool:
        """Identify learned tools that embed obvious fixed final-answer literals."""
        return bool(self._extract_hardcoded_ok_answers(code))

    def _extract_tool_sequence(self, skill_content: str) -> list[str]:
        """Extract ordered tool names from an SOP."""
        matches = re.findall(r"python(?:3)?\s+-m\s+tools\s+([a-zA-Z0-9_]+)\s+<(?:image|artifact)_path>", skill_content)
        sequence: list[str] = []
        for tool_name in matches:
            if tool_name not in sequence:
                sequence.append(tool_name)
        return sequence

    def _run_tool_command(
        self,
        tool_name: str,
        image_path: str,
        project_root: Path,
        problem_id: str,
        case_id: str,
        attempt: int | None,
        stage_label: str,
    ) -> tuple[str, int]:
        """Run a learned tool on a concrete input image and return combined output."""
        command = [sys.executable, "-m", "tools", tool_name, image_path]
        runtime = subprocess.run(
            command,
            cwd=project_root,
            env=self._tool_env(project_root, problem_id, case_id, attempt, stage_label),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return runtime.stdout + runtime.stderr, runtime.returncode

    def _tool_env(self, project_root: Path, problem_id: str, case_id: str, attempt: int | None, stage_label: str) -> dict[str, str]:
        """Build a consistent environment for learned tool execution."""
        import os

        env = os.environ.copy()
        scoped_work_dir = (
            self.work_dir
            / f"problem_{self._slug(problem_id)}"
            / f"case_{case_id}"
            / f"attempt_{attempt or 'unknown'}"
            / stage_label
        )
        env["VISION_AGENT_PROJECT_ROOT"] = str(project_root)
        env["VISION_AGENT_WORK_DIR"] = str(scoped_work_dir)
        env["VISION_AGENT_LEARNED_DIR"] = str(self.learned_dir)
        return env

    def restore_preserved_tool(self, tool_name: str) -> None:
        """Restore the previously promoted version of a tool after a failed staged retry."""
        tool_path = self.learned_dir / "tools" / f"{tool_name}.py"
        manifest_path = self.learned_dir / "tools" / f"{tool_name}.json"
        self._rollback_staged_tool(tool_path, manifest_path, preserved=True)

    def clear_preserved_tool(self, tool_name: str) -> None:
        """Drop backups for a tool once the new promoted version is committed."""
        self._backup_tool_path(tool_name).unlink(missing_ok=True)
        self._backup_manifest_path(tool_name).unlink(missing_ok=True)

    def _preserve_existing_tool(self, tool_path: Path, manifest_path: Path) -> bool:
        """Back up an existing promoted tool before staging a same-name candidate."""
        preserved = False
        if tool_path.exists():
            self._backup_tool_path(tool_path.stem).write_text(tool_path.read_text(encoding="utf-8"), encoding="utf-8")
            preserved = True
        if manifest_path.exists():
            self._backup_manifest_path(tool_path.stem).write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")
            preserved = True
        return preserved

    def _rollback_staged_tool(self, tool_path: Path, manifest_path: Path, preserved: bool) -> None:
        """Undo a failed staged tool write without deleting the previously promoted tool."""
        tool_name = tool_path.stem
        backup_tool = self._backup_tool_path(tool_name)
        backup_manifest = self._backup_manifest_path(tool_name)
        if preserved:
            if backup_tool.exists():
                tool_path.write_text(backup_tool.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                tool_path.unlink(missing_ok=True)
            if backup_manifest.exists():
                manifest_path.write_text(backup_manifest.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                manifest_path.unlink(missing_ok=True)
        else:
            tool_path.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)

    def _backup_tool_path(self, tool_name: str) -> Path:
        return self.learned_dir / "tools" / f".{tool_name}.backup.py"

    def _backup_manifest_path(self, tool_name: str) -> Path:
        return self.learned_dir / "tools" / f".{tool_name}.backup.json"

    @staticmethod
    def _slug(value: str) -> str:
        """Normalize identifiers used in artifact directory names."""
        return re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()) or "unknown"
