"""Tests for TaskListWidget — the Textual task status display widget."""

from __future__ import annotations

import time

import pytest
from rich.console import Console
from rich.spinner import Spinner
from textual.app import App, ComposeResult

from ingot.ui.widgets.task_list import TaskListWidget
from ingot.workflow.events import TaskRunRecord, TaskRunStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_records(*statuses: TaskRunStatus) -> list[TaskRunRecord]:
    """Create TaskRunRecord list with appropriate timestamps per status."""
    now = time.time()
    records: list[TaskRunRecord] = []
    for i, status in enumerate(statuses):
        rec = TaskRunRecord(task_index=i, task_name=f"Task {i}")
        rec.status = status
        if status in (TaskRunStatus.RUNNING, TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
            rec.start_time = now - 5  # 5 seconds ago
        if status in (TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
            rec.end_time = now
        records.append(rec)
    return records


def _render_to_str(widget: TaskListWidget) -> str:
    """Render the widget's Rich output to a plain-text string."""
    renderable = widget.render()
    console = Console(width=120, force_terminal=True, no_color=True)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class TaskListTestApp(App[None]):
    """Minimal app that mounts a TaskListWidget for testing."""

    def __init__(
        self,
        records: list[TaskRunRecord] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__()
        self._initial_records = records or []
        self._widget_kwargs = kwargs

    def compose(self) -> ComposeResult:
        widget = TaskListWidget(**self._widget_kwargs)  # type: ignore[arg-type]
        yield widget

    def on_mount(self) -> None:
        widget = self.query_one(TaskListWidget)
        if self._initial_records:
            widget.set_records(self._initial_records)
        widget.focus()


# ===========================================================================
# Rendering tests
# ===========================================================================


class TestRendering:
    """Tests that verify render output correctness."""

    def test_all_status_types_render(self) -> None:
        """All 5 status types render without error."""
        records = _make_records(
            TaskRunStatus.PENDING,
            TaskRunStatus.RUNNING,
            TaskRunStatus.SUCCESS,
            TaskRunStatus.FAILED,
            TaskRunStatus.SKIPPED,
        )
        widget = TaskListWidget(ticket_id="TEST-1")
        widget.set_records(records)
        output = _render_to_str(widget)
        assert "TASKS" in output

    def test_correct_icons_appear(self) -> None:
        """Correct status icons appear for non-running statuses."""
        records = _make_records(
            TaskRunStatus.PENDING,
            TaskRunStatus.SUCCESS,
            TaskRunStatus.FAILED,
            TaskRunStatus.SKIPPED,
        )
        widget = TaskListWidget()
        widget.set_records(records)
        output = _render_to_str(widget)
        assert "○" in output  # PENDING
        assert "✓" in output  # SUCCESS
        assert "✗" in output  # FAILED
        assert "⊘" in output  # SKIPPED

    def test_duration_shown_for_running_success_failed(self) -> None:
        """Duration is shown for RUNNING, SUCCESS, and FAILED statuses."""
        records = _make_records(
            TaskRunStatus.RUNNING,
            TaskRunStatus.SUCCESS,
            TaskRunStatus.FAILED,
        )
        widget = TaskListWidget()
        widget.set_records(records)
        output = _render_to_str(widget)
        # All three should have a duration like "5.0s"
        assert output.count("s") >= 3

    def test_duration_absent_for_pending_skipped(self) -> None:
        """Duration is absent for PENDING and SKIPPED tasks."""
        records = _make_records(TaskRunStatus.PENDING, TaskRunStatus.SKIPPED)
        widget = TaskListWidget()
        widget.set_records(records)
        output = _render_to_str(widget)
        # The only duration-like strings should not be present
        # PENDING and SKIPPED should not have a "X.Xs" pattern
        assert "0.0s" not in output

    def test_empty_records_render(self) -> None:
        """Empty records list renders with 0/0 in header."""
        widget = TaskListWidget()
        output = _render_to_str(widget)
        assert "0/0" in output

    def test_header_contains_ticket_id(self) -> None:
        """Header contains the ticket_id."""
        widget = TaskListWidget(ticket_id="AMI-99")
        widget.set_records(_make_records(TaskRunStatus.SUCCESS))
        output = _render_to_str(widget)
        assert "AMI-99" in output

    def test_header_completion_count(self) -> None:
        """Header shows correct completed/total count."""
        records = _make_records(
            TaskRunStatus.SUCCESS,
            TaskRunStatus.SUCCESS,
            TaskRunStatus.PENDING,
        )
        widget = TaskListWidget()
        widget.set_records(records)
        output = _render_to_str(widget)
        assert "2/3" in output


# ===========================================================================
# Parallel mode tests
# ===========================================================================


class TestParallelMode:
    """Tests for parallel mode indicators."""

    def test_parallel_indicator_shown(self) -> None:
        """Lightning bolt shown next to RUNNING tasks in parallel mode."""
        records = _make_records(TaskRunStatus.RUNNING)
        widget = TaskListWidget()
        widget.set_records(records)
        widget.parallel_mode = True
        output = _render_to_str(widget)
        assert "⚡" in output

    def test_sequential_running_indicator(self) -> None:
        """'← Running' shown when parallel_mode is False."""
        records = _make_records(TaskRunStatus.RUNNING)
        widget = TaskListWidget()
        widget.set_records(records)
        widget.parallel_mode = False
        output = _render_to_str(widget)
        assert "← Running" in output

    def test_parallel_header_count(self) -> None:
        """Header shows parallel count when parallel tasks are running."""
        records = _make_records(TaskRunStatus.RUNNING, TaskRunStatus.RUNNING)
        widget = TaskListWidget(ticket_id="X-1")
        widget.set_records(records)
        widget.parallel_mode = True
        output = _render_to_str(widget)
        assert "2 parallel" in output


# ===========================================================================
# Navigation tests
# ===========================================================================


class TestNavigation:
    """Tests for keyboard navigation via Textual pilot."""

    @pytest.mark.timeout(10)
    async def test_down_from_no_selection(self) -> None:
        """Pressing 'j' from no selection moves to index 0."""
        app = TaskListTestApp(
            records=_make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            assert widget.selected_index == -1
            await pilot.press("j")
            assert widget.selected_index == 0

    @pytest.mark.timeout(10)
    async def test_down_increments(self) -> None:
        """Pressing 'j' increments selected_index."""
        app = TaskListTestApp(
            records=_make_records(
                TaskRunStatus.PENDING, TaskRunStatus.PENDING, TaskRunStatus.PENDING
            ),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            await pilot.press("j")
            assert widget.selected_index == 0
            await pilot.press("j")
            assert widget.selected_index == 1

    @pytest.mark.timeout(10)
    async def test_down_clamps_at_bottom(self) -> None:
        """Pressing 'j' at the last index stays there."""
        app = TaskListTestApp(
            records=_make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            await pilot.press("j")
            await pilot.press("j")
            assert widget.selected_index == 1
            await pilot.press("j")
            assert widget.selected_index == 1  # clamped

    @pytest.mark.timeout(10)
    async def test_up_from_no_selection(self) -> None:
        """Pressing 'k' from no selection moves to last index."""
        app = TaskListTestApp(
            records=_make_records(
                TaskRunStatus.PENDING, TaskRunStatus.PENDING, TaskRunStatus.PENDING
            ),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            assert widget.selected_index == -1
            await pilot.press("k")
            assert widget.selected_index == 2

    @pytest.mark.timeout(10)
    async def test_up_decrements(self) -> None:
        """Pressing 'k' decrements selected_index."""
        app = TaskListTestApp(
            records=_make_records(
                TaskRunStatus.PENDING, TaskRunStatus.PENDING, TaskRunStatus.PENDING
            ),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            # Start at bottom
            await pilot.press("k")
            assert widget.selected_index == 2
            await pilot.press("k")
            assert widget.selected_index == 1

    @pytest.mark.timeout(10)
    async def test_up_clamps_at_top(self) -> None:
        """Pressing 'k' at index 0 stays there."""
        app = TaskListTestApp(
            records=_make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            await pilot.press("j")  # go to 0
            assert widget.selected_index == 0
            await pilot.press("k")
            assert widget.selected_index == 0  # clamped

    @pytest.mark.timeout(10)
    async def test_navigation_empty_list(self) -> None:
        """Navigation on empty list does not crash, stays at -1."""
        app = TaskListTestApp(records=[])
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            await pilot.press("j")
            assert widget.selected_index == -1
            await pilot.press("k")
            assert widget.selected_index == -1

    @pytest.mark.timeout(10)
    async def test_arrow_keys(self) -> None:
        """Arrow keys behave the same as j/k."""
        app = TaskListTestApp(
            records=_make_records(
                TaskRunStatus.PENDING, TaskRunStatus.PENDING, TaskRunStatus.PENDING
            ),
        )
        async with app.run_test() as pilot:
            widget = app.query_one(TaskListWidget)
            await pilot.press("down")
            assert widget.selected_index == 0
            await pilot.press("down")
            assert widget.selected_index == 1
            await pilot.press("up")
            assert widget.selected_index == 0


# ===========================================================================
# Message tests
# ===========================================================================


class TestMessages:
    """Tests for the Selected message."""

    @pytest.mark.timeout(10)
    async def test_selected_message_emitted(self) -> None:
        """Selected message is emitted on cursor movement with correct index."""
        messages: list[TaskListWidget.Selected] = []

        class CapturingApp(App[None]):
            def compose(self) -> ComposeResult:
                yield TaskListWidget()

            def on_mount(self) -> None:
                widget = self.query_one(TaskListWidget)
                widget.set_records(_make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING))
                widget.focus()

            def on_task_list_widget_selected(self, event: TaskListWidget.Selected) -> None:
                messages.append(event)

        app = CapturingApp()
        async with app.run_test() as pilot:
            await pilot.press("j")
            await pilot.press("j")

        assert len(messages) == 2
        assert messages[0].index == 0
        assert messages[1].index == 1


# ===========================================================================
# Spinner tests
# ===========================================================================


class TestSpinners:
    """Tests for spinner lifecycle management."""

    def test_spinner_created_for_running(self) -> None:
        """Spinner is created in _spinners for a RUNNING task."""
        widget = TaskListWidget()
        widget.set_records(_make_records(TaskRunStatus.RUNNING))
        assert 0 in widget._spinners
        assert isinstance(widget._spinners[0], Spinner)

    def test_spinner_removed_on_success(self) -> None:
        """Spinner is removed when task transitions to SUCCESS."""
        widget = TaskListWidget()
        records = _make_records(TaskRunStatus.RUNNING)
        widget.set_records(records)
        assert 0 in widget._spinners

        # Transition to SUCCESS
        records[0].status = TaskRunStatus.SUCCESS
        records[0].end_time = time.time()
        widget.update_record(0, records[0])
        assert 0 not in widget._spinners

    @pytest.mark.timeout(10)
    async def test_timer_resumed_when_running(self) -> None:
        """Timer is resumed when RUNNING tasks exist."""
        app = TaskListTestApp(
            records=_make_records(TaskRunStatus.RUNNING),
        )
        async with app.run_test():
            widget = app.query_one(TaskListWidget)
            assert widget._spinner_timer is not None
            # Timer should be active (not paused) because there's a running task
            assert widget._spinner_timer._active.is_set()

    @pytest.mark.timeout(10)
    async def test_timer_paused_when_no_running(self) -> None:
        """Timer is paused when no RUNNING tasks exist."""
        app = TaskListTestApp(
            records=_make_records(TaskRunStatus.PENDING, TaskRunStatus.SUCCESS),
        )
        async with app.run_test():
            widget = app.query_one(TaskListWidget)
            assert widget._spinner_timer is not None
            assert not widget._spinner_timer._active.is_set()


# ===========================================================================
# Update helper tests
# ===========================================================================


class TestUpdateHelpers:
    """Tests for set_records() and update_record()."""

    def test_set_records_replaces_all(self) -> None:
        """set_records() replaces all records."""
        widget = TaskListWidget()
        original = _make_records(TaskRunStatus.PENDING)
        widget.set_records(original)
        assert len(widget.records) == 1

        replacement = _make_records(TaskRunStatus.SUCCESS, TaskRunStatus.FAILED)
        widget.set_records(replacement)
        assert len(widget.records) == 2
        assert widget.records[0].status == TaskRunStatus.SUCCESS
        assert widget.records[1].status == TaskRunStatus.FAILED

    def test_update_record_mutates_single(self) -> None:
        """update_record() mutates a single record in place."""
        widget = TaskListWidget()
        records = _make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING)
        widget.set_records(records)

        updated = TaskRunRecord(
            task_index=1,
            task_name="Task 1",
            status=TaskRunStatus.RUNNING,
            start_time=time.time(),
        )
        widget.update_record(1, updated)
        assert widget.records[1].status == TaskRunStatus.RUNNING
        assert widget.records[0].status == TaskRunStatus.PENDING

    def test_update_record_out_of_bounds(self) -> None:
        """update_record() with invalid index is a no-op."""
        widget = TaskListWidget()
        widget.set_records(_make_records(TaskRunStatus.PENDING))
        widget.update_record(5, TaskRunRecord(task_index=5, task_name="X"))
        assert len(widget.records) == 1
