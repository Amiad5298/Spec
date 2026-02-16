"""Code review utilities for Step 3 execution.

This module provides utilities for running code reviews during the
execution phase, including parsing review output, building review
prompts, and coordinating the review workflow with optional auto-fix.

Supports baseline-anchored diffs to ensure reviews only inspect changes
introduced by the current workflow, not pre-existing dirty changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from ingot.integrations.backends.base import AIBackend
from ingot.ui.prompts import prompt_confirm
from ingot.utils.console import (
    print_info,
    print_step,
    print_success,
    print_warning,
)
from ingot.workflow.git_utils import get_smart_diff, get_smart_diff_from_baseline

if TYPE_CHECKING:
    from ingot.workflow.state import WorkflowState


class ReviewStatus(Enum):
    """Status codes returned by the review parser."""

    PASS = "PASS"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


class ExitReason(Enum):
    """Why the review-fix loop terminated."""

    PASSED = "PASSED"
    EXHAUSTED = "EXHAUSTED"
    AUTOFIX_FAILED_INTERNAL = "AUTOFIX_FAILED_INTERNAL"
    VERIFY_FAILED = "VERIFY_FAILED"
    GIT_ERROR = "GIT_ERROR"
    NO_DIFF = "NO_DIFF"


@dataclass
class ReviewFixResult:
    """Result of the review-fix loop."""

    passed: bool
    exit_reason: ExitReason
    review_output: str = ""
    fix_attempts: int = 0
    max_attempts: int = 0


def parse_review_status(output: str) -> ReviewStatus:
    """Parse review status from agent output.

    Extracts the final status marker from review output. The canonical format is:
        **Status**: PASS
        **Status**: NEEDS_ATTENTION

    This parser is robust to multiple formats:
    - Canonical: **Status**: PASS or Status: PASS
    - Bullet form: - **PASS** - description or - **NEEDS_ATTENTION** - description
    - Standalone: **PASS** or NEEDS_ATTENTION on its own line near the end
    - Case variations (PASS, Pass, pass)
    - Multiple occurrences (uses last one as final verdict)
    - PASS in normal prose is NOT matched (avoids false positives)

    Args:
        output: Review agent output text

    Returns:
        ReviewStatus.PASS if review passed, ReviewStatus.NEEDS_ATTENTION if
        issues found, or ReviewStatus.NEEDS_ATTENTION if status cannot be
        determined (fail-safe)

    Examples:
        >>> parse_review_status("**Status**: PASS\\n\\nLooks good!")
        <ReviewStatus.PASS: 'PASS'>
        >>> parse_review_status("Status: NEEDS_ATTENTION\\n\\nIssues found")
        <ReviewStatus.NEEDS_ATTENTION: 'NEEDS_ATTENTION'>
        >>> parse_review_status("- **PASS** - Changes look good")
        <ReviewStatus.PASS: 'PASS'>
        >>> parse_review_status("Ambiguous output")
        <ReviewStatus.NEEDS_ATTENTION: 'NEEDS_ATTENTION'>
    """
    if not output or not output.strip():
        return ReviewStatus.NEEDS_ATTENTION

    # All status patterns we recognize, ordered by specificity
    # Each pattern captures the status keyword (PASS or NEEDS_ATTENTION)
    patterns = [
        # 1. Canonical format: **Status**: PASS or Status: PASS
        r"(?:\*\*)?Status(?:\*\*)?\s*:\s*(PASS|NEEDS_ATTENTION)",
        # 2. Bullet format: - **PASS** - ... or - **NEEDS_ATTENTION** - ...
        r"^-\s*\*\*(PASS|NEEDS_ATTENTION)\*\*\s*-",
        # 3. Bullet format without trailing dash: - **PASS** or - **NEEDS_ATTENTION**
        r"^-\s*\*\*(PASS|NEEDS_ATTENTION)\*\*\s*$",
    ]

    # Collect all matches with their positions
    all_matches: list[tuple[int, str]] = []

    for pattern in patterns:
        for match in re.finditer(pattern, output, re.IGNORECASE | re.MULTILINE):
            # Store (position, status)
            all_matches.append((match.end(), match.group(1).upper()))

    if all_matches:
        # Sort by position, use last match as final verdict
        all_matches.sort(key=lambda x: x[0])
        return ReviewStatus(all_matches[-1][1])

    # No explicit status marker found - check for standalone markers as fallback
    # Only in the last 500 chars to avoid false positives from prose
    tail = output[-500:] if len(output) > 500 else output

    # Fallback patterns for standalone markers (near end only)
    fallback_patterns = [
        # NEEDS_ATTENTION on its own line (more specific, check first)
        (r"(?:^|\n)\s*\*?\*?NEEDS_ATTENTION\*?\*?\s*(?:\n|$)", ReviewStatus.NEEDS_ATTENTION),
        # **PASS** on its own line
        (r"(?:^|\n)\s*\*\*PASS\*\*\s*(?:\n|$)", ReviewStatus.PASS),
        # PASS on its own line (but NOT "will PASS" or "PASS all tests")
        # Must be at line start or after sentence-ending punctuation
        (r"(?:^|\n)\s*PASS\s*(?:\n|$)", ReviewStatus.PASS),
    ]

    for pattern, status in fallback_patterns:
        if re.search(pattern, tail, re.IGNORECASE):
            return status

    # No clear marker found - default to NEEDS_ATTENTION (fail-safe)
    return ReviewStatus.NEEDS_ATTENTION


def build_review_prompt(
    state: WorkflowState,
    phase: str,
    diff_output: str,
    is_truncated: bool,
) -> str:
    """Build the prompt for the reviewer agent.

    Args:
        state: Current workflow state
        phase: Phase identifier for the review (e.g., "final")
        diff_output: Git diff output (full or stat-only)
        is_truncated: Whether diff was truncated due to size

    Returns:
        Formatted prompt string for the reviewer
    """
    plan_path = state.get_plan_path()

    prompt = f"""Review the code changes from the {phase} phase of implementation.

## Implementation Plan
File: {plan_path}
(Use codebase-retrieval to read relevant sections as needed)

## Code Changes
{diff_output}
"""

    if is_truncated:
        prompt += """
## Large Changeset Instructions
This is a large changeset. The diff above shows only the file summary.
Use `git diff -- <file_path>` to inspect specific files that need detailed review.
Focus on files most critical to the implementation plan.
"""

    # Add user-provided context if available
    user_context = state.user_context.strip() if state.user_context else ""
    if user_context:
        prompt += f"""
## Additional Context
{user_context}
"""

    prompt += """
## Review Instructions
1. Check that changes align with the implementation plan
2. Identify any issues, bugs, or missing functionality
3. Look for missing tests, error handling, or edge cases

## Output Format
End your review with one of these EXACT status lines:

**Status**: PASS

OR

**Status**: NEEDS_ATTENTION

If NEEDS_ATTENTION, list specific issues:
**Issues**:
1. [ISSUE_TYPE] Description of the issue
2. [ISSUE_TYPE] Description of the issue
...
"""

    return prompt


def _get_diff_for_review(state: WorkflowState) -> tuple[str, bool, bool]:
    """Get diff for review, using baseline if available.

    Uses baseline-anchored diff when diff_baseline_ref is set in state,
    otherwise falls back to legacy get_smart_diff() for backwards compatibility.

    Args:
        state: Current workflow state with optional diff_baseline_ref.

    Returns:
        Tuple of (diff_output, is_truncated, git_error).
    """
    if state.diff_baseline_ref:
        # Use baseline-anchored diff (recommended)
        return get_smart_diff_from_baseline(
            state.diff_baseline_ref,
            include_working_tree=True,  # Include uncommitted changes
        )
    else:
        # Fallback to legacy behavior (no baseline)
        return get_smart_diff()


def _display_review_issues(output: str) -> None:
    """Extract and display review issues from reviewer output.

    Looks for a structured **Issues**: section. Falls back to showing
    the last 10 non-status lines if no structured section is found.
    """
    # Try to extract structured issues section
    issues_match = re.search(
        r"\*\*Issues\*\*\s*:\s*\n((?:.*\n)*?)(?:\n\*\*|\Z)",
        output,
    )
    if issues_match:
        for line in issues_match.group(1).strip().splitlines():
            stripped = line.strip()
            if stripped:
                print_info(f"  {stripped}")
        return

    # Fallback: show last 10 non-empty, non-status lines
    lines = [
        ln.strip()
        for ln in output.splitlines()
        if ln.strip() and not re.match(r"^\*?\*?Status\*?\*?\s*:", ln.strip(), re.IGNORECASE)
    ]
    for line in lines[-10:]:
        print_info(f"  {line}")


def _run_review_fix_loop(
    state: WorkflowState,
    review_output: str,
    log_dir: Path,
    phase: str,
    backend: AIBackend,
) -> ReviewFixResult:
    """Run the review-fix loop up to max_review_fix_attempts times.

    Each iteration: (1) run auto-fix with the latest review feedback,
    (2) re-review the result. Stops early on PASS or if no diff remains.

    Args:
        state: Current workflow state (reads max_review_fix_attempts)
        review_output: Initial review feedback to fix
        log_dir: Directory for log files
        phase: Phase identifier for the review (e.g., "final")
        backend: AI backend instance for agent interactions

    Returns:
        ReviewFixResult with pass/fail status and attempt counts.
    """
    from ingot.workflow.autofix import run_auto_fix

    max_attempts = state.max_review_fix_attempts
    current_feedback = review_output

    if max_attempts <= 0:
        return ReviewFixResult(
            passed=False,
            exit_reason=ExitReason.EXHAUSTED,
            review_output=review_output,
            fix_attempts=0,
            max_attempts=max_attempts,
        )

    for attempt in range(1, max_attempts + 1):
        # --- FIX phase ---
        print_step(f"[AUTO-FIX {attempt}/{max_attempts}] Attempting fix for {phase} review...")
        fix_success = run_auto_fix(state, current_feedback, log_dir, backend)

        if not fix_success:
            print_warning(f"[AUTO-FIX {attempt}/{max_attempts}] Auto-fix reported failure")

        # --- VERIFY phase ---
        # Always verify, even after autofix failure — partial fixes may satisfy the reviewer
        print_step(f"[VERIFY {attempt}/{max_attempts}] Re-reviewing after fix...")

        diff_output, is_truncated, git_error = _get_diff_for_review(state)

        if git_error:
            print_warning("Could not retrieve git diff for verification")
            return ReviewFixResult(
                passed=False,
                exit_reason=ExitReason.GIT_ERROR,
                review_output=current_feedback,
                fix_attempts=attempt,
                max_attempts=max_attempts,
            )

        if not diff_output.strip():
            print_info("Working tree clean relative to baseline -- no changes remain")
            return ReviewFixResult(
                passed=True,
                exit_reason=ExitReason.NO_DIFF,
                review_output="",
                fix_attempts=attempt,
                max_attempts=max_attempts,
            )

        prompt = build_review_prompt(state, phase, diff_output, is_truncated)

        try:
            success, output = backend.run_with_callback(
                prompt,
                subagent=state.subagent_names["reviewer"],
                output_callback=lambda _line: None,
                dont_save_session=True,
            )
        except Exception as e:
            print_warning(f"Verification review failed: {e}")
            return ReviewFixResult(
                passed=False,
                exit_reason=ExitReason.VERIFY_FAILED,
                review_output=current_feedback,
                fix_attempts=attempt,
                max_attempts=max_attempts,
            )

        if not success:
            print_warning("Verification review returned failure")
            return ReviewFixResult(
                passed=False,
                exit_reason=ExitReason.VERIFY_FAILED,
                review_output=current_feedback,
                fix_attempts=attempt,
                max_attempts=max_attempts,
            )

        status = parse_review_status(output)

        if status == ReviewStatus.PASS:
            print_success(f"[VERIFY {attempt}/{max_attempts}] {phase.capitalize()} review: PASS")
            return ReviewFixResult(
                passed=True,
                exit_reason=ExitReason.PASSED,
                review_output=output,
                fix_attempts=attempt,
                max_attempts=max_attempts,
            )

        # NEEDS_ATTENTION — display issues and feed into next fix attempt
        print_warning(
            f"[VERIFY {attempt}/{max_attempts}] {phase.capitalize()} review: NEEDS_ATTENTION"
        )
        _display_review_issues(output)
        current_feedback = output

    # All attempts exhausted
    return ReviewFixResult(
        passed=False,
        exit_reason=ExitReason.EXHAUSTED,
        review_output=current_feedback,
        fix_attempts=max_attempts,
        max_attempts=max_attempts,
    )


def run_phase_review(
    state: WorkflowState,
    log_dir: Path,
    phase: str,
    *,
    backend: AIBackend,
) -> bool:
    """Run review checkpoint and optionally auto-fix.

    Executes the ingot-reviewer agent to validate completed work.
    If issues are found, offers the user the option to attempt
    automatic fixes using the implementer agent, and optionally
    re-run the review after fixes.

    Uses baseline-anchored diffs when available to ensure the review
    only inspects changes introduced by the current workflow, not
    pre-existing dirty changes.

    Args:
        state: Current workflow state
        log_dir: Directory for log files
        phase: Phase identifier for the review (e.g., "final")
        backend: AI backend instance for agent interactions

    Returns:
        True if review passed or user chose to continue,
        False if user explicitly chose to stop after failed review
    """
    print_step(f"Running {phase} phase review...")

    # Get smart diff using baseline if available
    diff_output, is_truncated, git_error = _get_diff_for_review(state)

    if git_error:
        # Git command failed - prompt user instead of silently skipping
        print_warning("Could not retrieve git diff for review")
        print_info("The review cannot inspect code changes without git diff output.")
        if prompt_confirm("Continue workflow without code review?", default=True):
            return True
        else:
            print_info("Workflow stopped by user (could not retrieve diff for review)")
            return False

    if not diff_output.strip():
        print_info("No changes to review")
        return True

    # Build prompt
    prompt = build_review_prompt(state, phase, diff_output, is_truncated)

    # Run review
    try:
        success, output = backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["reviewer"],
            output_callback=lambda _line: None,
            dont_save_session=True,
        )
    except Exception as e:
        print_warning(f"Review execution failed: {e}")
        print_info("Continuing workflow despite review failure")
        return True  # Continue workflow on review crash (advisory behavior)

    # Check if execution succeeded before parsing output
    if not success:
        print_warning("Review execution returned failure (exit code non-zero)")
        print_info("Review output may be incomplete or unreliable")
        # Treat as NEEDS_ATTENTION for decision-making, but allow user to continue
        if prompt_confirm("Continue workflow despite review execution failure?", default=True):
            return True
        else:
            print_info("Workflow stopped by user after review execution failure")
            return False

    # Parse review result using robust parser (only when execution succeeded)
    status = parse_review_status(output)

    if status == ReviewStatus.PASS:
        print_success(f"{phase.capitalize()} review: PASS")
        return True

    # Review found issues
    print_warning(f"{phase.capitalize()} review: NEEDS_ATTENTION")

    # Offer auto-fix loop when max_review_fix_attempts > 0
    if state.max_review_fix_attempts > 0:
        if prompt_confirm("Would you like to attempt auto-fix?", default=False):
            loop_result = _run_review_fix_loop(state, output, log_dir, phase, backend)
            if loop_result.passed:
                return True
            match loop_result.exit_reason:
                case ExitReason.EXHAUSTED:
                    print_info(
                        f"Auto-fix made {loop_result.fix_attempts} attempt(s) "
                        "but review issues remain."
                    )
                case ExitReason.GIT_ERROR:
                    print_info("Auto-fix aborted: could not retrieve git diff for verification.")
                case ExitReason.VERIFY_FAILED:
                    print_info(
                        f"Auto-fix attempt {loop_result.fix_attempts}: "
                        "verification review failed to execute."
                    )
                case ExitReason.NO_DIFF:
                    print_info(
                        "Working tree clean relative to baseline -- " "no changes remain after fix."
                    )
                case _:
                    pass

    # Ask user if they want to continue or stop
    if prompt_confirm("Continue workflow despite review issues?", default=True):
        return True
    else:
        print_info("Workflow stopped by user after review")
        return False


__all__ = [
    "ExitReason",
    "ReviewFixResult",
    "ReviewStatus",
    "build_review_prompt",
    "parse_review_status",
    "run_phase_review",
]
