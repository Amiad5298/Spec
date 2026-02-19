"""Step 1: Create Implementation Plan.

This module implements the first step of the workflow - creating
an implementation plan based on the Jira ticket.
"""

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from ingot.integrations.backends.base import AIBackend
from ingot.ui.menus import ReviewChoice, show_plan_review_menu
from ingot.ui.prompts import prompt_enter, prompt_input
from ingot.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
)
from ingot.utils.logging import log_message
from ingot.workflow.constants import MAX_REVIEW_ITERATIONS, noop_output_callback
from ingot.workflow.events import format_run_directory
from ingot.workflow.state import WorkflowState

# Robust ANSI/terminal escape sequence patterns (ECMA-48 compliant).
# Matches:
# - CSI sequences: \x1b[ followed by parameter bytes (0x30-0x3f, including ?),
#   intermediate bytes (0x20-0x2f), and a final byte (0x40-0x7e).
#   Examples: \x1b[32m (color), \x1b[?25l (hide cursor), \x1b[38;2;255;0;0m (24-bit color)
# - OSC sequences: \x1b] ... ST (terminated by \x1b\\ or \x07).
#   Examples: \x1b]0;title\x07 (set window title)
# - Character set designation: \x1b( or \x1b) followed by a charset ID.
#
# Known limitation: Does not match bare two-byte ESC sequences like \x1bM
# (reverse index) or \x1bc (terminal reset). These are rare in AI CLI output.
_ANSI_RE = re.compile(
    r"\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]"  # CSI sequences
    r"|\x1b\].*?(?:\x1b\\|\x07)"  # OSC sequences
    r"|\x1b[()][A-Z0-9]"  # Character set designation
)

# Matches <thinking>...</thinking> blocks (case-insensitive, multi-line).
_THINKING_BLOCK_RE = re.compile(
    r"<thinking>.*?</thinking>",
    re.DOTALL | re.IGNORECASE,
)

# Maximum character limits for replan prompt sections to keep prompt size reasonable.
_REPLAN_PLAN_EXCERPT_LIMIT = 4000
_REPLAN_FEEDBACK_EXCERPT_LIMIT = 3000

# Source-label constants used in prompts to tag data provenance.
_SOURCE_VERIFIED = "[SOURCE: VERIFIED PLATFORM DATA]"
_SOURCE_UNVERIFIED = "[SOURCE: NO VERIFIED PLATFORM DATA]"
_UNVERIFIED_NOTE = (
    "NOTE: The platform returned no verified content for this ticket. "
    'Do NOT reference "the ticket" as a source of requirements.'
)


# =============================================================================
# Log Directory Management
# =============================================================================


def _get_log_base_dir() -> Path:
    """Get the base directory for run logs."""
    env_dir = os.environ.get("INGOT_LOG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(".ingot/runs")


def _create_plan_log_dir(safe_ticket_id: str) -> Path:
    """Create a timestamped log directory for plan generation.

    safe_ticket_id MUST be sanitized (use ticket.safe_filename_stem) -
    raw ticket IDs may contain unsafe chars like '/'.
    """
    base_dir = _get_log_base_dir()
    plan_dir = base_dir / safe_ticket_id / "plan_generation"
    plan_dir.mkdir(parents=True, exist_ok=True)
    return plan_dir


# =============================================================================
# Plan Generation Functions
# =============================================================================


def _generate_plan_with_tui(
    state: WorkflowState,
    plan_path: Path,
    backend: AIBackend,
) -> tuple[bool, str]:
    """Generate plan with TUI progress display using subagent.

    Returns:
        Tuple of (success, captured_output).
    """
    from ingot.ui.inline_runner import InlineRunner

    # Create log directory and log path (use safe_filename_stem for paths)
    log_dir = _create_plan_log_dir(state.ticket.safe_filename_stem)
    log_path = log_dir / f"{format_run_directory()}.log"

    ui = InlineRunner(
        status_message="Generating implementation plan...",
        ticket_id=state.ticket.id,  # Keep original ID for display
    )
    ui.set_log_path(log_path)

    # Use plan_mode only for backends that map it to a CLI flag;
    # others (Auggie, Codex) can write the plan file directly.
    use_plan_mode = backend.supports_plan_mode

    # Build minimal prompt - agent has the instructions
    prompt = _build_minimal_prompt(state, plan_path, plan_mode=use_plan_mode)

    def _work() -> tuple[bool, str]:
        return backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["planner"],
            output_callback=ui.handle_output_line,
            dont_save_session=True,
            plan_mode=use_plan_mode,
        )

    success, output = ui.run_with_work(_work)

    # Check if user requested quit
    if ui.check_quit_requested():
        print_warning("Plan generation cancelled by user.")
        return False, ""

    ui.print_summary(success)
    return success, output


def _build_minimal_prompt(state: WorkflowState, plan_path: Path, *, plan_mode: bool = False) -> str:
    """Build minimal prompt for plan generation.

    The subagent has detailed instructions - we just pass context.

    Args:
        state: Current workflow state.
        plan_path: Path where the plan should be saved.
        plan_mode: If True, instruct the AI to output the plan to stdout
            instead of writing a file (for read-only backends).
    """
    source_label = _SOURCE_VERIFIED if state.spec_verified else _SOURCE_UNVERIFIED

    prompt = f"""Create implementation plan for: {state.ticket.id}

{source_label}
Ticket: {state.ticket.title or state.ticket.branch_summary or "Not available"}
Description: {state.ticket.description or "Not available"}"""

    if not state.spec_verified:
        prompt += f"\n{_UNVERIFIED_NOTE}"

    # Add user constraints if provided
    if state.user_constraints:
        prompt += f"""

[SOURCE: USER-PROVIDED CONSTRAINTS & PREFERENCES]
{state.user_constraints}"""

    if plan_mode:
        prompt += """

Output the complete implementation plan in Markdown format to stdout.
Do not attempt to create or write any files.

Codebase context will be retrieved automatically."""
    else:
        prompt += f"""

Save the plan to: {plan_path}

Codebase context will be retrieved automatically."""

    return prompt


def _extract_plan_markdown(output: str) -> str:
    """Extract clean markdown plan from CLI output.

    Strips ANSI escape codes, ``<thinking>`` blocks, tool-call logs,
    and other noise. Looks for the first markdown heading (any level)
    and returns everything from there. Falls back to full output if no
    headings found.

    Known limitation: Heading detection does not account for fenced code
    blocks — a ``# comment`` inside a code fence would be matched as a
    heading. This is low risk for typical plan output.
    """
    output = _ANSI_RE.sub("", output)
    output = _THINKING_BLOCK_RE.sub("", output)
    lines = output.splitlines()

    # Find first markdown heading (any level: #, ##, ###, etc.)
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith("#") and stripped.lstrip("#").startswith(" "):
            start_idx = i
            break

    # Strip trailing empty lines
    content = "\n".join(lines[start_idx:]).rstrip()
    return content if content else output.strip()


def step_1_create_plan(state: WorkflowState, backend: AIBackend) -> bool:
    """Execute Step 1: Create implementation plan.

    This step:
    1. Generates an implementation plan
    2. Saves the plan to specs/{ticket}-plan.md

    Note: Ticket information is already fetched in the workflow runner
    before this step is called. Clarification is handled separately
    in step 1.5 (step1_5_clarification.py).
    """
    print_header("Step 1: Create Implementation Plan")

    # Ensure specs directory exists
    state.specs_dir.mkdir(parents=True, exist_ok=True)

    # Display ticket information (already fetched earlier)
    if state.ticket.title:
        print_info(f"Ticket: {state.ticket.title}")
    if state.ticket.description:
        print_info(f"Description: {state.ticket.description[:200]}...")

    # Generate implementation plan using subagent
    print_step("Generating implementation plan...")
    plan_path = state.get_plan_path()

    success, output = _generate_plan_with_tui(state, plan_path, backend)

    if not success:
        print_error("Failed to generate implementation plan")
        return False

    # Check if plan file was created
    if not plan_path.exists():
        # Plan might be in output, save it
        print_info("Saving plan to file...")
        _save_plan_from_output(plan_path, state, output=output)

    if plan_path.exists():
        print_success(f"Implementation plan saved to: {plan_path}")
        state.plan_file = plan_path

        # Display plan summary
        _display_plan_summary(plan_path)

        # Plan review loop
        for _iteration in range(MAX_REVIEW_ITERATIONS):
            choice = show_plan_review_menu()

            if choice == ReviewChoice.APPROVE:
                state.current_step = 2
                return True

            elif choice == ReviewChoice.REGENERATE:
                feedback = prompt_input("What changes would you like?", default="")
                if not feedback or not feedback.strip():
                    print_warning("No feedback provided. Please describe what to change.")
                    continue

                state.plan_revision_count += 1
                if replan_with_feedback(state, backend, feedback):
                    _display_plan_summary(plan_path)
                    continue
                else:
                    print_error("Failed to regenerate plan. You can retry or edit manually.")
                    continue

            elif choice == ReviewChoice.EDIT:
                _edit_plan(plan_path)
                _display_plan_summary(plan_path)
                continue

            elif choice == ReviewChoice.ABORT:
                print_warning("Workflow aborted by user")
                return False
        else:
            print_warning(
                f"Maximum review iterations ({MAX_REVIEW_ITERATIONS}) reached. "
                "Please re-run the workflow."
            )
            return False
    else:
        print_error("Plan file was not created")
        return False


def _save_plan_from_output(plan_path: Path, state: WorkflowState, *, output: str = "") -> None:
    """Save plan from backend output if file wasn't created.

    When output is non-empty (plan mode backends output to stdout),
    sanitize and save the captured output. Falls back to a template
    when output is empty.
    """
    if output.strip():
        plan_content = _extract_plan_markdown(output)
        plan_path.write_text(plan_content)
        log_message(f"Saved plan from output at {plan_path}")
        return

    # Create a basic plan template if backend didn't create the file
    template = f"""# Implementation Plan: {state.ticket.id}

## Summary
{state.ticket.title or "Implementation task"}

## Description
{state.ticket.description or "No description was returned by the ticketing platform."}

## Implementation Steps
1. Review requirements
2. Implement changes
3. Write tests
4. Review and refactor

## Testing Strategy
- Unit tests for new functionality
- Integration tests as needed
- Manual verification

## Notes
Plan generated automatically. Please review and update as needed.
"""
    plan_path.write_text(template)
    log_message(f"Created template plan at {plan_path}")


def _display_plan_summary(plan_path: Path) -> None:
    """Display summary of the plan."""
    content = plan_path.read_text()
    lines = content.splitlines()

    # Show first 20 lines
    preview_lines = lines[:20]

    console.print()
    console.print("[bold]Plan Preview:[/bold]")
    console.print("-" * 40)
    for line in preview_lines:
        console.print(line)
    if len(lines) > len(preview_lines):
        console.print("...")
    console.print("-" * 40)
    console.print()


def _edit_plan(plan_path: Path) -> None:
    """Allow user to edit the plan file in their editor."""
    if not sys.stdin.isatty():
        print_warning("Cannot open editor: not running in a terminal")
        print_info(f"Edit the file manually: {plan_path}")
        prompt_enter("Press Enter when done editing...")
        return

    editor = os.environ.get("EDITOR", "vim")

    print_info(f"Opening plan in {editor}...")
    print_info("Save and close the editor when done.")

    try:
        editor_cmd = shlex.split(editor)
        subprocess.run([*editor_cmd, str(plan_path)], check=True)
        if plan_path.exists():
            print_success("Plan updated")
        else:
            print_warning(f"Plan file no longer exists at {plan_path}")
    except subprocess.CalledProcessError:
        print_warning("Editor exited with an error")
    except FileNotFoundError:
        print_error(f"Editor not found: {editor}")
        print_info(f"Edit the file manually: {plan_path}")
        prompt_enter("Press Enter when done editing...")


def _build_replan_prompt(
    state: WorkflowState,
    plan_path: Path,
    existing_plan: str,
    review_feedback: str,
) -> str:
    """Build the prompt for re-planning based on reviewer feedback.

    Args:
        state: Current workflow state.
        plan_path: Path where the plan should be saved.
        existing_plan: Current plan content (truncated for prompt size).
        review_feedback: Reviewer output explaining why replan is needed.
    """
    # Truncate to keep prompt reasonable
    plan_excerpt = existing_plan[:_REPLAN_PLAN_EXCERPT_LIMIT]
    if len(existing_plan) > _REPLAN_PLAN_EXCERPT_LIMIT:
        plan_excerpt += "\n\n... [truncated] ..."

    feedback_excerpt = review_feedback[:_REPLAN_FEEDBACK_EXCERPT_LIMIT]
    if len(review_feedback) > _REPLAN_FEEDBACK_EXCERPT_LIMIT:
        feedback_excerpt += "\n\n... [truncated] ..."

    ticket_source_label = _SOURCE_VERIFIED if state.spec_verified else _SOURCE_UNVERIFIED

    prompt = f"""Revise the implementation plan based on reviewer feedback.

## Ticket
{ticket_source_label}
ID: {state.ticket.id}
Title: {state.ticket.title or state.ticket.branch_summary or "Not available"}
Description: {state.ticket.description or "Not available"}"""

    if not state.spec_verified:
        prompt += f"\n{_UNVERIFIED_NOTE}"

    prompt += f"""

## Current Plan (needs revision)
{plan_excerpt}

## Reviewer Feedback
The reviewer determined the current plan is flawed and needs revision:
{feedback_excerpt}

## Instructions
1. Analyze the reviewer's feedback carefully
2. Identify what needs to change in the plan
3. Write a revised implementation plan that addresses the reviewer's concerns
4. Save the revised plan to: {plan_path}

Codebase context will be retrieved automatically."""

    if state.user_constraints:
        prompt += f"""

[SOURCE: USER-PROVIDED CONSTRAINTS & PREFERENCES]
{state.user_constraints}"""

    return prompt


def replan_with_feedback(
    state: WorkflowState,
    backend: AIBackend,
    review_feedback: str,
) -> bool:
    """Re-generate the implementation plan based on reviewer feedback.

    Reads the existing plan, combines it with reviewer feedback, and asks
    the planner subagent to produce a revised plan.

    Args:
        state: Current workflow state.
        backend: AI backend for agent calls.
        review_feedback: The reviewer's output explaining why replan is needed.

    Returns:
        True if plan was successfully updated, False otherwise.
    """
    print_header("Re-planning: Revising Implementation Plan")

    plan_path = state.get_plan_path()

    # Read existing plan and create backup before overwriting
    existing_plan = ""
    if plan_path.exists():
        existing_plan = plan_path.read_text()
        backup_idx = state.replan_count + state.plan_revision_count
        backup_path = plan_path.with_suffix(f".pre-replan-{backup_idx}.md")
        backup_path.write_text(existing_plan)
        log_message(f"Backed up previous plan to {backup_path}")

    # Build replan prompt
    use_plan_mode = backend.supports_plan_mode
    prompt = _build_replan_prompt(state, plan_path, existing_plan, review_feedback)

    if use_plan_mode:
        prompt += """

Output the complete revised implementation plan in Markdown format to stdout.
Do not attempt to create or write any files."""

    # Run the planner subagent
    # dont_save_session=True: Replan attempts are transient and should not
    # pollute the session history, which is reserved for the main plan run.
    print_step("Generating revised implementation plan...")
    try:
        success, output = backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["planner"],
            output_callback=noop_output_callback,
            dont_save_session=True,
            plan_mode=use_plan_mode,
        )
    except Exception as e:
        print_error(f"Re-planning failed: {e}")
        return False

    if not success:
        print_error("Re-planning agent returned failure")
        return False

    # Handle plan mode output (save from stdout)
    if not plan_path.exists() or use_plan_mode:
        if output.strip():
            plan_content = _extract_plan_markdown(output)
            plan_path.write_text(plan_content)
            log_message(f"Saved revised plan from output at {plan_path}")

    if plan_path.exists():
        print_success(f"Revised plan saved to: {plan_path}")
        state.plan_file = plan_path
        _display_plan_summary(plan_path)
        return True
    else:
        print_error("Revised plan file was not created")
        return False


__all__ = [
    "replan_with_feedback",
    "step_1_create_plan",
]
