"""Tests for ai_workflow.workflow.tasks module."""

import pytest
from pathlib import Path
from unittest.mock import patch

from ai_workflow.workflow.tasks import (
    TaskStatus,
    Task,
    parse_task_list,
    get_pending_tasks,
    get_completed_tasks,
    mark_task_complete,
    format_task_list,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_pending_value(self):
        """PENDING has correct value."""
        assert TaskStatus.PENDING.value == "pending"

    def test_complete_value(self):
        """COMPLETE has correct value."""
        assert TaskStatus.COMPLETE.value == "complete"


class TestTask:
    """Tests for Task dataclass."""

    def test_default_values(self):
        """Default values are set correctly."""
        task = Task(name="Test task")
        assert task.status == TaskStatus.PENDING
        assert task.line_number == 0
        assert task.indent_level == 0
        assert task.parent is None


class TestParseTaskList:
    """Tests for parse_task_list function."""

    def test_parses_pending_task(self):
        """Parses pending task with [ ]."""
        content = "- [ ] Task one"
        tasks = parse_task_list(content)
        
        assert len(tasks) == 1
        assert tasks[0].name == "Task one"
        assert tasks[0].status == TaskStatus.PENDING

    def test_parses_complete_task(self):
        """Parses complete task with [x]."""
        content = "- [x] Task one"
        tasks = parse_task_list(content)
        
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.COMPLETE

    def test_parses_uppercase_x(self):
        """Parses complete task with [X]."""
        content = "- [X] Task one"
        tasks = parse_task_list(content)
        
        assert tasks[0].status == TaskStatus.COMPLETE

    def test_parses_multiple_tasks(self):
        """Parses multiple tasks."""
        content = """- [ ] Task one
- [x] Task two
- [ ] Task three"""
        tasks = parse_task_list(content)
        
        assert len(tasks) == 3

    def test_parses_asterisk_bullet(self):
        """Parses task with * bullet."""
        content = "* [ ] Task one"
        tasks = parse_task_list(content)
        
        assert len(tasks) == 1
        assert tasks[0].name == "Task one"

    def test_parses_no_bullet(self):
        """Parses task without bullet."""
        content = "[ ] Task one"
        tasks = parse_task_list(content)
        
        assert len(tasks) == 1

    def test_parses_indented_tasks(self):
        """Parses indented (nested) tasks."""
        content = """- [ ] Parent task
  - [ ] Child task"""
        tasks = parse_task_list(content)
        
        assert len(tasks) == 2
        assert tasks[1].indent_level == 1
        assert tasks[1].parent == "Parent task"

    def test_ignores_non_task_lines(self):
        """Ignores lines that aren't tasks."""
        content = """# Header
Some text
- [ ] Actual task
More text"""
        tasks = parse_task_list(content)
        
        assert len(tasks) == 1


class TestGetPendingTasks:
    """Tests for get_pending_tasks function."""

    def test_returns_only_pending(self):
        """Returns only pending tasks."""
        tasks = [
            Task(name="Task 1", status=TaskStatus.PENDING),
            Task(name="Task 2", status=TaskStatus.COMPLETE),
            Task(name="Task 3", status=TaskStatus.PENDING),
        ]
        
        pending = get_pending_tasks(tasks)
        
        assert len(pending) == 2
        assert all(t.status == TaskStatus.PENDING for t in pending)


class TestGetCompletedTasks:
    """Tests for get_completed_tasks function."""

    def test_returns_only_completed(self):
        """Returns only completed tasks."""
        tasks = [
            Task(name="Task 1", status=TaskStatus.PENDING),
            Task(name="Task 2", status=TaskStatus.COMPLETE),
        ]
        
        completed = get_completed_tasks(tasks)
        
        assert len(completed) == 1
        assert completed[0].name == "Task 2"


class TestMarkTaskComplete:
    """Tests for mark_task_complete function."""

    def test_marks_task_complete(self, tmp_path):
        """Marks task as complete in file."""
        tasklist = tmp_path / "tasks.md"
        tasklist.write_text("- [ ] Task one\n- [ ] Task two\n")
        
        result = mark_task_complete(tasklist, "Task one")
        
        assert result is True
        content = tasklist.read_text()
        assert "[x] Task one" in content
        assert "[ ] Task two" in content

    def test_returns_false_for_missing_file(self, tmp_path):
        """Returns False when file doesn't exist."""
        tasklist = tmp_path / "nonexistent.md"
        
        result = mark_task_complete(tasklist, "Task one")
        
        assert result is False


class TestFormatTaskList:
    """Tests for format_task_list function."""

    def test_formats_pending_task(self):
        """Formats pending task correctly."""
        tasks = [Task(name="Task one", status=TaskStatus.PENDING)]
        
        result = format_task_list(tasks)
        
        assert result == "- [ ] Task one"

    def test_formats_complete_task(self):
        """Formats complete task correctly."""
        tasks = [Task(name="Task one", status=TaskStatus.COMPLETE)]
        
        result = format_task_list(tasks)
        
        assert result == "- [x] Task one"

    def test_formats_indented_task(self):
        """Formats indented task correctly."""
        tasks = [Task(name="Child task", indent_level=1)]

        result = format_task_list(tasks)

        assert result == "  - [ ] Child task"


class TestDeeplyNestedTasks:
    """Tests for deeply nested tasks (3+ levels)."""

    def test_parses_three_level_nesting(self):
        """Parses tasks with 3 levels of nesting."""
        content = """- [ ] Parent task
  - [ ] Child task
    - [ ] Grandchild task"""
        tasks = parse_task_list(content)

        assert len(tasks) == 3
        assert tasks[0].indent_level == 0
        assert tasks[1].indent_level == 1
        assert tasks[2].indent_level == 2
        assert tasks[1].parent == "Parent task"
        assert tasks[2].parent == "Child task"

    def test_parses_four_level_nesting(self):
        """Parses tasks with 4 levels of nesting."""
        content = """- [ ] Level 0
  - [ ] Level 1
    - [ ] Level 2
      - [ ] Level 3"""
        tasks = parse_task_list(content)

        assert len(tasks) == 4
        assert tasks[3].indent_level == 3
        assert tasks[3].parent == "Level 2"

    def test_formats_deeply_nested_tasks(self):
        """Formats deeply nested tasks correctly."""
        tasks = [
            Task(name="Level 0", indent_level=0),
            Task(name="Level 1", indent_level=1),
            Task(name="Level 2", indent_level=2),
            Task(name="Level 3", indent_level=3),
        ]

        result = format_task_list(tasks)

        assert "- [ ] Level 0" in result
        assert "  - [ ] Level 1" in result
        assert "    - [ ] Level 2" in result
        assert "      - [ ] Level 3" in result


class TestMixedIndentationStyles:
    """Tests for mixed indentation styles."""

    def test_parses_mixed_bullets(self):
        """Parses tasks with mixed bullet styles."""
        content = """- [ ] Dash task
* [ ] Asterisk task
[ ] No bullet task"""
        tasks = parse_task_list(content)

        assert len(tasks) == 3
        assert tasks[0].name == "Dash task"
        assert tasks[1].name == "Asterisk task"
        assert tasks[2].name == "No bullet task"

    def test_parses_mixed_checkbox_cases(self):
        """Parses tasks with mixed checkbox cases."""
        content = """- [x] Lowercase complete
- [X] Uppercase complete
- [ ] Pending task"""
        tasks = parse_task_list(content)

        assert len(tasks) == 3
        assert tasks[0].status == TaskStatus.COMPLETE
        assert tasks[1].status == TaskStatus.COMPLETE
        assert tasks[2].status == TaskStatus.PENDING


class TestEdgeCases:
    """Tests for edge cases."""

    def test_parses_empty_content(self):
        """Handles empty content."""
        tasks = parse_task_list("")
        assert tasks == []

    def test_parses_content_with_only_headers(self):
        """Handles content with only headers."""
        content = """# Header 1

## Header 2

Some text without tasks.
"""
        tasks = parse_task_list(content)
        assert tasks == []

    def test_parses_whitespace_only_content(self):
        """Handles content with only whitespace."""
        tasks = parse_task_list("   \n\n   \n")
        assert tasks == []

    def test_parses_task_with_special_characters(self):
        """Parses task with special characters in name."""
        content = "- [ ] Task with special: [brackets], (parens), {braces}, `backticks`"
        tasks = parse_task_list(content)

        assert len(tasks) == 1
        assert "[brackets]" in tasks[0].name
        assert "(parens)" in tasks[0].name
        assert "`backticks`" in tasks[0].name

    def test_parses_task_with_emojis(self):
        """Parses task with emojis in name."""
        content = "- [ ] Task with emoji 🎉 and 🚀"
        tasks = parse_task_list(content)

        assert len(tasks) == 1
        assert "🎉" in tasks[0].name
        assert "🚀" in tasks[0].name

    def test_parses_task_with_urls(self):
        """Parses task with URLs in name."""
        content = "- [ ] Review PR at https://github.com/org/repo/pull/123"
        tasks = parse_task_list(content)

        assert len(tasks) == 1
        assert "https://github.com/org/repo/pull/123" in tasks[0].name


class TestMarkTaskCompleteEdgeCases:
    """Tests for mark_task_complete edge cases."""

    def test_returns_false_when_task_not_found(self, tmp_path):
        """Returns False when task is not found in file."""
        tasklist = tmp_path / "tasks.md"
        tasklist.write_text("- [ ] Different task\n- [ ] Another task\n")

        result = mark_task_complete(tasklist, "Nonexistent task")

        assert result is False
        # File should be unchanged
        content = tasklist.read_text()
        assert "[ ] Different task" in content
        assert "[ ] Another task" in content

    def test_only_marks_exact_match(self, tmp_path):
        """Only marks the task with exact name match."""
        tasklist = tmp_path / "tasks.md"
        tasklist.write_text("- [ ] Task\n- [ ] Task with suffix\n- [ ] Prefix Task\n")

        result = mark_task_complete(tasklist, "Task")

        assert result is True
        content = tasklist.read_text()
        assert "[x] Task\n" in content
        assert "[ ] Task with suffix" in content
        assert "[ ] Prefix Task" in content

    def test_handles_already_complete_task(self, tmp_path):
        """Handles case when task is already complete."""
        tasklist = tmp_path / "tasks.md"
        tasklist.write_text("- [x] Already done\n- [ ] Not done\n")

        # Trying to mark already complete task returns False (no match for [ ])
        result = mark_task_complete(tasklist, "Already done")

        assert result is False

    def test_handles_special_regex_characters_in_task_name(self, tmp_path):
        """Handles special regex characters in task name."""
        tasklist = tmp_path / "tasks.md"
        tasklist.write_text("- [ ] Fix bug (issue #123)\n")

        result = mark_task_complete(tasklist, "Fix bug (issue #123)")

        assert result is True
        content = tasklist.read_text()
        assert "[x] Fix bug (issue #123)" in content

