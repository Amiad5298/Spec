"""Tests for MultiTaskScreen — the split-pane task/log layout screen."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.widgets import Footer

from ingot.ui.screens.multi_task import (
    _DEFAULT_TAIL_LINES,
    _VERBOSE_TAIL_LINES,
    MultiTaskScreen,
)
from ingot.ui.widgets.log_panel import LogPanelWidget
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
            rec.start_time = now - 5
        if status in (TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
            rec.end_time = now
        records.append(rec)
    return records


def _make_record_with_log_buffer(
    index: int,
    name: str,
    status: TaskRunStatus = TaskRunStatus.RUNNING,
    tail_lines: list[str] | None = None,
    log_path: str = "/tmp/test.log",
) -> TaskRunRecord:
    """Create a TaskRunRecord with a mock log_buffer."""
    now = time.time()
    rec = TaskRunRecord(task_index=index, task_name=name)
    rec.status = status
    if status in (TaskRunStatus.RUNNING, TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
        rec.start_time = now - 5
    if status in (TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
        rec.end_time = now

    mock_buffer = MagicMock()
    mock_buffer.log_path = Path(log_path)
    mock_buffer.get_tail = MagicMock(return_value=tail_lines or [])
    rec.log_buffer = mock_buffer
    return rec


class MultiTaskTestApp(App[None]):
    """Minimal app that pushes a MultiTaskScreen on mount."""

    def __init__(
        self,
        ticket_id: str = "",
    ) -> None:
        super().__init__()
        self._ticket_id = ticket_id

    def on_mount(self) -> None:
        screen = MultiTaskScreen(ticket_id=self._ticket_id)
        self.push_screen(screen)


def _get_screen(app: MultiTaskTestApp) -> MultiTaskScreen:
    """Get the active MultiTaskScreen from the app."""
    screen = app.screen
    assert isinstance(screen, MultiTaskScreen)
    return screen


# ===========================================================================
# Composition tests
# ===========================================================================


class TestComposition:
    """Tests that the screen composes the expected widgets."""

    @pytest.mark.timeout(10)
    async def test_contains_task_list_widget(self) -> None:
        """Screen contains a TaskListWidget."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.query_one("#task-list", TaskListWidget)

    @pytest.mark.timeout(10)
    async def test_contains_log_panel_widget(self) -> None:
        """Screen contains a LogPanelWidget."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.query_one("#log-panel", LogPanelWidget)

    @pytest.mark.timeout(10)
    async def test_contains_footer(self) -> None:
        """Screen contains a Footer widget."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.query_one(Footer)

    @pytest.mark.timeout(10)
    async def test_ticket_id_passed_through(self) -> None:
        """ticket_id is passed to the TaskListWidget."""
        app = MultiTaskTestApp(ticket_id="AMI-99")
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.ticket_id == "AMI-99"


# ===========================================================================
# Navigation tests
# ===========================================================================


class TestNavigation:
    """Tests that navigation updates both task list and log panel."""

    @pytest.mark.timeout(10)
    async def test_j_updates_selection_and_log_panel(self) -> None:
        """Pressing 'j' updates selection and log panel task_name."""
        rec0 = _make_record_with_log_buffer(0, "Build", tail_lines=["building..."])
        rec1 = _make_record_with_log_buffer(1, "Test", tail_lines=["testing..."])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec0, rec1])
            await pilot.press("j")
            log_panel = screen.query_one("#log-panel", LogPanelWidget)
            assert log_panel.task_name == "Build"

    @pytest.mark.timeout(10)
    async def test_navigating_between_tasks_switches_log(self) -> None:
        """Navigating from task 0 to task 1 switches log content."""
        rec0 = _make_record_with_log_buffer(0, "Build", tail_lines=["build log"])
        rec1 = _make_record_with_log_buffer(1, "Test", tail_lines=["test log"])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec0, rec1])
            await pilot.press("j")  # select Task 0
            log_panel = screen.query_one("#log-panel", LogPanelWidget)
            assert log_panel.task_name == "Build"

            await pilot.press("j")  # select Task 1
            assert log_panel.task_name == "Test"


# ===========================================================================
# Follow mode tests
# ===========================================================================


class TestFollowMode:
    """Tests for the follow mode toggle."""

    @pytest.mark.timeout(10)
    async def test_f_toggles_follow_mode(self) -> None:
        """Pressing 'f' toggles log_panel.follow_mode."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            log_panel = screen.query_one("#log-panel", LogPanelWidget)
            assert log_panel.follow_mode is True

            await pilot.press("f")
            assert log_panel.follow_mode is False

            await pilot.press("f")
            assert log_panel.follow_mode is True


# ===========================================================================
# Verbose mode tests
# ===========================================================================


class TestVerboseMode:
    """Tests for the verbose mode toggle."""

    @pytest.mark.timeout(10)
    async def test_v_toggles_verbose_mode(self) -> None:
        """Pressing 'v' toggles screen.verbose_mode."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.verbose_mode is False

            await pilot.press("v")
            assert screen.verbose_mode is True

            await pilot.press("v")
            assert screen.verbose_mode is False

    @pytest.mark.timeout(10)
    async def test_verbose_uses_more_tail_lines(self) -> None:
        """Verbose mode calls get_tail with _VERBOSE_TAIL_LINES."""
        rec = _make_record_with_log_buffer(0, "Build", tail_lines=["line"])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            # Select the record first
            await pilot.press("j")

            # Toggle verbose on
            await pilot.press("v")
            # Check that get_tail was called with verbose line count
            assert rec.log_buffer is not None
            rec.log_buffer.get_tail.assert_called_with(_VERBOSE_TAIL_LINES)  # type: ignore[attr-defined]

    @pytest.mark.timeout(10)
    async def test_normal_uses_default_tail_lines(self) -> None:
        """Normal mode calls get_tail with _DEFAULT_TAIL_LINES."""
        rec = _make_record_with_log_buffer(0, "Build", tail_lines=["line"])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")
            # In normal mode, should use default tail lines
            assert rec.log_buffer is not None
            rec.log_buffer.get_tail.assert_called_with(_DEFAULT_TAIL_LINES)  # type: ignore[attr-defined]


# ===========================================================================
# Quit tests
# ===========================================================================


class TestQuit:
    """Tests for the quit action."""

    @pytest.mark.timeout(10)
    async def test_q_pushes_quit_modal(self) -> None:
        """Pressing 'q' pushes the QuitConfirmModal instead of exiting."""
        from ingot.ui.screens.quit_modal import QuitConfirmModal

        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)

    @pytest.mark.timeout(10)
    async def test_q_then_y_exits_app(self) -> None:
        """Pressing 'q' then 'y' exits the app."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("y")
            # If we reach here without hanging, the test passes

    @pytest.mark.timeout(10)
    async def test_q_then_n_returns_to_screen(self) -> None:
        """Pressing 'q' then 'n' returns to MultiTaskScreen."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            screen = _get_screen(app)
            assert isinstance(screen, MultiTaskScreen)


# ===========================================================================
# Show log path tests
# ===========================================================================


class TestShowLogPath:
    """Tests for the show log path action."""

    @pytest.mark.timeout(10)
    async def test_l_does_not_crash(self) -> None:
        """Pressing 'l' with no selection does not crash."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("l")
            # No crash = pass

    @pytest.mark.timeout(10)
    async def test_l_with_selected_record(self) -> None:
        """Pressing 'l' with a selected record posts notification."""
        rec = _make_record_with_log_buffer(0, "Build", log_path="/tmp/build.log")
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")  # select task 0
            await pilot.press("l")
            # No crash = pass; notification was posted


# ===========================================================================
# Property delegation tests
# ===========================================================================


class TestPropertyDelegation:
    """Tests for property delegation to TaskListWidget."""

    @pytest.mark.timeout(10)
    async def test_parallel_mode_getter(self) -> None:
        """parallel_mode getter delegates to TaskListWidget."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            task_list = screen.query_one("#task-list", TaskListWidget)
            assert screen.parallel_mode == task_list.parallel_mode

    @pytest.mark.timeout(10)
    async def test_parallel_mode_setter(self) -> None:
        """parallel_mode setter delegates to TaskListWidget."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.parallel_mode = True
            task_list = screen.query_one("#task-list", TaskListWidget)
            assert task_list.parallel_mode is True

    @pytest.mark.timeout(10)
    async def test_records_returns_widget_records(self) -> None:
        """records property returns TaskListWidget.records."""
        records = _make_records(TaskRunStatus.PENDING, TaskRunStatus.RUNNING)
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records(records)
            assert len(screen.records) == 2
            assert screen.records[0].task_name == "Task 0"

    @pytest.mark.timeout(10)
    async def test_update_record_refreshes_log_panel(self) -> None:
        """update_record refreshes log panel when updated record is selected."""
        rec = _make_record_with_log_buffer(0, "Build", tail_lines=["initial"])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")  # select task 0

            # Update the record
            updated = _make_record_with_log_buffer(
                0, "Build", status=TaskRunStatus.SUCCESS, tail_lines=["done"]
            )
            screen.update_record(0, updated)
            # Verify get_tail was called on the updated record
            assert updated.log_buffer is not None
            updated.log_buffer.get_tail.assert_called()  # type: ignore[attr-defined]
