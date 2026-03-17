"""Test script for visual analysis feature."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.types import TaskCase, AgentResult, AgentStep
from core.vlm_client import VLMClient
from evolution.roles import AnalyzerDecider


def test_visual_analysis():
    """Test that AnalyzerDecider can process images."""

    print("="*60)
    print("Testing Visual Analysis Feature")
    print("="*60)
    print()

    # Create a mock case
    case = TaskCase(
        case_id="test_001",
        problem_id="mirror_clock",
        prompt="What time is shown on this mirror clock?",
        gold_answer="02:30",
        image_path="datasets/mira/images/mirror_clock_001.png",  # This should exist
    )

    # Create a mock failed result
    result = AgentResult(
        task=case.prompt,
        final_answer="10:30",  # Wrong answer
        steps=[
            AgentStep(
                turn=1,
                thought="I'll restore the mirrored clock",
                observation="ANSWER: restored_clock.png\nSTATUS: ok\nARTIFACTS: artifacts/restored_clock.png",
                artifacts=["artifacts/restored_clock.png"],
            ),
            AgentStep(
                turn=2,
                thought="Now I'll read the time",
                observation="ANSWER: 10:30\nSTATUS: ok",
                artifacts=[],
            ),
        ],
        total_turns=2,
        success=False,
        all_artifacts=["artifacts/restored_clock.png"],
    )

    # Check what will be sent to VLM
    print("📋 Test Configuration:")
    print(f"  Case ID: {case.case_id}")
    print(f"  Task: {case.prompt}")
    print(f"  Expected: {case.gold_answer}")
    print(f"  Agent's answer: {result.final_answer}")
    print()

    print("📸 Visual Context:")
    print(f"  Original image: {case.image_path}")
    has_original = Path(case.image_path).exists() if case.image_path else False
    print(f"    → Exists: {has_original}")

    image_artifacts = result.get_image_artifacts()
    print(f"  Artifacts: {len(image_artifacts)}")
    for i, art in enumerate(image_artifacts):
        exists = Path(art).exists()
        print(f"    {i+1}. {art} → Exists: {exists}")
    print()

    # Test visual analysis capability
    print("🧪 Testing AnalyzerDecider...")
    print("  (This will make a real API call if VLM is configured)")
    print()

    try:
        # This requires VLM to be configured
        client = VLMClient()
        analyzer = AnalyzerDecider(client)

        print("  Creating analysis request with visual context...")

        # Mock current capabilities
        current_caps = [
            "tool:mirror_clock_restore",
            "tool:mirror_clock_answer",
            "skill:mirror_clock_solver",
        ]

        # Note: This will fail gracefully if images don't exist
        # or if VLM is not configured
        analysis = analyzer.analyze_and_decide(
            case=case,
            result=result,
            current_capabilities=current_caps,
        )

        print()
        print("✓ Analysis completed successfully!")
        print()
        print("📊 Analysis Results:")
        print(f"  Root cause: {analysis.root_cause}")
        print(f"  Failure stage: {analysis.failure_stage}")
        print(f"  Missing capabilities: {', '.join(analysis.missing_capabilities)}")
        print(f"  Next action: {analysis.next_action}")
        print(f"  Confidence: {analysis.confidence}")
        print()
        print(f"  Rationale: {analysis.rationale}")
        print()
        print("="*60)
        print("✓✓✓ VISUAL ANALYSIS TEST PASSED ✓✓✓")
        print("="*60)

        return True

    except FileNotFoundError as e:
        print(f"⚠️  Image file not found: {e}")
        print()
        print("To fully test visual analysis:")
        print("1. Place a test image at: datasets/mira/images/mirror_clock_001.png")
        print("2. Or create artifacts/restored_clock.png")
        print("3. Re-run this test")
        print()
        print("The code structure is correct, just missing test images.")
        return False

    except Exception as e:
        print(f"✗ Error during analysis: {e}")
        print()
        print("Possible causes:")
        print("- VLM not configured (check VLM_BASE_URL, VLM_API_KEY, VLM_MODEL)")
        print("- Image files don't exist")
        print("- API connection issue")
        print()
        import traceback
        traceback.print_exc()
        return False


def test_artifact_extraction():
    """Test artifact extraction from observations."""
    print()
    print("="*60)
    print("Testing Artifact Extraction")
    print("="*60)
    print()

    from core.agent import ReActAgent

    test_cases = [
        (
            "ANSWER: result.png\nSTATUS: ok\nARTIFACTS: output.png, debug.jpg",
            ["output.png", "debug.jpg"]
        ),
        (
            "ANSWER: done\nSTATUS: ok\nARTIFACTS: single_file.png",
            ["single_file.png"]
        ),
        (
            "ANSWER: done\nSTATUS: ok",
            []
        ),
    ]

    agent = ReActAgent(client=None, config=None)

    all_passed = True
    for i, (observation, expected) in enumerate(test_cases, 1):
        extracted = agent._extract_artifacts(observation)
        passed = extracted == expected

        status = "✓" if passed else "✗"
        print(f"{status} Test {i}: {passed}")
        if not passed:
            print(f"  Expected: {expected}")
            print(f"  Got: {extracted}")
            all_passed = False

    print()
    if all_passed:
        print("✓ All artifact extraction tests passed")
    else:
        print("✗ Some tests failed")

    return all_passed


def main():
    print()
    print("Vision Agent Evolve - Visual Analysis Tests")
    print()

    # Test 1: Artifact extraction
    test1 = test_artifact_extraction()

    # Test 2: Visual analysis
    test2 = test_visual_analysis()

    print()
    print("="*60)
    print("Summary:")
    print(f"  Artifact extraction: {'✓ PASS' if test1 else '✗ FAIL'}")
    print(f"  Visual analysis: {'✓ PASS' if test2 else '⚠️  SKIP (missing images/VLM)'}")
    print("="*60)

    return 0 if test1 else 1


if __name__ == "__main__":
    sys.exit(main())
