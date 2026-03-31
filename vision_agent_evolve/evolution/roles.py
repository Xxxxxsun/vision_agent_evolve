"""Simplified roles for evolution (2 roles instead of 10)."""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

from core.vlm_client import VLMClient, ModelSettings, UsageStats
from core.types import AgentResult, TaskCase
from skills.base import Skill
from tools.builtin_tools import list_builtin_tools
from .types import CoverageContract, FailedDirection, FailureAnalysis, MasteryProfile, MasteryStrategyCandidate, RevisionBrief, ToolProposal, SkillProposal, SkillReferenceProposal, ToolChainContext


class AnalyzerDecider:
    """Combined role: analyzes failure and decides next action."""

    def __init__(self, client: VLMClient, debug_dir: Path | None = None):
        self.client = client
        self.total_usage = UsageStats()
        self.debug_dir = debug_dir
        if self.debug_dir is not None:
            self.debug_dir.mkdir(parents=True, exist_ok=True)

    def analyze_and_decide(
        self,
        case: TaskCase,
        result: AgentResult,
        current_capabilities: list[str],
        previous_attempts: list[str] | None = None,
        attempt: int | None = None,
        extra_artifacts: list[str] | None = None,
        chain_context: ToolChainContext | None = None,
        capability_snapshot: str = "",
        known_failure_lessons: list[Skill] | None = None,
        failed_directions: list[FailedDirection] | None = None,
        capability_mode: str = "persistent_tools",
    ) -> FailureAnalysis:
        """Analyze failure and decide next action in one LLM call."""

        # Build analysis with visual context if available
        analysis_artifacts = self._merge_artifacts(result.get_image_artifacts(), extra_artifacts or [])
        has_images = bool(case.image_path) or bool(analysis_artifacts)

        prompt_parts = []

        # Text description
        text_analysis = f"""You are analyzing why an agent failed to solve a vision task.

IMPORTANT:
- Do not think too much.
- Do not produce long reasoning.
- Do not write an essay.
- Return compact JSON as quickly as possible.

Task: {case.prompt}
Task Family: {case.problem_id}
Expected Answer: {case.gold_answer}
Agent's Answer: {result.final_answer}
Agent Steps: {len(result.steps)} turns
Dense Caption: {case.dense_caption() or "N/A"}

Current Capabilities:
{chr(10).join(current_capabilities)}

Capability Mode: {capability_mode}

"""
        if capability_snapshot:
            text_analysis += f"""Capability Snapshot:
{capability_snapshot}

"""
        if chain_context:
            text_analysis += f"""Current Tool Chain:
{chain_context.summary()}

"""

        if previous_attempts:
            history_text = "\n".join(f"- {entry}" for entry in previous_attempts)
            text_analysis += f"""Previous failed evolve attempts for this same case:
{history_text}

"""

        if known_failure_lessons:
            text_analysis += f"""Known Failure Lessons:
{self._format_known_failure_lessons(known_failure_lessons)}

"""

        if failed_directions:
            text_analysis += f"""Previously tried and failed directions for this task family:
{self._format_failed_directions(failed_directions)}

"""

        if has_images:
            text_analysis += """
VISUAL ANALYSIS INSTRUCTIONS:
You will see the original input image and any artifacts (processed images) generated during execution.
Compare them carefully to understand:
1. Did the tool correctly process the image?
2. What's the quality/correctness of the processed output?
3. Are there visual issues (blur, wrong transformation, missing elements)?
4. Does the visual output match what the task needed?

Before deciding the next action, explicitly inspect and describe:
- what you see in the original image
- what you see in each tool-generated artifact image
- the most important visual difference between the original image and the artifact
- based on the visual details above, what they imply for the next step
- even if an existing tool succeeded on a previous example, treat the current case as potentially having new visual properties that may require an additional tool for further processing

"""

        text_analysis += """
Focus on the MINIMAL missing step needed to solve this task family.

1. What did the agent already try?
2. What visual transformation or computation is still missing?
3. If there are already tools or a task-specific skill, why were they insufficient for this image?
4. What is the next smallest useful addition: a new tool, a skill update, a code-writing skill update, both, or give up?

Provide response as JSON:
{
    "image_observation": "short description of the original image and the tool-generated image(s)",
    "root_cause": "short explanation of why the current solve failed",
    "missing_step": "the next missing transformation or computation",
    "next_action": "generate_tool|generate_skill|generate_both|generate_code_skill|give_up",
    "tool_goal": "what the next tool should do, if any",
    "skill_update_note": "what the task-specific skill should tell the solver to do next time",
    "differentiation_note": "how this direction differs from the closest failed directions, or why retrying is still justified",
    "confidence": 0.0-1.0,
    "rationale": "short reason this is the smallest useful next step"
}

Guidelines:
- Choose the change that is most suitable for helping the current VLM solve this task correctly.
- Prefer tools when changing the image or extracting intermediate information would make the task substantially easier for the current VLM.
- Prefer skills when the needed capability already exists and the main problem is strategy, ordering, or tool selection.
- If a validated tool already produced a useful artifact but the solver still keeps failing, actively consider that this case may be outside the scope of the current SOP and may need an additional tool plus a new step.
- If the current tool changed the image but the solver still cannot reliably read or use the transformed result, prefer generate_both over repeated generate_skill updates.
- If an existing tool chain already produced an intermediate artifact, decide whether the missing capability should happen after that artifact rather than on the raw image.
- generate_tool: use when a new transformation/computation is missing.
- generate_skill: use when the existing tools are already sufficient but the solver needs a better ordered rule.
- generate_both: use when a new tool is needed and the solver should be told when to use it.
- generate_code_skill: use when the solver should learn how to write and run temporary Python editing code for this task family, instead of promoting a new permanent tool.
- If previous attempts only updated the skill and the case still failed, strongly prefer generate_both unless the current tools are already clearly sufficient.
- Do not merely rephrase a previously failed direction.
- If your proposal is close to a prior failed direction, the differentiation_note must explain the concrete new angle or why retrying is still justified.
- If no materially different direction exists, prefer give_up or switch action type instead of repeating the same idea.
- give_up: if task seems unsolvable or we've tried too many times
- Stay concrete and task-family-specific. Do not write a broad essay about VLM weaknesses.
"""
        if capability_mode == "scratch_code_skill":
            text_analysis += """
Scratch-code mode rules:
- Do not propose a new permanent tool unless it is absolutely unavoidable.
- Prefer generate_code_skill when temporary Python editing code should be written at solve time.
- The code-writing skill should teach the solver how to edit the image for the question, save an edited artifact, observe it, and only then answer.
- In this mode, generate_tool and generate_both will be treated as weaker fallbacks than generate_code_skill.
"""

        # Build message with images if available
        if has_images:
            # Create multimodal content
            content_parts = [{"type": "text", "text": text_analysis}]

            # Add original image
            if case.image_path:
                from pathlib import Path
                if Path(case.image_path).exists():
                    content_parts.append({
                        "type": "text",
                        "text": "\n--- ORIGINAL INPUT IMAGE ---"
                    })
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {"url": VLMClient.image_data_url(case.image_path)}
                    })

            # Add artifact images
            image_artifacts = analysis_artifacts
            if image_artifacts:
                content_parts.append({
                    "type": "text",
                    "text": f"\n--- TOOL-GENERATED ARTIFACTS ({len(image_artifacts)} images) ---"
                })

                for i, artifact_path in enumerate(image_artifacts[:3]):  # Limit to 3 artifacts
                    from pathlib import Path
                    if Path(artifact_path).exists():
                        content_parts.append({
                            "type": "text",
                            "text": f"\nArtifact {i+1}: {Path(artifact_path).name}"
                        })
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": VLMClient.image_data_url(artifact_path)}
                        })

            messages = [
                {"role": "system", "content": "You are an expert AI system analyzer with vision capabilities. Do not think too much. Return compact JSON only."},
                {"role": "user", "content": content_parts},
            ]
        else:
            # Text-only analysis
            messages = [
                {"role": "system", "content": "You are an expert AI system analyzer. Do not think too much. Return compact JSON only."},
                {"role": "user", "content": text_analysis},
            ]

        response, usage = self.client.chat(messages, ModelSettings(temperature=0.3, max_tokens=16000))
        self.total_usage = self.total_usage + usage

        # Print usage
        print(f"  [AnalyzerDecider] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")

        # Extract JSON
        analysis_dict = self._extract_json(response)
        self._log_analysis(
            case=case,
            attempt=attempt,
            prompt_text=text_analysis,
            attached_images=self._attached_image_refs(case, analysis_artifacts),
            chain_summary=chain_context.summary() if chain_context else "",
            capability_snapshot=capability_snapshot,
            raw_response=response,
            parsed_analysis=analysis_dict,
        )

        return FailureAnalysis(
            root_cause=analysis_dict.get("root_cause", "Unknown"),
            next_action=analysis_dict.get("next_action", "give_up"),
            confidence=float(analysis_dict.get("confidence", 0.5)),
            missing_step=analysis_dict.get("missing_step", ""),
            tool_goal=analysis_dict.get("tool_goal", ""),
            skill_update_note=analysis_dict.get("skill_update_note", ""),
            failure_stage=analysis_dict.get("failure_stage", "Unknown"),
            missing_capabilities=analysis_dict.get("missing_capabilities", []),
            rationale=self._merge_rationale(
                analysis_dict.get("image_observation", ""),
                analysis_dict.get("rationale", ""),
            ),
            differentiation_note=analysis_dict.get("differentiation_note", ""),
        )

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON from text."""
        # Try to find JSON block
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback to empty dict
        return {}

    def _attached_image_refs(self, case: TaskCase, image_artifacts: list[str]) -> list[str]:
        refs: list[str] = []
        if case.image_path:
            refs.append(case.image_path)
        refs.extend(image_artifacts[:3])
        return refs

    def _merge_artifacts(self, primary: list[str], secondary: list[str]) -> list[str]:
        merged: list[str] = []
        for artifact in [*primary, *secondary]:
            if artifact and artifact not in merged:
                merged.append(artifact)
        return merged

    def _format_known_failure_lessons(self, lessons: list[Skill]) -> str:
        return "\n\n".join(
            f"- {lesson.description or lesson.name}\nApplicability: {lesson.applicability_conditions or 'N/A'}\n{lesson.content.strip()}"
            for lesson in lessons
        )

    def _format_failed_directions(self, directions: list[FailedDirection]) -> str:
        return "\n".join(
            self._format_failed_direction(direction, index)
            for index, direction in enumerate(directions, start=1)
        )

    @staticmethod
    def _format_failed_direction(direction: FailedDirection, index: int) -> str:
        parts = [
            f"{index}. case={direction.case_id}",
            f"attempt={direction.attempt}",
            f"action={direction.next_action}",
            f"missing_step={direction.missing_step or 'N/A'}",
        ]
        if direction.tool_goal:
            parts.append(f"tool_goal={direction.tool_goal}")
        if direction.skill_update_note:
            parts.append(f"skill_note={direction.skill_update_note}")
        if direction.failure_reason:
            parts.append(f"failed_because={direction.failure_reason}")
        if direction.times_failed > 1:
            parts.append(f"times_failed={direction.times_failed}")
        return " | ".join(parts)

    def _log_analysis(
        self,
        case: TaskCase,
        attempt: int | None,
        prompt_text: str,
        attached_images: list[str],
        chain_summary: str,
        capability_snapshot: str,
        raw_response: str,
        parsed_analysis: dict[str, Any],
    ) -> None:
        if self.debug_dir is None:
            return

        filename = f"case_{case.case_id}_attempt_{attempt or 'unknown'}.json"
        payload = {
            "case_id": case.case_id,
            "problem_id": case.problem_id,
            "attempt": attempt,
            "prompt_text": prompt_text,
            "attached_images": attached_images,
            "chain_summary": chain_summary,
            "capability_snapshot": capability_snapshot,
            "raw_response": raw_response,
            "parsed_analysis": parsed_analysis,
        }
        (self.debug_dir / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _merge_rationale(self, image_observation: str, rationale: str) -> str:
        observation = str(image_observation).strip()
        reason = str(rationale).strip()
        if observation and reason:
            return f"{observation} {reason}".strip()
        return observation or reason


class Generator:
    """Generates tools and skills based on analysis."""

    def __init__(self, client: VLMClient):
        self.client = client
        self.total_usage = UsageStats()

    def generate_tool(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        chain_context: ToolChainContext | None = None,
        training_context: str = "",
        coverage_contract: CoverageContract | None = None,
    ) -> ToolProposal:
        """Generate a new tool based on failure analysis."""
        prompt = self._build_tool_prompt(case, analysis, chain_context, training_context, coverage_contract)
        messages = self._build_tool_messages(case, prompt, chain_context)

        response, usage = self.client.chat(messages, ModelSettings(temperature=0.4, max_tokens=12000))
        self.total_usage = self.total_usage + usage

        # Print usage
        print(f"  [Generator/Tool] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")

        # Extract JSON
        proposal_dict = self._extract_json(response)
        return self._normalize_tool_proposal(proposal_dict)

    def _build_tool_messages(
        self,
        case: TaskCase,
        prompt: str,
        chain_context: ToolChainContext | None,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        image_refs: list[tuple[str, str]] = []
        if case.image_path:
            image_refs.append(("ORIGINAL INPUT IMAGE", case.image_path))

        latest_artifact = chain_context.latest_artifact if chain_context else ""
        if latest_artifact:
            image_refs.append(("LATEST INTERMEDIATE ARTIFACT", latest_artifact))

        for label, image_path in image_refs:
            path = Path(image_path)
            if not path.exists():
                continue
            content.append({"type": "text", "text": f"\n--- {label}: {path.name} ---"})
            content.append({"type": "image_url", "image_url": {"url": self._image_data_url(path)}})

        return [
            {"role": "system", "content": "You are an expert Python developer for vision tools."},
            {"role": "user", "content": content if len(content) > 1 else prompt},
        ]

    def _build_tool_prompt(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        chain_context: ToolChainContext | None,
        training_context: str,
        coverage_contract: CoverageContract | None,
    ) -> str:
        chain_summary = chain_context.summary() if chain_context else "No existing tool chain."
        latest_artifact = chain_context.latest_artifact if chain_context else ""
        primitive_category = coverage_contract.primitive_category if coverage_contract else ""
        tool_skeleton = self._tool_skeleton_guidance(case, primitive_category)
        return f"""You are generating a new Python tool to solve a vision task.

Task: {case.prompt}
Image: {case.image_path}
Dense Caption: {case.dense_caption() or "N/A"}

Failure Analysis:
- Root Cause: {analysis.root_cause}
- Missing step: {analysis.missing_step}
- Tool goal: {analysis.tool_goal or analysis.rationale}
Existing Tool Chain:
{chain_summary}

Aggregated Training Context:
{training_context or "No aggregated training context provided."}

Coverage Contract:
{self._format_coverage_contract(coverage_contract)}

Primitive Skeleton Guidance:
{tool_skeleton}

Scaffold Code Template:
```python
{self._tool_code_scaffold(case, primitive_category)}
```

Generate one reusable family-level primitive tool, not a case-solving tool.

CRITICAL REQUIREMENTS:
- Maximum 150 lines of code
- Our runtime will call it as: `python -m tools <tool_name> <image_path>`
- The `image_path` input may be an intermediate artifact from a previous tool, not just the raw image.
- Put the real logic inside a top-level `run(image_path: str) -> ToolResult` function
- `main()` is optional, but if you include it, it should only do `print(run(sys.argv[1]))`
- Use libraries: opencv-python (cv2), numpy, PIL
- Use shared helpers from `tools.implementations.shared` whenever possible
- Save at least one real file under `artifacts/`
- Return that exact relative path in `artifacts=[...]`
- Print exactly one ToolResult and nothing else
- Do not use abstract base classes unless truly necessary
- Prefer a single short script over framework-heavy structure
- Do not rely on custom CLI parsing; runtime can call `run(image_path)` directly
- The easiest successful tools are usually: load image -> transform image -> save artifact -> return ToolResult
- Prefer image-derived quantities over fixed numeric literals. A few small constants are fine, but avoid many bespoke thresholds.
- If there is already a tool chain, design this tool as the next processing step after the latest artifact: `{latest_artifact or "<artifact_path>"}`.
- If the dense caption or failure analysis provides measurable visual cues (for example colors, markers, geometry, orientations, or other detectable properties), the code must include real detection/extraction steps that use those cues.
- Do not skip those cues by hardcoding image-specific coordinates, fixed vectors, or a fixed final answer in place of detection.
- Do not output the task's final answer from the tool itself.
- `ToolResult.answer` should usually be empty, or at most a short intermediate status/result summary that helps debugging without solving the task for the agent.
- Design for the recurring family/cluster pattern in the aggregated training context, not just this single representative case.
- Implement exactly one primitive visual operation or extraction step that a family skill can orchestrate later.
- Do not combine multiple unrelated transformations or solve the question end-to-end inside the tool.
- Do not compute the final arithmetic/comparison answer for the task. Only produce an artifact or an intermediate signal.
- Do not encode fixed coordinates, hardcoded answer options, fixed years, fixed counts, or per-example threshold tables.
- Avoid fixed coordinates, case ids, one-off text literals from this example, or logic that only makes sense for one image.
- Applicability conditions must describe when this tool should be used across the family, including at least one variation pattern seen in the training context.
- Preserve the scaffold's overall control flow and helper structure unless there is a strong reason not to.
- Replace only the marked TODO sections or helper internals with family-generic logic.

Follow this EXACT structure:

```python
from core.types import ToolResult
from tools.implementations.shared import load_image, save_image

def run(image_path: str) -> ToolResult:
    try:
        img = load_image(image_path)
        # ... process img into processed_img ...

        output_path = "artifacts/tool_name_output.png"
        save_image(processed_img, output_path)

        return ToolResult(
            status="ok",
            answer="",
            artifacts=[output_path],
        )
    except Exception as e:
        return ToolResult(status="error", answer="", error=str(e))

def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python {{sys.argv[0]}} <image_path>")
        sys.exit(1)

    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()
```

Provide response as JSON:
{{
    "name": "tool_name",
    "description": "brief description",
    "applicability_conditions": "when this tool should be used within the task family",
    "code": "full Python code (with main() function)",
    "usage_example": "python -m tools tool_name <image_path>",
    "expected_inputs": ["image_path", "other params if needed"],
    "expected_outputs": ["description of output", "artifacts/output.png"],
    "primitive_category": "family primitive category"
}}

IMPORTANT:
- The tool MUST state its applicability conditions in a reusable, task-family-level way.
- The applicability conditions must say what visual situation or intermediate artifact state makes this tool appropriate.
- The validator will fail the tool unless stdout contains a ToolResult with an ARTIFACTS line.
- The validator will reject tools that hardcode or directly output the task's final answer.
- The saved file must actually exist at the same relative path you put inside `artifacts=[...]`.
- Use a descriptive artifact path like `artifacts/<tool_name>_output.png`.
- Agent runtime will discover this tool by filename, so keep `name` aligned with the file/tool name.
- If a shared helper already exists for the transformation, import and use it instead of rewriting it.
- Prefer one input image and one output artifact unless the task truly needs more.
- Tool MUST print ToolResult in format:
  ANSWER: <result>
  STATUS: ok|error
  ARTIFACTS: file1.png, file2.png
"""

    def generate_skill(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        tool_proposal: ToolProposal | None = None,
        existing_skill_content: str | None = None,
        chain_context: ToolChainContext | None = None,
        training_context: str = "",
        coverage_contract: CoverageContract | None = None,
    ) -> SkillProposal:
        """Generate a new skill based on failure analysis."""

        preset_catalog = self._format_preset_tool_catalog()
        tool_context = f"""
Preset built-in tools are available for this rule:
{preset_catalog}

The skill MUST select from this preset catalog only.
"""
        if tool_proposal:
            tool_context += f"""
One newly staged tool is also available in this draft:
- Name: {tool_proposal.name}
- Description: {tool_proposal.description}
- Usage: {tool_proposal.usage_example}

If you reference it, preserve the preset-tool branches too.
"""

        existing_sop_context = ""
        if existing_skill_content:
            existing_sop_context = f"""
Existing task-family SOP:
{existing_skill_content}

This SOP already works for some examples, but it is not sufficient for the current example.
Revise it so it still preserves the previously useful behavior while adding or adjusting the steps needed for this example.
"""

        prompt = f"""You are generating a SHORT SOP-style task prompt for the solver.

Task family: {case.capability_family()}
Current question: {case.prompt}
Current image path: {case.image_path or "<image_path>"}
Dense caption: {case.dense_caption() or "N/A"}
Current failure: {analysis.root_cause}
Missing step: {analysis.missing_step}
Skill update note: {analysis.skill_update_note or analysis.rationale}
Current chain summary: {chain_context.summary() if chain_context else "No existing tool chain."}
Aggregated training context: {training_context or "No aggregated training context provided."}
Coverage contract: {self._format_coverage_contract(coverage_contract)}

{tool_context}
{existing_sop_context}

IMPORTANT CONTEXT:
- This skill is for future solves of THIS task family only.
- This skill should orchestrate the preset family tools with explicit branches when different cluster patterns need different primitives.
- The current question, image path, and dense caption are provided only so you can avoid copying sample-specific details into the SOP.
- The updated SOP must explicitly state its applicability conditions, including when the original tool alone is enough and when an added step/tool is needed.
- The SOP must cover the recurring family-level patterns in the aggregated training context, not only the current example.
- If the training context shows multiple cluster variants, the SOP should include branch conditions instead of one fixed procedure.
- Keep it short and operational.
- Write it as an SOP, not as background explanation.
- Make it reusable across future examples in the same task family.
- The content must be Markdown only. Do NOT include frontmatter.
- Use this exact structure:
  ## SOP
  1. ...
  2. ...
  3. ...
  4. ...
- At least one step must explicitly branch, for example "If ... use tool A, otherwise ...".
- Step 1 or step 2 must contain at least one exact command pattern such as `python -m tools localized_text_zoom <image_path>`.
- Only reference preset tools from the catalog above unless a staged tool is explicitly listed.
- Do not invent any new tool names.
- If this SOP extends an existing tool chain, write the next tool step using `<artifact_path>` as the input placeholder.
- When a prior tool already exists, preserve that earlier step and add the new step after it.
- Always use the placeholder `<image_path>`, not a concrete dataset path.
- Tell the solver to wait for the Observation after running the tool, then use the tool output before answering.
- Do not mention the specific numbers, arithmetic, or final answer from the current example.
- Do not mention a concrete dataset path or filename from the current example.
- Describe the final step generically as answering the original question from the corrected image or extracted result.
- Do not explain evolve history, previous knowledge, common failures, or examples.
- Do not say "mentally flip" or "visually flip" when a validated tool is available.

Provide response as JSON:
{{
    "name": "{case.capability_family()}",
    "description": "one sentence describing the task-specific SOP",
    "applicability_conditions": "when this SOP or this added step applies within the task family",
    "content": "short markdown SOP only",
    "level": "mid",
    "depends_on": []
}}
"""

        messages = [
            {"role": "system", "content": "You are an expert in creating guidance documents."},
            {"role": "user", "content": prompt},
        ]

        response, usage = self.client.chat(messages, ModelSettings(temperature=0.4, max_tokens=8000))
        self.total_usage = self.total_usage + usage

        # Print usage
        print(f"  [Generator/Skill] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")

        # Extract JSON
        proposal_dict = self._extract_json(response)

        return self._normalize_skill_proposal(case, analysis, proposal_dict, tool_proposal, existing_skill_content)

    def generate_mastery_candidates(
        self,
        case: TaskCase,
        training_context: str,
        coverage_contract: CoverageContract | None = None,
        existing_skill_content: str | None = None,
    ) -> list[MasteryStrategyCandidate]:
        preset_catalog = self._format_preset_tool_catalog()
        prompt = f"""You are proposing candidate tool-usage strategies for a mastery phase.

Task family: {case.capability_family()}
Current question: {case.prompt}
Coverage contract: {self._format_coverage_contract(coverage_contract)}
Aggregated training context: {training_context or "No aggregated training context provided."}
Existing family skill:
{existing_skill_content or "N/A"}

Available preset tools:
{preset_catalog}

Return JSON only:
{{
  "candidates": [
    {{
      "name": "short strategy name",
      "tool_sequence": ["tool_a", "tool_b"],
      "trigger_conditions": ["when this strategy should be used"],
      "avoid_conditions": ["when not to use it"],
      "fallback_action": "answer_directly|use_existing_skill",
      "rationale": "why this strategy should work"
    }}
  ]
}}

Rules:
- Propose 2 to 4 candidates.
- Only use tools from the preset catalog.
- Focus on when to use tools, when not to use them, and when to chain them.
- At least one candidate may choose no tool if direct reasoning is better.
- Keep trigger and avoid conditions family-level, not one-case-specific.
"""
        messages = [
            {"role": "system", "content": "You design compact mastery strategies. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=3000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/MasteryCandidates] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        payload = self._extract_json(response)
        candidates = self._normalize_mastery_candidates(payload.get("candidates", []))
        if candidates:
            return candidates
        return self._fallback_mastery_candidates(case, coverage_contract)

    def distill_mastery_skill(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        mastery_profile: MasteryProfile,
        existing_skill_content: str | None = None,
        training_context: str = "",
        coverage_contract: CoverageContract | None = None,
    ) -> SkillProposal:
        prompt = f"""You are distilling a final mastery skill from an evaluated tool-boundary profile.

Task family: {case.capability_family()}
Current question: {case.prompt}
Coverage contract: {self._format_coverage_contract(coverage_contract)}
Aggregated training context: {training_context or "No aggregated training context provided."}
Existing skill:
{existing_skill_content or "N/A"}

Mastery profile:
{self._format_mastery_profile(mastery_profile)}

Return JSON only:
{{
    "name": "{case.capability_family()}",
    "description": "one sentence describing the mastery SOP",
    "applicability_conditions": "when this mastery SOP applies",
    "content": "router markdown only; reference branch docs explicitly using paths like references/tool_branch.md",
    "level": "mid",
    "depends_on": [],
    "references": [
        {{
            "path": "references/tool_branch.md",
            "description": "what this branch handles",
            "content": "detailed markdown branch skill"
        }}
    ]
}}

Rules:
- The main content must act as a router, not a full summary.
- Put branch details into references/*.md.
- The SOP must be derived from the mastery profile, not from one current example.
- Include explicit positive trigger conditions and negative trigger conditions.
- Reference only tools that appear in the mastery profile.
- Always include at least one no-tool or do-not-use branch reference.
- Keep the router short and operational.
"""
        messages = [
            {"role": "system", "content": "You distill mastery profiles into reusable SOPs. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=5000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/MasterySkill] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal_dict = self._extract_json(response)
        proposal = self._normalize_skill_proposal(case, analysis, proposal_dict, None, existing_skill_content)
        if not proposal.content.strip() or "references/" not in proposal.content or not proposal.references:
            proposal.content, proposal.references = self._build_mastery_skill_package(mastery_profile)
        if not proposal.applicability_conditions.strip():
            proposal.applicability_conditions = self._sanitize_applicability(
                "; ".join(mastery_profile.recommended_trigger_conditions or mastery_profile.common_success_signals)
            )
        return proposal

    @staticmethod
    def _format_preset_tool_catalog() -> str:
        lines: list[str] = []
        for spec in list_builtin_tools():
            lines.append(
                f"- {spec.name}: {spec.description} | applies when: {spec.applicability} | notes: {spec.benchmark_notes}"
            )
        return "\n".join(lines) or "- none"

    def _format_mastery_profile(self, profile: MasteryProfile) -> str:
        return (
            f"primary_tool={profile.primary_tool or 'none'}; "
            f"tool_sequence={', '.join(profile.tool_sequence) or 'none'}; "
            f"supported_patterns={'; '.join(profile.supported_cluster_patterns) or 'N/A'}; "
            f"negative_patterns={'; '.join(profile.negative_cluster_patterns) or 'N/A'}; "
            f"trigger={'; '.join(profile.recommended_trigger_conditions) or 'N/A'}; "
            f"avoid={'; '.join(profile.negative_trigger_conditions) or 'N/A'}; "
            f"success_signals={'; '.join(profile.common_success_signals) or 'N/A'}; "
            f"failure_signals={'; '.join(profile.common_failure_signals) or 'N/A'}; "
            f"best_chain={'; '.join(profile.best_chain_patterns) or 'N/A'}; "
            f"bad_chain={'; '.join(profile.bad_chain_patterns) or 'N/A'}; "
            f"coverage={profile.coverage:.3f}; precision={profile.precision:.3f}; delta={profile.score_delta:.3f}"
        )

    def _normalize_mastery_candidates(self, raw_candidates: list[Any]) -> list[MasteryStrategyCandidate]:
        available = {spec.name for spec in list_builtin_tools()}
        normalized: list[MasteryStrategyCandidate] = []
        for index, item in enumerate(raw_candidates[:4], start=1):
            if not isinstance(item, dict):
                continue
            tools = [str(tool).strip() for tool in item.get("tool_sequence", []) if str(tool).strip() in available]
            candidate = MasteryStrategyCandidate(
                name=str(item.get("name", "")).strip() or f"strategy_{index}",
                tool_sequence=tools,
                trigger_conditions=[str(value).strip() for value in item.get("trigger_conditions", []) if str(value).strip()],
                avoid_conditions=[str(value).strip() for value in item.get("avoid_conditions", []) if str(value).strip()],
                fallback_action=str(item.get("fallback_action", "answer_directly")).strip() or "answer_directly",
                rationale=str(item.get("rationale", "")).strip(),
            )
            normalized.append(candidate)
        return normalized

    def _fallback_mastery_candidates(
        self,
        case: TaskCase,
        coverage_contract: CoverageContract | None,
    ) -> list[MasteryStrategyCandidate]:
        primitive = (coverage_contract.primitive_category if coverage_contract else "").strip()
        if primitive and primitive in {spec.name for spec in list_builtin_tools()}:
            return [
                MasteryStrategyCandidate(
                    name=f"{primitive}_primary",
                    tool_sequence=[primitive],
                    trigger_conditions=[f"use when the family pattern matches {primitive} evidence needs"],
                    avoid_conditions=["skip when direct reading or reasoning already resolves the case reliably"],
                    fallback_action="answer_directly",
                    rationale="Primary single-tool mastery candidate derived from the family primitive.",
                ),
                MasteryStrategyCandidate(
                    name="no_tool_fallback",
                    tool_sequence=[],
                    trigger_conditions=["use when the question is already directly answerable from the raw image"],
                    avoid_conditions=[f"avoid when {primitive} is clearly needed to localize evidence"],
                    fallback_action="answer_directly",
                    rationale="No-tool baseline for boundary discovery.",
                ),
            ]
        return [
            MasteryStrategyCandidate(
                name="no_tool_fallback",
                tool_sequence=[],
                trigger_conditions=["use when the task is directly answerable without preprocessing"],
                avoid_conditions=[],
                fallback_action="answer_directly",
                rationale="Fallback mastery baseline without tools.",
            )
        ]

    def _build_mastery_skill_content(self, profile: MasteryProfile) -> str:
        primary_tool = profile.primary_tool or (profile.tool_sequence[0] if profile.tool_sequence else "")
        first_command = f"`python -m tools {primary_tool} <image_path>`" if primary_tool else "no tool command"
        second_command = ""
        if len(profile.tool_sequence) > 1:
            second_command = f" then `python -m tools {profile.tool_sequence[1]} <artifact_path>`"
        trigger = self._strip_bullet("; ".join(profile.recommended_trigger_conditions or profile.common_success_signals) or "the current image matches the profiled tool-trigger pattern")
        avoid = self._strip_bullet("; ".join(profile.negative_trigger_conditions or profile.common_failure_signals) or "direct answering is already sufficient")
        return "\n".join([
            "## SOP",
            f"1. Confirm this applies: {trigger}",
            f"2. If the current case matches that trigger, run {first_command}{second_command} and wait for the Observation before answering.",
            f"3. If the case instead matches this avoid condition, skip the tool path and answer directly: {avoid}.",
            "4. Answer the original question from the final artifact when the tool path is used; otherwise answer from the raw image.",
        ])

    def generate_code_writing_skill(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        existing_skill_content: str | None = None,
        chain_context: ToolChainContext | None = None,
        training_context: str = "",
        coverage_contract: CoverageContract | None = None,
    ) -> SkillProposal:
        """Generate a skill that teaches the solver to write temporary Python editing code."""

        existing_sop_context = ""
        if existing_skill_content:
            existing_sop_context = f"""
Existing task-family SOP:
{existing_skill_content}

This SOP already works for some examples, but it is not sufficient for the current example.
Revise it so it preserves the previously useful behavior while adding or adjusting the temporary-code editing workflow.
"""

        prompt = f"""You are generating a SHORT SOP-style task prompt for the solver.

Task family: {case.capability_family()}
Current question: {case.prompt}
Current image path: {case.image_path or "<image_path>"}
Dense caption: {case.dense_caption() or "N/A"}
Current failure: {analysis.root_cause}
Missing step: {analysis.missing_step}
Skill update note: {analysis.skill_update_note or analysis.rationale}
Current chain summary: {chain_context.summary() if chain_context else "No existing tool chain."}
Aggregated training context: {training_context or "No aggregated training context provided."}
Coverage contract: {self._format_coverage_contract(coverage_contract)}

{existing_sop_context}

IMPORTANT CONTEXT:
- This skill is for future solves of THIS task family only.
- The skill must teach the solver how to write temporary Python image-editing code at solve time.
- The SOP must reflect recurring family-level conditions from the aggregated training context, not a one-case editing trick.
- The temporary code should remove or weaken irrelevant visual content, preserve only the evidence needed for the question, and save an edited image under `artifacts/`.
- The solver must observe the edited image before answering.
- Do not invent a permanent tool name or a learned tool registration step.
- Keep it short and operational.
- Write it as an SOP, not as background explanation.
- Make it reusable across future examples in the same task family.
- The content must be Markdown only. Do NOT include frontmatter.
- Use this exact structure:
  ## SOP
  1. ...
  2. ...
  3. ...
  4. ...
- The SOP must explicitly tell the solver to:
  1. extract the target from the question,
  2. decide what to keep vs hide/highlight,
  3. write and run temporary Python editing code via bash,
  4. save an edited image to `artifacts/`,
  5. wait for the Observation and answer from the edited image.
- Use the placeholders `<image_path>` and `<artifact_path>`.
- You may include a short bash/heredoc code pattern, but it must stay generic and reusable.
- Do not mention concrete dataset paths, exact numbers, or the final answer from the current example.

Provide response as JSON:
{{
    "name": "{case.capability_family()}",
    "description": "one sentence describing the code-writing SOP",
    "applicability_conditions": "when this temporary-code editing SOP applies within the task family",
    "content": "short markdown SOP only",
    "level": "mid",
    "depends_on": []
}}
"""

        messages = [
            {"role": "system", "content": "You are an expert in creating reusable SOPs for temporary Python image-editing workflows."},
            {"role": "user", "content": prompt},
        ]

        response, usage = self.client.chat(messages, ModelSettings(temperature=0.4, max_tokens=8000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/CodeSkill] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal_dict = self._extract_json(response)
        return self._normalize_code_skill_proposal(case, analysis, proposal_dict, existing_skill_content)

    def generate_coverage_contract(
        self,
        case: TaskCase,
        target_cluster_ids: list[str],
        training_context: str,
        representative_case_summaries: list[str],
        planner_action: str,
    ) -> CoverageContract:
        prompt = f"""You are writing a reusable coverage contract before generating a capability.

Task family: {case.capability_family()}
Representative case summaries:
{chr(10).join(representative_case_summaries) or "N/A"}

Aggregated training context:
{training_context or "No aggregated training context provided."}

Planner requested action: {planner_action}

Return JSON only:
{{
  "target_family": "{case.capability_family()}",
  "target_cluster_ids": {json.dumps(target_cluster_ids)},
  "problem_pattern": "short family-level pattern",
  "supported_variations": ["variation 1", "variation 2"],
  "unsupported_variations": ["variation outside intended scope"],
  "forbidden_case_specific_assumptions": ["do not hardcode one image", "no one-off coordinates"],
  "primitive_category": "localized_text_zoom|localized_color_focus|relative_position_marker|chart_value_overlay|count_support_view|generic_visual_focus",
  "tool_validation_scope": "cluster|family",
  "recommended_action": "generate_tool|generate_skill|generate_both|generate_code_skill|give_up",
  "why_this_should_generalize": "short reason"
}}

        Rules:
- Summarize the cluster-level pattern, not individual case trivia.
- Prefer one reusable primitive category rather than a full end-to-end solver tool.
- If the family/problem looks theorem-like, symbolic, or text-reasoning dominant, prefer generate_skill.
- If the pattern is not stable enough for a reusable tool, prefer generate_skill.
- Keep forbidden assumptions concrete and anti-overfitting.
"""
        messages = [
            {"role": "system", "content": "You write compact capability coverage contracts. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=2000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/Coverage] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        return self._normalize_coverage_contract(case.capability_family(), target_cluster_ids, self._extract_json(response), planner_action)

    def revise_tool(
        self,
        tool: ToolProposal,
        revision_brief: RevisionBrief,
        coverage_contract: CoverageContract | None,
        training_context: str,
    ) -> ToolProposal:
        prompt = f"""Revise this tool proposal according to the validator feedback.

Current tool name: {tool.name}
Current description: {tool.description}
Current applicability: {tool.applicability_conditions}
Current usage: {tool.usage_example}
Current code:
{tool.code}

Coverage contract:
{self._format_coverage_contract(coverage_contract)}

Aggregated training context:
{training_context}

Revision brief:
{self._format_revision_brief(revision_brief)}

Return JSON only with the same schema as tool generation.
Rules:
- Keep the tool name the same unless impossible.
- Satisfy every rewrite requirement.
- Remove banned patterns explicitly.
"""
        messages = [
            {"role": "system", "content": "You revise reusable vision tools. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=12000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/ToolRevision] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal = self._normalize_tool_proposal(self._extract_json(response))
        proposal.name = tool.name
        proposal.usage_example = f"python -m tools {tool.name} <image_path>"
        if not proposal.primitive_category:
            proposal.primitive_category = tool.primitive_category or (coverage_contract.primitive_category if coverage_contract else "")
        return proposal

    def revise_skill(
        self,
        skill: SkillProposal,
        revision_brief: RevisionBrief,
        coverage_contract: CoverageContract | None,
        training_context: str,
    ) -> SkillProposal:
        prompt = f"""Revise this skill proposal according to the validator feedback.

Current skill name: {skill.name}
Current description: {skill.description}
Current applicability: {skill.applicability_conditions}
Current content:
{skill.content}

Coverage contract:
{self._format_coverage_contract(coverage_contract)}

Aggregated training context:
{training_context}

Revision brief:
{self._format_revision_brief(revision_brief)}

Return JSON only with the same schema as skill generation.
Rules:
- Keep the skill name the same.
- Satisfy every rewrite requirement.
- Remove banned patterns explicitly.
"""
        messages = [
            {"role": "system", "content": "You revise reusable task-family SOPs. Return JSON only."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=6000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/SkillRevision] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal = self._normalize_skill_proposal(
            TaskCase(case_id="", problem_id=skill.name, prompt="", gold_answer=""),
            FailureAnalysis(root_cause=revision_brief.reason, next_action="generate_skill", confidence=0.0),
            self._extract_json(response),
            None,
            skill.content,
        )
        proposal.name = skill.name
        return proposal

    def review_skill(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        draft_skill: SkillProposal,
        tool_proposal: ToolProposal | None = None,
        existing_skill_content: str | None = None,
        chain_context: ToolChainContext | None = None,
        family_examples: list[TaskCase] | None = None,
        known_failure_lessons: list[Skill] | None = None,
    ) -> SkillProposal:
        """Review a drafted SOP with full context and fix missing conditions/branching."""
        family_context = self._format_family_examples(family_examples or [case])
        lesson_text = self._format_known_failure_lessons(known_failure_lessons or []) if known_failure_lessons else "N/A"
        prompt = f"""You are reviewing a task-family SOP draft before it is used again.

Task family: {case.capability_family()}
Current question: {case.prompt}
Current image path: {case.image_path or "<image_path>"}
Dense caption: {case.dense_caption() or "N/A"}
Task-family examples seen so far:
{family_context}

Known Failure Lessons:
{lesson_text}

Failure analysis:
- Root cause: {analysis.root_cause}
- Missing step: {analysis.missing_step}
- Skill update note: {analysis.skill_update_note or analysis.rationale}
Current chain summary: {chain_context.summary() if chain_context else "No existing tool chain."}

Existing task-family SOP (if any):
{existing_skill_content or "N/A"}

Draft SOP to review:
Description: {draft_skill.description}
Applicability: {draft_skill.applicability_conditions}
Content:
{draft_skill.content}

Available new tool:
- {tool_proposal.name if tool_proposal else "N/A"}: {tool_proposal.description if tool_proposal else "N/A"}
- Applicability: {tool_proposal.applicability_conditions if tool_proposal else "N/A"}

Review goal:
- Re-read the draft in light of the full context above.
- Check whether it forgot important applicability conditions.
- Check whether it should branch, for example when one example only needs the original tool but another example needs an added step.
- Rewrite the SOP so it can cover the whole task family represented by the examples above, not just the current example.
- Use the first/second/etc. example descriptions only to infer family-level conditions; do not copy their exact details into the final SOP.
- Keep the SOP reusable across the task family, not tied to this single example.
- Do not include concrete numbers, final answers, or dataset-specific file paths.
- Keep command placeholders generic: `<image_path>` and `<artifact_path>`.
- Treat the known failure lessons as reusable warnings and branch conditions, not as tool/runtime history.

Return JSON:
{{
  "name": "{case.capability_family()}",
  "description": "reviewed one-sentence SOP description",
  "applicability_conditions": "reviewed applicability conditions",
  "content": "reviewed markdown SOP only",
  "level": "mid",
  "depends_on": []
}}
"""
        messages = [
            {"role": "system", "content": "You are an expert reviewer for task-specific SOPs. Revise only when needed."},
            {"role": "user", "content": prompt},
        ]

        response, usage = self.client.chat(messages, ModelSettings(temperature=0.2, max_tokens=4000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/SkillReview] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal_dict = self._extract_json(response)
        if not proposal_dict:
            return draft_skill
        reviewed = self._normalize_skill_proposal(case, analysis, proposal_dict, tool_proposal, existing_skill_content)
        return reviewed

    def _format_known_failure_lessons(self, lessons: list[Skill]) -> str:
        """Render reusable failure lessons for skill review prompts."""
        return "\n\n".join(
            f"- {lesson.description or lesson.name}\nApplicability: {lesson.applicability_conditions or 'N/A'}\n{lesson.content.strip()}"
            for lesson in lessons
        )

    def _format_family_examples(self, cases: list[TaskCase]) -> str:
        lines: list[str] = []
        for index, example in enumerate(cases, start=1):
            dense = example.dense_caption() or "N/A"
            lines.append(
                f"{index}. case_id={example.case_id}; dense_caption={dense}; prompt={example.prompt}"
            )
        return "\n".join(lines) if lines else "1. current example only; dense_caption=N/A"

    def generate_failure_skill(
        self,
        case: TaskCase,
        analysis: FailureAnalysis | None,
        result: AgentResult,
        existing_skill_content: str | None = None,
        chain_context: ToolChainContext | None = None,
        family_examples: list[TaskCase] | None = None,
    ) -> SkillProposal:
        """Generate a failure lesson skill that captures helpful methods without promoting it."""
        family_context = self._format_family_examples(family_examples or [case])
        prompt = f"""You are writing a short failure lesson for a task family.

Task family: {case.capability_family()}
Current question: {case.prompt}
Dense caption: {case.dense_caption() or "N/A"}
Expected answer: {case.gold_answer}
Agent answer: {result.final_answer}
Existing task-family SOP:
{existing_skill_content or "N/A"}
Current chain summary: {chain_context.summary() if chain_context else "No existing tool chain."}
Task-family examples seen so far:
{family_context}

Failure analysis:
- Root cause: {analysis.root_cause if analysis else "N/A"}
- Missing step: {analysis.missing_step if analysis else "N/A"}
- Rationale: {analysis.rationale if analysis else "N/A"}

Write a reusable lesson that captures:
- what tends to help on this task family
- what common mistake happened here
- what extra condition or extra step should be considered next time

IMPORTANT:
- This is a failure lesson, not the main promoted solver SOP.
- This lesson may later be shown to a real solver, so it must still be helpful even when no new tool was learned.
- Focus on reusable visual cues, geometric checks, intermediate verification steps, and branch conditions that would help solve similar cases next time.
- Ignore temporary tool registration, loading, promotion, or availability issues unless they reveal a genuine missing reasoning step. Do not center the lesson on missing tool names.
- Do not mention a concrete generated tool, validator outcome, runtime error, or evolve-only implementation detail. Abstract them into a general lesson the solver can use later.
- Keep it reusable across the task family.
- Do not include concrete file paths, exact example arithmetic, or the final answer of this example.
- Keep command placeholders generic.

Return JSON:
{{
  "name": "{case.capability_family()}",
  "description": "short description of the failure lesson",
  "applicability_conditions": "when this lesson is relevant",
  "content": "markdown lesson only",
  "level": "low",
  "depends_on": []
}}
"""
        messages = [
            {"role": "system", "content": "You are an expert at writing reusable failure lessons for evolving agents."},
            {"role": "user", "content": prompt},
        ]
        response, usage = self.client.chat(messages, ModelSettings(temperature=0.3, max_tokens=3000))
        self.total_usage = self.total_usage + usage
        print(f"  [Generator/FailureSkill] Tokens: {usage.total_tokens} (prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})")
        proposal_dict = self._extract_json(response)
        lesson = self._normalize_skill_proposal(
            case,
            analysis or FailureAnalysis(root_cause="unsolved case", next_action="give_up", confidence=0.0),
            proposal_dict,
            None,
            existing_skill_content,
        )
        lesson.description = self._normalize_failure_description(lesson.description, case)
        lesson.applicability_conditions = self._normalize_failure_applicability(
            lesson.applicability_conditions,
            case,
            analysis,
        )
        lesson.content = self._build_failure_lesson_content(
            case,
            analysis,
            result,
            lesson.content,
            chain_context,
            family_examples or [case],
        )
        return lesson

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Extract JSON from text."""
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _normalize_coverage_contract(
        self,
        target_family: str,
        target_cluster_ids: list[str],
        payload: dict[str, Any],
        fallback_action: str,
    ) -> CoverageContract:
        recommended_action = str(payload.get("recommended_action", "")).strip() or fallback_action
        if recommended_action not in {"generate_tool", "generate_skill", "generate_both", "generate_code_skill", "give_up"}:
            recommended_action = fallback_action
        return CoverageContract(
            target_family=str(payload.get("target_family", "")).strip() or target_family,
            target_cluster_ids=[str(item) for item in payload.get("target_cluster_ids", target_cluster_ids)],
            problem_pattern=str(payload.get("problem_pattern", "")).strip() or "Reusable family-level failure pattern.",
            supported_variations=[str(item).strip() for item in payload.get("supported_variations", []) if str(item).strip()],
            unsupported_variations=[str(item).strip() for item in payload.get("unsupported_variations", []) if str(item).strip()],
            forbidden_case_specific_assumptions=[
                str(item).strip() for item in payload.get("forbidden_case_specific_assumptions", []) if str(item).strip()
            ],
            primitive_category=str(payload.get("primitive_category", "")).strip() or "generic_visual_focus",
            tool_validation_scope=str(payload.get("tool_validation_scope", "cluster")).strip() in {"family"} and "family" or "cluster",
            recommended_action=recommended_action,  # type: ignore[arg-type]
            why_this_should_generalize=str(payload.get("why_this_should_generalize", "")).strip() or "Covers a repeated cluster-level pattern rather than a single example.",
        )

    def _format_coverage_contract(self, contract: CoverageContract | None) -> str:
        if contract is None:
            return "No coverage contract available."
        return (
            f"family={contract.target_family}; clusters={','.join(contract.target_cluster_ids) or 'N/A'}; "
            f"pattern={contract.problem_pattern or 'N/A'}; "
            f"supported={'; '.join(contract.supported_variations) or 'N/A'}; "
            f"unsupported={'; '.join(contract.unsupported_variations) or 'N/A'}; "
            f"forbidden={'; '.join(contract.forbidden_case_specific_assumptions) or 'N/A'}; "
            f"primitive_category={contract.primitive_category or 'N/A'}; "
            f"tool_validation_scope={contract.tool_validation_scope}; "
            f"recommended_action={contract.recommended_action}; "
            f"why={contract.why_this_should_generalize or 'N/A'}"
        )

    def _format_revision_brief(self, brief: RevisionBrief | None) -> str:
        if brief is None:
            return "No revision brief available."
        return (
            f"failure_type={brief.failure_type}; reason={brief.reason}; "
            f"evidence={'; '.join(brief.evidence) or 'N/A'}; "
            f"rewrite_requirements={'; '.join(brief.rewrite_requirements) or 'N/A'}; "
            f"banned_patterns={'; '.join(brief.banned_patterns) or 'N/A'}; "
            f"retry_action={brief.retry_action}"
        )

    def _normalize_tool_proposal(self, proposal_dict: dict[str, Any]) -> ToolProposal:
        """Normalize generator output into the runtime contract."""
        raw_name = str(proposal_dict.get("name", "unnamed_tool"))
        name = self._normalize_tool_name(raw_name)
        code = self._normalize_tool_code(str(proposal_dict.get("code", "")), name)
        usage_example = proposal_dict.get("usage_example") or f"python -m tools {name} <image_path>"

        return ToolProposal(
            name=name,
            description=str(proposal_dict.get("description", "")),
            applicability_conditions=self._sanitize_applicability(
                str(proposal_dict.get("applicability_conditions", "")) or proposal_dict.get("description", "") or "Use this tool when the current image or intermediate artifact still needs this specific transformation."
            ),
            code=code,
            usage_example=str(usage_example).replace("python learned/tools/", "python -m tools ").replace(".py", ""),
            expected_inputs=list(proposal_dict.get("expected_inputs", ["image_path"])),
            expected_outputs=list(proposal_dict.get("expected_outputs", [f"artifacts/{name}_output.png"])),
            primitive_category=str(proposal_dict.get("primitive_category", "")).strip(),
        )

    def _tool_skeleton_guidance(self, case: TaskCase, primitive_category: str) -> str:
        dataset_name = str(case.metadata.get("dataset_name", "")).strip().lower() if hasattr(case, "metadata") else ""
        if primitive_category == "chart_value_overlay" or dataset_name == "chartqa":
            return (
                "- Allowed flow: detect chart region -> detect bars/series geometry from the image -> draw overlay/labels -> save artifact.\n"
                "- The tool must not return numeric chart answers or perform dataset-specific scale lookup.\n"
                "- Avoid fixed pixel x/y positions, fixed axis ranges, hardcoded years/countries/categories, or hand-tuned threshold tables.\n"
                "- Prefer producing an overlay artifact that helps the solver read the chart manually."
            )
        if dataset_name == "mathvista":
            return (
                "- Allowed flow: highlight/count candidate objects, mark relative positions, or crop a localized evidence region -> save artifact.\n"
                "- The tool must not solve geometry, arithmetic, or multiple-choice reasoning inside code.\n"
                "- Avoid age/angle/count answer literals, absolute coordinates, and any one-image layout assumptions."
            )
        if primitive_category in {"localized_color_focus", "localized_text_zoom"}:
            return (
                "- Allowed flow: isolate a local region, boost contrast/zoom, or mark candidate regions -> save artifact.\n"
                "- The tool must not map visual evidence directly to final answer options."
            )
        if primitive_category == "relative_position_marker":
            return (
                "- Allowed flow: detect salient objects/regions, mark relative left-right or top-bottom relations, and save an annotated image.\n"
                "- The tool must not emit the final relational answer directly."
            )
        return (
            "- Keep the tool to one primitive visual transformation or annotation step.\n"
            "- Save an artifact that helps the solver reason, rather than solving the task in code."
        )

    def _tool_code_scaffold(self, case: TaskCase, primitive_category: str) -> str:
        dataset_name = str(case.metadata.get("dataset_name", "")).strip().lower() if hasattr(case, "metadata") else ""
        if primitive_category == "chart_value_overlay" or dataset_name == "chartqa":
            return """from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def _find_chart_region(image: np.ndarray) -> tuple[int, int, int, int]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = (0, 0, w, h)
    best_area = 0
    image_area = float(h * w)
    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = float(cw * ch)
        if area < image_area * 0.08:
            continue
        if area > best_area:
            best = (x, y, cw, ch)
            best_area = area
    return best

def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        overlay = image.copy()
        x, y, w, h = _find_chart_region(image)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), 2)
        # TODO: detect bar-like regions inside the chart box using relative geometry only.
        # TODO: draw generic overlays/labels that help a solver read values manually.
        output_path = "artifacts/chart_value_overlay_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
"""
        if dataset_name == "mathvista" or primitive_category == "relative_position_marker":
            return """from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def _candidate_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[int, int, int, int]] = []
    image_area = float(h * w)
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.01 or area > image_area * 0.8:
            continue
        boxes.append((x, y, bw, bh))
    return boxes

def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        overlay = image.copy()
        boxes = _candidate_regions(image)
        for x, y, w, h in boxes[:12]:
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # TODO: mark generic relative-position or evidence regions without computing the final answer.
        output_path = "artifacts/relative_position_marker_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
"""
        if primitive_category in {"localized_color_focus", "localized_text_zoom"} or dataset_name == "hrbench":
            return """from core.types import ToolResult
from tools.implementations.shared import load_image, save_image
import cv2
import numpy as np

def _proposal_regions(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.convertScaleAbs(cv2.magnitude(grad_x, grad_y))
    _, mask = cv2.threshold(mag, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = float(h * w)
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < image_area * 0.005 or area > image_area * 0.6:
            continue
        boxes.append((x, y, bw, bh))
    return boxes

def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        overlay = image.copy()
        for x, y, w, h in _proposal_regions(image)[:10]:
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (255, 200, 0), 2)
        # TODO: boost contrast or highlight a few candidate local regions generically.
        output_path = "artifacts/localized_focus_output.png"
        save_image(overlay, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
"""
        return """from core.types import ToolResult
from tools.implementations.shared import load_image, save_image

def run(image_path: str) -> ToolResult:
    try:
        image = load_image(image_path)
        output_path = "artifacts/generic_visual_focus_output.png"
        save_image(image, output_path)
        return ToolResult(status="ok", answer="", artifacts=[output_path])
    except Exception as exc:
        return ToolResult(status="error", answer="", error=str(exc))
"""

    def _normalize_tool_name(self, raw_name: str) -> str:
        normalized = re.sub(r"[^a-z0-9_]+", "_", raw_name.strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized or "unnamed_tool"

    def _normalize_tool_code(self, code: str, tool_name: str) -> str:
        normalized = code.replace("Path(__file__).parents[3]", "Path(__file__).parents[2]")
        if "python learned/tools/" in normalized:
            normalized = normalized.replace("python learned/tools/", "python -m tools ")

        has_run = bool(re.search(r"^def run\s*\(", normalized, re.MULTILINE))
        has_main = bool(re.search(r"^def main\s*\(", normalized, re.MULTILINE))
        if has_run and not has_main:
            normalized = normalized.rstrip() + f"""

def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python -m tools {tool_name} <image_path>")
        raise SystemExit(1)

    print(run(sys.argv[1]))

if __name__ == "__main__":
    main()
"""

        return normalized

    def _normalize_skill_proposal(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        proposal_dict: dict[str, Any],
        tool_proposal: ToolProposal | None,
        existing_skill_content: str | None,
    ) -> SkillProposal:
        """Normalize a generated skill into a short task rule the solver can execute."""
        description = self._sanitize_description(
            str(proposal_dict.get("description", "")).strip(),
            tool_proposal is not None,
        )
        raw_content = str(proposal_dict.get("content", "")).strip()
        applicability_conditions = self._sanitize_applicability(
            str(proposal_dict.get("applicability_conditions", "")).strip()
            or self._derive_skill_applicability(raw_content, analysis, existing_skill_content, tool_proposal)
        )
        level = str(proposal_dict.get("level", "mid"))
        depends_on = list(proposal_dict.get("depends_on", []))
        references = self._normalize_skill_references(proposal_dict.get("references", []))

        if tool_proposal is None:
            content = raw_content or self._build_plain_skill_content(analysis)
        else:
            content = self._build_tool_skill_content(case, raw_content, analysis, tool_proposal, existing_skill_content)

        return SkillProposal(
            name=case.capability_family(),
            description=description,
            applicability_conditions=applicability_conditions,
            content=content,
            level=level if level in {"foundation", "high", "mid", "low"} else "mid",
            depends_on=depends_on,
            references=references,
        )

    def _normalize_code_skill_proposal(
        self,
        case: TaskCase,
        analysis: FailureAnalysis,
        proposal_dict: dict[str, Any],
        existing_skill_content: str | None,
    ) -> SkillProposal:
        """Normalize a code-writing skill into a reusable temporary-edit SOP."""
        description = self._sanitize_description(
            str(proposal_dict.get("description", "")).strip(),
            False,
        )
        raw_content = str(proposal_dict.get("content", "")).strip()
        applicability_conditions = self._sanitize_applicability(
            str(proposal_dict.get("applicability_conditions", "")).strip()
            or self._derive_skill_applicability(raw_content, analysis, existing_skill_content, None)
        )
        level = str(proposal_dict.get("level", "mid"))
        depends_on = list(proposal_dict.get("depends_on", []))
        content = self._build_code_writing_skill_content(raw_content, analysis)

        return SkillProposal(
            name=case.capability_family(),
            description=description or "Use temporary Python image-editing code before answering when the raw chart contains distracting information.",
            applicability_conditions=applicability_conditions,
            content=content,
            level=level if level in {"foundation", "high", "mid", "low"} else "mid",
            depends_on=depends_on,
        )

    def _normalize_skill_references(self, raw_references: Any) -> list[SkillReferenceProposal]:
        """Normalize structured reference docs for progressive-disclosure skills."""
        if not isinstance(raw_references, list):
            return []
        references: list[SkillReferenceProposal] = []
        seen: set[str] = set()
        for item in raw_references:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            content = str(item.get("content", "")).strip()
            description = str(item.get("description", "")).strip()
            if not path or not content:
                continue
            if not path.startswith("references/") or not path.endswith(".md"):
                continue
            if path in seen:
                continue
            seen.add(path)
            references.append(
                SkillReferenceProposal(
                    path=path,
                    content=content,
                    description=description,
                )
            )
        return references

    def _build_mastery_skill_package(
        self,
        profile: MasteryProfile,
    ) -> tuple[str, list[SkillReferenceProposal]]:
        """Build a router skill plus branch detail docs from a mastery profile."""
        primary_sequence = profile.tool_sequence or ([profile.primary_tool] if profile.primary_tool else [])
        tool_branch_path = "references/tool_branch.md"
        fallback_path = "references/no_tool_fallback.md"
        tool_steps = []
        if primary_sequence:
            tool_steps.append(f"1. Use this branch only when the task matches the supported trigger conditions for `{primary_sequence[0]}`.")
            for index, tool_name in enumerate(primary_sequence, start=2):
                tool_steps.append(f"{index}. Run `{tool_name}` and inspect the returned artifact before answering.")
            tool_steps.append(f"{len(tool_steps) + 1}. Answer only after the artifact clearly supports the conclusion.")
        else:
            tool_steps.extend(
                [
                    "1. Use this branch only when the positive trigger conditions clearly match.",
                    "2. Apply the most suitable preset tool already confirmed by the mastery profile.",
                    "3. Answer only if the artifact materially clarifies the target evidence.",
                ]
            )
        if profile.bad_chain_patterns:
            tool_steps.append(f"{len(tool_steps) + 1}. Do not continue chaining tools if you hit: {'; '.join(profile.bad_chain_patterns)}.")

        fallback_steps = [
            "## Branch Goal",
            "Use direct visual reasoning when the tool branch is not clearly justified.",
            "",
            "## SOP",
            "1. Prefer this branch when the chart/scene lacks a clean localized cue for the tool path.",
            "2. Use direct reasoning if the problem requires combining multiple elements or the artifact stays ambiguous.",
            "3. Do not force tool use just because a tool is available.",
        ]
        if profile.negative_trigger_conditions:
            fallback_steps.append(f"4. Explicit avoid conditions: {'; '.join(profile.negative_trigger_conditions)}.")

        references = [
            SkillReferenceProposal(
                path=tool_branch_path,
                description="Primary tool-enabled branch for this mastery skill.",
                content="\n".join(
                    [
                        "## Branch Goal",
                        "Apply the tool-backed branch only for the supported pattern cluster.",
                        "",
                        "## SOP",
                        *tool_steps,
                    ]
                ),
            ),
            SkillReferenceProposal(
                path=fallback_path,
                description="No-tool or do-not-use fallback branch.",
                content="\n".join(fallback_steps),
            ),
        ]
        positive = "; ".join(profile.recommended_trigger_conditions or profile.common_success_signals) or "the task clearly matches the supported pattern"
        negative = "; ".join(profile.negative_trigger_conditions or profile.common_failure_signals) or "the tool path stays ambiguous"
        router = "\n".join(
            [
                "## Router",
                f"1. Positive trigger: {positive}.",
                f"2. Negative trigger: {negative}.",
                f"3. If the positive trigger clearly matches, see reference: {tool_branch_path}",
                f"4. If the negative trigger matches or the artifact would be inconclusive, see reference: {fallback_path}",
                "5. Do not improvise a new branch outside these references.",
            ]
        )
        return router, references

    def _build_plain_skill_content(self, analysis: FailureAnalysis) -> str:
        when_text = self._sanitize_context_text(analysis.missing_step or "When this exact task pattern appears.")
        then_text = "Then answer the original question using the corrected interpretation for this task family."
        still_text = self._sanitize_context_text(analysis.rationale or "State what remaining step is missing.")
        return "\n".join([
            "## SOP",
            f"1. Check whether this task matches: {when_text}",
            "2. Follow the task-specific steps before giving any final answer.",
            f"3. {then_text}",
            f"4. If still failing, {still_text}",
        ])

    def _build_code_writing_skill_content(self, raw_content: str, analysis: FailureAnalysis) -> str:
        """Build a reusable SOP for temporary Python image-editing code."""
        sections = self._extract_markdown_sections(raw_content)
        when_text = self._sanitize_context_text(
            sections.get("When this applies")
            or sections.get("When to Use")
            or analysis.missing_step
            or "When the question only needs a subset of the visual evidence."
        )
        code_hint = self._sanitize_context_text(
            sections.get("Editing plan")
            or analysis.skill_update_note
            or analysis.tool_goal
            or "Write temporary Python code that hides irrelevant regions and highlights or preserves only the evidence needed for the question."
        )
        still_text = self._sanitize_context_text(
            sections.get("If still failing")
            or analysis.rationale
            or "tighten the edit so only the needed evidence remains."
        )
        return "\n".join([
            "## SOP",
            f"1. Confirm this applies: {self._strip_bullet(when_text)}",
            "2. Extract the target evidence from the question, decide what visual content must be kept, and decide what should be hidden, weakened, cropped, or highlighted.",
            "3. Use bash to write and run temporary Python editing code on `<image_path>` or `<artifact_path>`, save a new edited image under `artifacts/`, and do not output the final answer from the code itself.",
            "4. Wait for the Observation, inspect the edited image, and answer the original question from that edited artifact. "
            f"If still failing, {self._strip_bullet(still_text)}. Keep this editing intent in mind: {self._strip_bullet(code_hint)}",
        ])

    def _build_tool_skill_content(
        self,
        case: TaskCase,
        raw_content: str,
        analysis: FailureAnalysis,
        tool_proposal: ToolProposal,
        existing_skill_content: str | None,
    ) -> str:
        sections = self._extract_markdown_sections(raw_content)
        fallback_when = sections.get("When this applies") or sections.get("When to Use") or analysis.missing_step or "When this task pattern appears."
        when_text = self._sanitize_context_text(fallback_when)
        still_text = self._sanitize_context_text(
            sections.get("If still failing") or analysis.rationale or "Explain what remaining transformation or computation is still missing."
        )
        generic_command = f"python -m tools {tool_proposal.name} <image_path>"
        prior_tools = self._extract_tool_names(existing_skill_content or "")

        if prior_tools and tool_proposal.name not in prior_tools:
            prior_chain = self._format_existing_chain(prior_tools)
            chained_command = f"python -m tools {tool_proposal.name} <artifact_path>"
            return "\n".join([
                "## SOP",
                f"1. Confirm this applies: {self._strip_bullet(when_text)}",
                f"2. Run the existing tool chain in order: {prior_chain}",
                f"3. Wait for the Observation, then use the newest artifact as the input to `{chained_command}`.",
                "4. Wait for the Observation again, then answer the original question using the final tool output instead of the raw image. "
                f"If still failing, {self._strip_bullet(still_text)}",
            ])

        return "\n".join([
            "## SOP",
            f"1. Confirm this applies: {self._strip_bullet(when_text)}",
            f"2. Run `{generic_command}`.",
            "3. Wait for the Observation, then use the tool output artifact or observation before giving any final answer.",
            "4. Answer the original question using the tool output instead of the raw image. "
            f"If still failing, {self._strip_bullet(still_text)}",
        ])

    def _extract_markdown_sections(self, content: str) -> dict[str, str]:
        """Extract simple markdown sections keyed by H2 heading."""
        sections: dict[str, str] = {}
        current: str | None = None
        buffer: list[str] = []

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                if current is not None and buffer:
                    sections[current] = "\n".join(buffer).strip()
                current = line[3:].strip()
                buffer = []
                continue
            if current is not None:
                buffer.append(line)

        if current is not None and buffer:
            sections[current] = "\n".join(buffer).strip()

        return sections

    def _strip_bullet(self, text: str) -> str:
        cleaned = " ".join(part.strip() for part in text.splitlines() if part.strip()).strip()
        if cleaned.startswith("- "):
            return cleaned[2:].strip()
        return cleaned

    def _sanitize_description(self, description: str, has_tool: bool) -> str:
        if not description:
            return "Use the validated tool before answering this task family." if has_tool else "Follow this task-family SOP before answering."
        cleaned = self._sanitize_context_text(description)
        if not cleaned or cleaned == description and self._looks_example_specific(description):
            return "Use the validated tool before answering this task family." if has_tool else "Follow this task-family SOP before answering."
        return cleaned

    def _sanitize_applicability(self, text: str) -> str:
        cleaned = self._sanitize_context_text(text)
        cleaned = cleaned.replace("tool command `python -m tools <tool_name> <image_path>`", "the relevant tool step")
        if not cleaned or self._looks_example_specific(cleaned):
            return "Use this only when the current image or intermediate artifact matches this task-specific visual condition."
        return cleaned

    def _derive_skill_applicability(
        self,
        raw_content: str,
        analysis: FailureAnalysis,
        existing_skill_content: str | None,
        tool_proposal: ToolProposal | None,
    ) -> str:
        sections = self._extract_markdown_sections(raw_content)
        when_text = sections.get("When this applies") or sections.get("When to Use") or analysis.missing_step or analysis.root_cause
        if existing_skill_content and tool_proposal:
            return self._sanitize_applicability(
                f"Use the existing tool path first, and add {tool_proposal.name} only when {when_text}"
            )
        return self._sanitize_applicability(when_text)

    def _sanitize_context_text(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"`?python(?:3)?\s+-m\s+tools\s+\S+\s+\S+`?", "tool command `python -m tools <tool_name> <image_path>`", cleaned)
        cleaned = re.sub(r"\b(?:datasets?|images?)\/[^\s`]+", "<image_path>", cleaned)
        cleaned = re.sub(r"\b\.\/[^\s`]+\.(?:png|jpg|jpeg|webp|gif)\b", "<image_path>", cleaned)
        cleaned = re.sub(r"\b\S+\.(?:png|jpg|jpeg|webp|gif)\b", "<image_path>", cleaned)
        cleaned = re.sub(r"\badd(?:ing)?\s+\d+\s+hours?(?:\s+and\s+\d+\s+minutes?)?", "answer the question-specific time offset", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d+\s+hours?(?:\s+and\s+\d+\s+minutes?)?\b", "the question-specific time offset", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\b\d{1,2}:\d{2}\b", "<time>", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if self._looks_example_specific(cleaned):
            return "Use the validated tool output to answer this task family."
        return cleaned

    def _normalize_failure_description(self, description: str, case: TaskCase) -> str:
        cleaned = self._sanitize_failure_text(description)
        if not cleaned:
            return f"Failure lesson for solving harder {case.problem_id} examples."
        return cleaned

    def _normalize_failure_applicability(
        self,
        applicability: str,
        case: TaskCase,
        analysis: FailureAnalysis | None,
    ) -> str:
        cleaned = self._sanitize_failure_text(applicability)
        if cleaned:
            return cleaned
        fallback = (analysis.missing_step if analysis else "") or (analysis.root_cause if analysis else "")
        cleaned_fallback = self._sanitize_failure_text(fallback)
        if cleaned_fallback:
            return cleaned_fallback
        return f"When a standard {case.problem_id} SOP still fails on a harder visual variation."

    def _build_failure_lesson_content(
        self,
        case: TaskCase,
        analysis: FailureAnalysis | None,
        result: AgentResult,
        raw_content: str,
        chain_context: ToolChainContext | None,
        family_examples: list[TaskCase],
    ) -> str:
        sections = self._extract_markdown_sections(raw_content)
        helpful_text = self._sanitize_failure_text(
            sections.get("Helpful method")
            or sections.get("Method")
            or (analysis.rationale if analysis else "")
            or self._default_failure_method(case, analysis, chain_context)
        )
        common_mistake = self._sanitize_failure_text(
            sections.get("Common mistake")
            or sections.get("Mistake")
            or (analysis.root_cause if analysis else "")
            or "The solver trusted an incomplete intermediate interpretation before checking the key visual constraints."
        )
        next_step = self._sanitize_failure_text(
            sections.get("Next time")
            or sections.get("Next")
            or (analysis.missing_step if analysis else "")
            or self._default_failure_next_step(case, analysis, family_examples)
        )

        if not helpful_text:
            helpful_text = self._default_failure_method(case, analysis, chain_context)
        if not common_mistake:
            common_mistake = "The solver followed an incomplete rule and skipped a necessary verification step."
        if not next_step:
            next_step = self._default_failure_next_step(case, analysis, family_examples)

        family_branch_hint = self._failure_family_branch_hint(case, family_examples)
        if family_branch_hint:
            next_step = f"{next_step} {family_branch_hint}".strip()

        return "\n".join(
            [
                "## SOP",
                "1. Recognize that the current task-family SOP was not sufficient for this example and identify the stable visual anchors before answering.",
                f"2. Helpful method: {helpful_text}",
                f"3. Common mistake: {common_mistake}",
                f"4. Next time, consider: {next_step}",
            ]
        )

    def _sanitize_failure_text(self, text: str) -> str:
        cleaned = self._sanitize_context_text(text or "")
        replacements = [
            (r"(?i)the agent failed because it tried to use a tool that wasn['’]?t registered\.?", "The solver relied on an unavailable intermediate step instead of reasoning from stable visual cues."),
            (r"(?i)the agent attempted to use a tool that wasn['’]?t registered\.?", "The solver relied on an unavailable intermediate step instead of checking the core visual cues."),
            (r"(?i)the agent attempted to call a non-existent tool '[^']+'", "The solver relied on an unavailable intermediate step instead of checking the image directly."),
            (r"(?i)unknown tool:?\s*[a-zA-Z0-9_]+", "an unavailable intermediate step"),
            (r"(?i)tool is marked untrusted due to hardcoded final answers", "an unreliable intermediate shortcut"),
            (r"(?i)tool wasn['’]?t registered", "the needed intermediate step was unavailable"),
            (r"(?i)tool was not registered", "the needed intermediate step was unavailable"),
            (r"(?i)tool unavailable", "an intermediate step was unavailable"),
            (r"(?i)non-existent tool", "unavailable intermediate step"),
            (r"(?i)use a valid tool", "use a reliable intermediate check"),
            (r"(?i)a generated tool failed", "the current procedure missed a reliable intermediate check"),
            (r"(?i)this tool failed", "the current procedure missed a reliable intermediate check"),
            (r"(?i)validator[^.]*", "an intermediate result was not trustworthy"),
        ]
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned)
        cleaned = re.sub(r"'[a-zA-Z0-9_]+'", "", cleaned)
        cleaned = re.sub(r"\b[a-z]+(?:_[a-z0-9]+){1,}\b", "the current procedure", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
        if not cleaned:
            return ""
        return cleaned + "."

    def _default_failure_method(
        self,
        case: TaskCase,
        analysis: FailureAnalysis | None,
        chain_context: ToolChainContext | None,
    ) -> str:
        combined = " ".join(
            filter(
                None,
                [
                    case.problem_id,
                    case.dense_caption() or "",
                    analysis.root_cause if analysis else "",
                    analysis.missing_step if analysis else "",
                    analysis.rationale if analysis else "",
                ],
            )
        ).lower()
        if any(token in combined for token in ["billiards", "pocket", "trajectory", "rail", "reflection", "arrow"]):
            base = "Start from the blue ball location, the arrow direction cue, and the true inner rail boundary, then trace the path segment by segment instead of guessing the final pocket."
        elif any(token in combined for token in ["mirror", "clock", "rotate", "upside", "orientation"]):
            base = "Normalize the image step by step and answer only from the latest trustworthy corrected view, not from the raw image."
        else:
            base = "Identify the most stable visual anchors first, then reason from them step by step before giving a final answer."
        if chain_context and chain_context.artifacts:
            return f"{base} Use intermediate artifacts as checks, but verify them against the original image before trusting them."
        return base

    def _default_failure_next_step(
        self,
        case: TaskCase,
        analysis: FailureAnalysis | None,
        family_examples: list[TaskCase],
    ) -> str:
        combined = " ".join(
            filter(
                None,
                [
                    case.problem_id,
                    case.dense_caption() or "",
                    analysis.missing_step if analysis else "",
                    analysis.rationale if analysis else "",
                ],
            )
        ).lower()
        if any(token in combined for token in ["billiards", "trajectory", "rail", "reflection", "arrow"]):
            return "Verify the initial direction, use only the first dark inner rail as the reflection boundary, and check every bounce against the reflection law before naming the final pocket."
        if any(token in combined for token in ["mirror", "clock", "rotate", "orientation", "upside"]):
            return "Explicitly check whether the current example only needs the original correction or needs an additional orientation step before reading the final answer."
        if len(family_examples) > 1:
            return "Check which branch of the task-family procedure applies to the current image instead of forcing the same final step on every example."
        return "Add the missing visual check or intermediate reasoning step before trusting the final answer."

    def _failure_family_branch_hint(self, case: TaskCase, family_examples: list[TaskCase]) -> str:
        dense_captions = [example.dense_caption() or "" for example in family_examples]
        unique_dense = [caption for caption in dense_captions if caption]
        if len(set(unique_dense)) > 1:
            return "Use the current image to decide which family variant applies before reusing the same fixed procedure."
        return ""

    def _looks_example_specific(self, text: str) -> bool:
        lowered = text.lower()
        example_markers = [
            "<image_path>",
            "<time>",
            "question-specific time offset",
        ]
        if any(marker in lowered for marker in example_markers):
            return True
        if re.search(r"\b\d+\b", lowered):
            return True
        return False

    def _extract_tool_names(self, content: str) -> list[str]:
        matches = re.findall(r"python(?:3)?\s+-m\s+tools\s+([a-zA-Z0-9_]+)\s+<(?:image|artifact)_path>", content)
        ordered: list[str] = []
        for name in matches:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _format_existing_chain(self, tool_names: list[str]) -> str:
        commands: list[str] = []
        for index, tool_name in enumerate(tool_names):
            placeholder = "<image_path>" if index == 0 else "<artifact_path>"
            commands.append(f"`python -m tools {tool_name} {placeholder}`")
        return " then ".join(commands)

    def _image_data_url(self, path: Path) -> str:
        return VLMClient.image_data_url(path)
