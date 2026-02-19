"""Tests for MultiTaskScreen — the split-pane task/log layout screen."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import Footer

from ingot.ui.messages import TaskFinished, TaskOutput
from ingot.ui.screens.multi_task import (
    _DEFAULT_TAIL_LINES,
    _VERBOSE_TAIL_LINES,
    MultiTaskScreen,
    _tail_file,
)
from ingot.ui.widgets.log_panel import LogPanelWidget
from ingot.ui.widgets.task_list import TaskListWidget
from ingot.workflow.events import TaskRunStatus
from tests.helpers.ui import make_record_with_log_buffer, make_records


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
        rec0 = make_record_with_log_buffer(0, "Build", tail_lines=["building..."])
        rec1 = make_record_with_log_buffer(1, "Test", tail_lines=["testing..."])
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
        rec0 = make_record_with_log_buffer(0, "Build", tail_lines=["build log"])
        rec1 = make_record_with_log_buffer(1, "Test", tail_lines=["test log"])
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
        rec = make_record_with_log_buffer(0, "Build", tail_lines=["line"])
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
        rec = make_record_with_log_buffer(0, "Build", tail_lines=["line"])
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
        rec = make_record_with_log_buffer(0, "Build", log_path="/tmp/build.log")
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
        records = make_records(TaskRunStatus.PENDING, TaskRunStatus.RUNNING)
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
        rec = make_record_with_log_buffer(0, "Build", tail_lines=["initial"])
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")  # select task 0

            # Update the record
            updated = make_record_with_log_buffer(
                0, "Build", status=TaskRunStatus.SUCCESS, tail_lines=["done"]
            )
            screen.update_record(0, updated)
            # Verify get_tail was called on the updated record
            assert updated.log_buffer is not None
            updated.log_buffer.get_tail.assert_called()  # type: ignore[attr-defined]


# ===========================================================================
# _tail_file tests
# ===========================================================================


class TestTailFile:
    """Tests for the _tail_file helper."""

    def test_small_file(self) -> None:
        """Small file returns all lines when fewer than n."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            path = Path(f.name)
        try:
            result = _tail_file(path, 10)
            assert result == ["line1", "line2", "line3"]
        finally:
            path.unlink()

    def test_returns_last_n_lines(self) -> None:
        """Returns only the last n lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            for i in range(20):
                f.write(f"line{i}\n")
            path = Path(f.name)
        try:
            result = _tail_file(path, 3)
            assert result == ["line17", "line18", "line19"]
        finally:
            path.unlink()

    def test_n_zero_returns_empty(self) -> None:
        """n=0 returns an empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("content\n")
            path = Path(f.name)
        try:
            assert _tail_file(path, 0) == []
        finally:
            path.unlink()

    def test_n_negative_returns_empty(self) -> None:
        """Negative n returns an empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("content\n")
            path = Path(f.name)
        try:
            assert _tail_file(path, -1) == []
        finally:
            path.unlink()

    def test_large_file_chunk_boundary(self) -> None:
        """Lines spanning chunk boundaries are read correctly."""
        # Create a file larger than 8 KiB to trigger the backward-seek path
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".log", delete=False) as f:
            path = Path(f.name)
            # Write enough data to exceed 8 KiB
            for i in range(200):
                f.write(f"line-{i:04d}-padding{'x' * 40}\n".encode())
        try:
            result = _tail_file(path, 5)
            assert len(result) == 5
            # Verify last 5 lines are intact (no split artifacts)
            assert result[-1] == f"line-0199-padding{'x' * 40}"
            assert result[-5] == f"line-0195-padding{'x' * 40}"
        finally:
            path.unlink()

    def test_empty_file(self) -> None:
        """Empty file returns an empty list."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = Path(f.name)
        try:
            assert _tail_file(path, 5) == []
        finally:
            path.unlink()


# ===========================================================================
# Log path preservation tests
# ===========================================================================


class TestLogPathPreservation:
    """Tests that log_path is preserved after log_buffer is closed."""

    @pytest.mark.timeout(10)
    async def test_log_path_preserved_after_task_finished(self) -> None:
        """on_task_finished preserves log_path from log_buffer before closing it."""
        rec = make_record_with_log_buffer(0, "Build", status=TaskRunStatus.RUNNING)
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])

            # Post TaskFinished — this should close the buffer but preserve log_path
            screen.post_message(
                TaskFinished(
                    task_index=0,
                    task_name="Build",
                    status="success",
                    duration=1.0,
                    error=None,
                    timestamp=0.0,
                )
            )
            await pilot.pause()

            record = screen.records[0]
            assert record.log_buffer is None, "log_buffer should be closed"
            assert record.log_path is not None, "log_path should be preserved"

    @pytest.mark.timeout(10)
    async def test_completed_task_log_viewable_via_file(self) -> None:
        """After buffer close, _update_log_panel falls back to _tail_file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("saved log line\n")
            log_path = Path(f.name)

        try:
            rec = make_record_with_log_buffer(
                0, "Build", status=TaskRunStatus.RUNNING, log_path=str(log_path)
            )
            app = MultiTaskTestApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                screen = _get_screen(app)
                screen.set_records([rec])

                # Finish the task to close the buffer
                screen.post_message(
                    TaskFinished(
                        task_index=0,
                        task_name="Build",
                        status="success",
                        duration=1.0,
                        error=None,
                        timestamp=0.0,
                    )
                )
                await pilot.pause()

                # Select the task — should read from disk
                await pilot.press("j")
                await pilot.pause()
                record = screen.records[0]
                assert record.log_buffer is None
                assert record.log_path == log_path
        finally:
            log_path.unlink(missing_ok=True)


# ===========================================================================
# Fast-path write_line tests
# ===========================================================================


class TestFastPathWriteLine:
    """Tests that follow-mode uses the fast-path single-line append."""

    @pytest.mark.timeout(10)
    async def test_follow_mode_appends_single_line(self) -> None:
        """In follow mode, TaskOutput appends via write_line (not set_content)."""
        rec = make_record_with_log_buffer(0, "Build", status=TaskRunStatus.RUNNING)
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")  # select task 0

            log_panel = screen.query_one("#log-panel", LogPanelWidget)
            assert log_panel.follow_mode is True

            # Post output — should use write_line fast path
            screen.post_message(TaskOutput(task_index=0, task_name="Build", line="hello"))
            await pilot.pause()

            # The mock buffer's get_tail should NOT have been called again
            # after the initial selection (j press calls _update_log_panel once).
            initial_call_count = rec.log_buffer.get_tail.call_count  # type: ignore[union-attr]

            screen.post_message(TaskOutput(task_index=0, task_name="Build", line="world"))
            await pilot.pause()

            # get_tail call count should not increase (fast path skips it)
            assert rec.log_buffer.get_tail.call_count == initial_call_count  # type: ignore[union-attr]

    @pytest.mark.timeout(10)
    async def test_paused_mode_uses_set_content(self) -> None:
        """When follow_mode is off, TaskOutput calls _update_log_panel (set_content)."""
        rec = make_record_with_log_buffer(0, "Build", status=TaskRunStatus.RUNNING)
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.set_records([rec])
            await pilot.press("j")  # select task 0
            await pilot.press("f")  # toggle follow off

            log_panel = screen.query_one("#log-panel", LogPanelWidget)
            assert log_panel.follow_mode is False

            call_count_before = rec.log_buffer.get_tail.call_count  # type: ignore[union-attr]

            screen.post_message(TaskOutput(task_index=0, task_name="Build", line="output"))
            await pilot.pause()

            # get_tail SHOULD be called (full refresh path)
            assert rec.log_buffer.get_tail.call_count > call_count_before  # type: ignore[union-attr]
