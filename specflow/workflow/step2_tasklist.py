"""Step 2: Create Task List.

This module implements the second step of the workflow - creating
a task list from the implementation plan with user approval.
"""

import re
from pathlib import Path
from typing import Optional

from specflow.integrations.auggie import AuggieClient
from specflow.ui.menus import TaskReviewChoice, show_task_review_menu
from specflow.ui.prompts import prompt_confirm, prompt_enter
from specflow.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
)
from specflow.utils.logging import log_message
from specflow.workflow.state import WorkflowState
from specflow.workflow.tasks import parse_task_list, format_task_list


def step_2_create_tasklist(state: WorkflowState, auggie: AuggieClient) -> bool:
    """Execute Step 2: Create task list.

    This step:
    1. Reads the implementation plan
    2. Generates a task list from the plan
    3. Allows user to review and approve/edit/regenerate
    4. Saves the approved task list

    Args:
        state: Current workflow state
        auggie: Auggie CLI client

    Returns:
        True if task list was created and approved
    """
    print_header("Step 2: Create Task List")

    # Verify plan exists
    plan_path = state.get_plan_path()
    if not plan_path.exists():
        print_error(f"Implementation plan not found: {plan_path}")
        print_info("Please run Step 1 first to create the plan.")
        return False

    tasklist_path = state.get_tasklist_path()

    # Flag to control when generation happens
    # Only generate on first entry or after REGENERATE
    needs_generation = True

    # Task list approval loop
    while True:
        if needs_generation:
            # Generate task list
            print_step("Generating task list from plan...")

            if not _generate_tasklist(state, plan_path, tasklist_path):
                print_error("Failed to generate task list")
                if not prompt_confirm("Retry?", default=True):
                    return False
                continue

            # Successfully generated, don't regenerate unless explicitly requested
            needs_generation = False

        # Display task list
        _display_tasklist(tasklist_path)

        # Get user decision
        choice = show_task_review_menu()

        if choice == TaskReviewChoice.APPROVE:
            state.tasklist_file = tasklist_path
            state.current_step = 3
            print_success("Task list approved!")
            return True

        elif choice == TaskReviewChoice.REGENERATE:
            print_info("Regenerating task list...")
            needs_generation = True
            continue

        elif choice == TaskReviewChoice.EDIT:
            _edit_tasklist(tasklist_path)
            # Re-display after edit, but do NOT regenerate
            # needs_generation stays False
            continue

        elif choice == TaskReviewChoice.ABORT:
            print_warning("Workflow aborted by user")
            return False


def _extract_task_name_from_add_tasks_format(raw_name: str) -> str:
    """Extract clean task name from add_tasks tool output format.

    The add_tasks tool outputs tasks in this format:
    UUID:xxx NAME:Task Name DESCRIPTION:...

    This function extracts just the task name portion.

    Args:
        raw_name: Raw task name string from checkbox line

    Returns:
        Clean task name
    """
    # Check for add_tasks format: UUID:xxx NAME:... DESCRIPTION:...
    # Extract the NAME field content
    name_match = re.search(r'NAME:(.+?)(?:\s+DESCRIPTION:|$)', raw_name)
    if name_match:
        return name_match.group(1).strip()

    # Not add_tasks format, return as-is
    return raw_name.strip()


def _extract_category_from_prefix(task_name: str) -> tuple[Optional[str], str]:
    """Extract category from FUNDAMENTAL:/INDEPENDENT: prefix in task name.

    Args:
        task_name: Task name that may have a category prefix

    Returns:
        Tuple of (category_metadata, clean_task_name) where category_metadata
        is the HTML comment to add (or None if no prefix found), and
        clean_task_name is the task name with prefix removed.
    """
    # Check for FUNDAMENTAL: prefix (case-insensitive)
    fundamental_match = re.match(r'^FUNDAMENTAL:\s*(.+)$', task_name, re.IGNORECASE)
    if fundamental_match:
        return ("<!-- category: fundamental -->", fundamental_match.group(1).strip())

    # Check for INDEPENDENT: prefix (case-insensitive)
    independent_match = re.match(r'^INDEPENDENT:\s*(.+)$', task_name, re.IGNORECASE)
    if independent_match:
        return ("<!-- category: independent -->", independent_match.group(1).strip())

    # No category prefix found
    return (None, task_name)


def _extract_tasklist_from_output(output: str, ticket_id: str) -> Optional[str]:
    """Extract markdown checkbox task list from AI output.

    Finds all lines matching checkbox format, preserving category metadata comments
    and section headers for parallel execution support.

    Also handles:
    - add_tasks tool output format (UUID:xxx NAME:... DESCRIPTION:...)
    - FUNDAMENTAL:/INDEPENDENT: prefixes in task names (converts to metadata)

    Args:
        output: AI output text that may contain task list
        ticket_id: Ticket ID for the header

    Returns:
        Formatted task list content, or None if no tasks found
    """
    # Pattern for task items: optional indent, optional bullet, checkbox, task name
    task_pattern = re.compile(r"^(\s*)[-*]?\s*\[([xX ])\]\s*(.+)$")
    # Pattern for category metadata comments
    metadata_pattern = re.compile(r"^\s*<!--\s*category:\s*.+-->\s*$")
    # Pattern for section headers (## Fundamental Tasks, ## Independent Tasks, etc.)
    section_pattern = re.compile(r"^##\s+(Fundamental|Independent)\s+Tasks.*$", re.IGNORECASE)

    output_lines = output.splitlines()
    result_lines = [f"# Task List: {ticket_id}", ""]

    task_count = 0
    pending_metadata: list[str] = []  # Buffer for metadata before a task

    for line in output_lines:
        # Check for section headers
        if section_pattern.match(line):
            # Add blank line before section (if we have content)
            if len(result_lines) > 2:
                result_lines.append("")
            result_lines.append(line)
            pending_metadata = []  # Reset metadata buffer
            continue

        # Check for category metadata comments
        if metadata_pattern.match(line):
            pending_metadata.append(line.strip())
            continue

        # Check for task items
        task_match = task_pattern.match(line)
        if task_match:
            indent, checkbox, raw_task_name = task_match.groups()

            # Extract clean task name (handles add_tasks format)
            task_name = _extract_task_name_from_add_tasks_format(raw_task_name)

            # Extract category from prefix (FUNDAMENTAL:/INDEPENDENT:)
            category_metadata, clean_task_name = _extract_category_from_prefix(task_name)

            # Add category metadata if extracted from prefix
            if category_metadata:
                pending_metadata.append(category_metadata)

            # Add any pending metadata before this task
            for meta in pending_metadata:
                result_lines.append(meta)
            pending_metadata = []

            # Normalize indentation (2 spaces per level)
            indent_level = len(indent) // 2
            normalized_indent = "  " * indent_level
            checkbox_char = checkbox.lower()  # Normalize to lowercase
            result_lines.append(f"{normalized_indent}- [{checkbox_char}] {clean_task_name}")
            task_count += 1

    if task_count == 0:
        log_message("No checkbox tasks found in AI output")
        return None

    log_message(f"Extracted {task_count} tasks from AI output")
    return "\n".join(result_lines) + "\n"


def _generate_tasklist(
    state: WorkflowState,
    plan_path: Path,
    tasklist_path: Path,
) -> bool:
    """Generate task list from implementation plan using subagent.

    Captures AI output and persists the task list to disk, even if the AI
    does not create/write the file itself.

    Args:
        state: Current workflow state
        plan_path: Path to implementation plan
        tasklist_path: Path to save task list

    Returns:
        True if task list was generated and contains valid tasks
    """
    plan_content = plan_path.read_text()

    # Minimal prompt - subagent has detailed instructions
    prompt = f"""Generate task list for: {state.ticket.ticket_id}

Implementation Plan:
{plan_content}

Create an executable task list with FUNDAMENTAL and INDEPENDENT categories."""

    # Use subagent - model comes from agent definition
    auggie_client = AuggieClient()

    # Use run_print_with_output to capture AI output
    success, output = auggie_client.run_print_with_output(
        prompt,
        agent=state.subagent_names["tasklist"],
        dont_save_session=True,
    )

    if not success:
        log_message("Auggie command failed")
        return False

    # Try to extract and persist the task list from AI output
    tasklist_content = _extract_tasklist_from_output(output, state.ticket.ticket_id)

    if tasklist_content:
        # Ensure parent directory exists
        tasklist_path.parent.mkdir(parents=True, exist_ok=True)
        tasklist_path.write_text(tasklist_content)
        log_message(f"Wrote task list to {tasklist_path}")

        # Verify we can parse the tasks
        tasks = parse_task_list(tasklist_content)
        if not tasks:
            log_message("Warning: Written task list has no parseable tasks")
            _create_default_tasklist(tasklist_path, state)
    else:
        # No tasks extracted from output, check if AI wrote the file
        if tasklist_path.exists():
            # AI wrote file - verify it has tasks
            content = tasklist_path.read_text()
            tasks = parse_task_list(content)
            if not tasks:
                log_message("AI-created file has no parseable tasks, using default")
                _create_default_tasklist(tasklist_path, state)
        else:
            # Fall back to default template
            log_message("No tasks extracted and no file created, using default")
            _create_default_tasklist(tasklist_path, state)

    return tasklist_path.exists()


def _create_default_tasklist(tasklist_path: Path, state: WorkflowState) -> None:
    """Create a default task list template.

    Args:
        tasklist_path: Path to save task list
        state: Current workflow state
    """
    template = f"""# Task List: {state.ticket.ticket_id}

## Implementation Tasks

- [ ] [Core functionality implementation with tests]
- [ ] [Integration/API layer with tests]
- [ ] [Documentation updates]

## Notes
Tasks represent complete units of work, not micro-steps.
Each task should leave the codebase in a working state.
"""
    tasklist_path.write_text(template)
    log_message(f"Created default task list at {tasklist_path}")


def _display_tasklist(tasklist_path: Path) -> None:
    """Display the task list.

    Args:
        tasklist_path: Path to task list file
    """
    content = tasklist_path.read_text()
    tasks = parse_task_list(content)

    console.print()
    console.print("[bold]Task List:[/bold]")
    console.print("-" * 50)
    console.print(content)
    console.print("-" * 50)
    console.print(f"[dim]Total tasks: {len(tasks)}[/dim]")
    console.print()


def _edit_tasklist(tasklist_path: Path) -> None:
    """Allow user to edit the task list.

    Args:
        tasklist_path: Path to task list file
    """
    import os
    import subprocess

    editor = os.environ.get("EDITOR", "vim")

    print_info(f"Opening task list in {editor}...")
    print_info("Save and close the editor when done.")

    try:
        subprocess.run([editor, str(tasklist_path)], check=True)
        print_success("Task list updated")
    except subprocess.CalledProcessError:
        print_warning("Editor closed without saving")
    except FileNotFoundError:
        print_error(f"Editor not found: {editor}")
        print_info(f"Edit the file manually: {tasklist_path}")
        prompt_enter("Press Enter when done editing...")


__all__ = [
    "step_2_create_tasklist",
    "_generate_tasklist",
    "_extract_tasklist_from_output",
]

