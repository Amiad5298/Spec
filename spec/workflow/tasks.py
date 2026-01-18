"""Task parsing and management for SPEC.

This module provides functions for parsing task lists from markdown files,
tracking task completion, and managing task state.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from spec.utils.logging import log_message


class TaskStatus(Enum):
    """Task completion status."""

    PENDING = "pending"
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    SKIPPED = "skipped"


class TaskCategory(Enum):
    """Task execution category for parallel execution."""

    FUNDAMENTAL = "fundamental"  # Must run sequentially
    INDEPENDENT = "independent"  # Can run in parallel


@dataclass
class Task:
    """Represents a single task from the task list.

    Attributes:
        name: Task name/description
        status: Current task status
        line_number: Line number in the task list file
        indent_level: Indentation level (for nested tasks)
        parent: Parent task name (if nested)
        category: Task execution category (fundamental or independent)
        dependency_order: Order for fundamental tasks (sequential execution)
        group_id: Group identifier for parallel tasks
        target_files: List of files this task should modify (predictive context)
    """

    name: str
    status: TaskStatus = TaskStatus.PENDING
    line_number: int = 0
    indent_level: int = 0
    parent: Optional[str] = None
    # Fields for parallel execution
    category: TaskCategory = TaskCategory.FUNDAMENTAL
    dependency_order: int = 0  # For fundamental tasks ordering
    group_id: Optional[str] = None  # For grouping parallel tasks
    # Predictive context - explicit file targeting
    target_files: list[str] = field(default_factory=list)


def _parse_task_metadata(
    lines: list[str], task_line_num: int
) -> tuple[TaskCategory, int, Optional[str], list[str]]:
    """Parse task metadata from comment lines above task.

    Searches backwards from the task line, skipping empty lines,
    to find metadata comments. This handles cases where LLMs
    insert blank lines between the comment and task for readability.

    Supports metadata formats:
    - <!-- category: fundamental, order: 1 -->
    - <!-- category: independent, group: ui -->
    - <!-- files: path/to/file1.py, path/to/file2.py -->

    Args:
        lines: All lines from task list
        task_line_num: Line number of the task (0-indexed)

    Returns:
        Tuple of (category, order, group_id, target_files)
    """
    # Default values
    category = TaskCategory.FUNDAMENTAL
    order = 0
    group_id = None
    target_files: list[str] = []

    # Collect all metadata content from comments above the task
    metadata_lines: list[str] = []

    # Look backwards from task line, collecting metadata comments
    search_line = task_line_num - 1
    while search_line >= 0:
        line_content = lines[search_line].strip()

        # Skip empty lines
        if not line_content:
            search_line -= 1
            continue

        # Check if it's a metadata comment
        if line_content.startswith("<!--") and "-->" in line_content:
            metadata_lines.append(line_content)
            search_line -= 1
            continue

        # Stop searching when we hit a non-empty, non-metadata line
        break

    # Parse all collected metadata
    for metadata_content in metadata_lines:
        # Parse category metadata
        if "category:" in metadata_content.lower():
            if "fundamental" in metadata_content.lower():
                category = TaskCategory.FUNDAMENTAL
                order_match = re.search(r'order:\s*(\d+)', metadata_content)
                if order_match:
                    order = int(order_match.group(1))
            elif "independent" in metadata_content.lower():
                category = TaskCategory.INDEPENDENT
                group_match = re.search(r'group:\s*(\w+)', metadata_content)
                if group_match:
                    group_id = group_match.group(1)

        # Parse files metadata
        # <!-- files: path/to/file1.py, path/to/file2.py -->
        files_match = re.search(r'files:\s*([^>]+)', metadata_content)
        if files_match:
            files_str = files_match.group(1).strip()
            # Handle trailing --> if present
            files_str = files_str.rstrip(' ->')
            # Split by comma and clean up each file path
            parsed_files = [f.strip() for f in files_str.split(',') if f.strip()]
            target_files.extend(parsed_files)

    return category, order, group_id, target_files


def parse_task_list(content: str) -> list[Task]:
    """Parse task list from markdown content with category metadata.

    Supports formats:
    - [ ] Task name (pending)
    - [x] Task name (complete)
    - [X] Task name (complete)
    - * [ ] Task name (alternate bullet)
    - - [ ] Task name (dash bullet)

    Also parses category metadata comments above tasks:
    - <!-- category: fundamental, order: N -->
    - <!-- category: independent, group: GROUP_NAME -->
    - <!-- files: path/to/file1.py, path/to/file2.py -->

    Args:
        content: Markdown content with task list

    Returns:
        List of Task objects
    """
    tasks: list[Task] = []
    lines = content.splitlines()

    # Pattern for task items: optional bullet, checkbox, task name
    # Captures: indent, checkbox state, task name
    pattern = re.compile(
        r"^(\s*)[-*]?\s*\[([xX ])\]\s*(.+)$",
        re.MULTILINE,
    )

    for line_num, line in enumerate(lines):
        match = pattern.match(line)
        if match:
            indent, checkbox, name = match.groups()
            indent_level = len(indent) // 2  # Assume 2-space indentation

            status = TaskStatus.COMPLETE if checkbox.lower() == "x" else TaskStatus.PENDING

            # Parse metadata from previous lines (category, order, group_id, target_files)
            category, order, group_id, target_files = _parse_task_metadata(lines, line_num)

            task = Task(
                name=name.strip(),
                status=status,
                line_number=line_num + 1,  # Convert to 1-based
                indent_level=indent_level,
                category=category,
                dependency_order=order,
                group_id=group_id,
                target_files=target_files,
            )

            # Set parent for nested tasks
            if indent_level > 0 and tasks:
                for prev_task in reversed(tasks):
                    if prev_task.indent_level < indent_level:
                        task.parent = prev_task.name
                        break

            tasks.append(task)
            log_message(f"Parsed task: {task.name} ({task.status.value}, {task.category.value})")

    log_message(f"Total tasks parsed: {len(tasks)}")
    return tasks


def get_pending_tasks(tasks: list[Task]) -> list[Task]:
    """Get list of pending (incomplete) tasks.

    Args:
        tasks: List of all tasks

    Returns:
        List of pending tasks
    """
    return [t for t in tasks if t.status == TaskStatus.PENDING]


def get_completed_tasks(tasks: list[Task]) -> list[Task]:
    """Get list of completed tasks.

    Args:
        tasks: List of all tasks

    Returns:
        List of completed tasks
    """
    return [t for t in tasks if t.status == TaskStatus.COMPLETE]


def mark_task_complete(
    tasklist_path: Path,
    task_name: str,
) -> bool:
    """Mark a task as complete in the task list file.

    Updates the checkbox from [ ] to [x] for the matching task.

    Args:
        tasklist_path: Path to task list file
        task_name: Name of task to mark complete

    Returns:
        True if task was found and marked
    """
    if not tasklist_path.exists():
        log_message(f"Task list file not found: {tasklist_path}")
        return False

    content = tasklist_path.read_text()
    lines = content.splitlines()
    modified = False

    # Pattern to match the specific task
    task_pattern = re.compile(
        rf"^(\s*[-*]?\s*)\[ \](\s*{re.escape(task_name)}\s*)$"
    )

    for i, line in enumerate(lines):
        match = task_pattern.match(line)
        if match:
            prefix, suffix = match.groups()
            lines[i] = f"{prefix}[x]{suffix}"
            modified = True
            log_message(f"Marked task complete: {task_name}")
            break

    if modified:
        tasklist_path.write_text("\n".join(lines) + "\n")
        return True

    log_message(f"Task not found in file: {task_name}")
    return False


def format_task_list(tasks: list[Task]) -> str:
    """Format tasks as markdown task list.

    Args:
        tasks: List of tasks

    Returns:
        Markdown formatted task list
    """
    lines = []
    for task in tasks:
        indent = "  " * task.indent_level
        checkbox = "[x]" if task.status == TaskStatus.COMPLETE else "[ ]"
        lines.append(f"{indent}- {checkbox} {task.name}")
    return "\n".join(lines)


def get_fundamental_tasks(tasks: list[Task]) -> list[Task]:
    """Get fundamental tasks sorted by dependency order with stable ordering.

    Sorting is done by:
    1. Explicit order flag: tasks with order > 0 come before order = 0 tasks
    2. dependency_order (explicit order from metadata)
    3. line_number (for stability when dependency_order is equal)

    This ensures tasks with explicit ordering (order > 0) are always executed
    before tasks with no explicit order (order = 0).

    Args:
        tasks: List of all tasks

    Returns:
        List of fundamental tasks sorted by (explicit_order_flag, dependency_order, line_number)
    """
    fundamental = [t for t in tasks if t.category == TaskCategory.FUNDAMENTAL]
    # Sort key: (0 if explicit order else 1, dependency_order, line_number)
    # This puts explicit order (>0) tasks first, then order=0 tasks
    return sorted(
        fundamental,
        key=lambda t: (0 if t.dependency_order > 0 else 1, t.dependency_order, t.line_number),
    )


def get_independent_tasks(tasks: list[Task]) -> list[Task]:
    """Get independent tasks (parallelizable).

    Args:
        tasks: List of all tasks

    Returns:
        List of independent tasks
    """
    return [t for t in tasks if t.category == TaskCategory.INDEPENDENT]


def get_pending_fundamental_tasks(tasks: list[Task]) -> list[Task]:
    """Get pending fundamental tasks sorted by order.

    Args:
        tasks: List of all tasks

    Returns:
        List of pending fundamental tasks sorted by dependency_order
    """
    return [t for t in get_fundamental_tasks(tasks) if t.status == TaskStatus.PENDING]


def get_pending_independent_tasks(tasks: list[Task]) -> list[Task]:
    """Get pending independent tasks.

    Args:
        tasks: List of all tasks

    Returns:
        List of pending independent tasks
    """
    return [t for t in get_independent_tasks(tasks) if t.status == TaskStatus.PENDING]


__all__ = [
    "TaskStatus",
    "TaskCategory",
    "Task",
    "parse_task_list",
    "get_pending_tasks",
    "get_completed_tasks",
    "mark_task_complete",
    "format_task_list",
    "get_fundamental_tasks",
    "get_independent_tasks",
    "get_pending_fundamental_tasks",
    "get_pending_independent_tasks",
]

