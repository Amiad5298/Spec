"""Tests for Textual Message types and the TaskEvent bridge.

Covers:
- Message construction for all message types
- ``convert_task_event`` mapping from TaskEvent to Message
- MultiTaskScreen event handlers
- SingleOperationScreen event handlers
- ``post_task_event`` bridge (async and thread contexts)
"""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from textual.app import App

from ingot.ui.messages import (
    LivenessUpdate,
    QuitRequested,
    RunFinished,
    TaskFinished,
    TaskOutput,
    TaskStarted,
    convert_task_event,
    post_task_event,
)
from ingot.ui.screens.multi_task import MultiTaskScreen
from ingot.ui.screens.single_operation import SingleOperationScreen
from ingot.ui.widgets.single_operation import SingleOperationWidget
from ingot.workflow.events import (
    TaskEvent,
    TaskEventType,
    TaskRunRecord,
    TaskRunStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_records(*statuses: TaskRunStatus) -> list[TaskRunRecord]:
    """Create TaskRunRecord list with the given statuses."""
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
    status: TaskRunStatus = TaskRunStatus.PENDING,
    tail_lines: list[str] | None = None,
    log_path: str | None = None,
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
    effective_path = log_path or str(Path(tempfile.gettempdir()) / "test.log")
    mock_buffer.log_path = Path(effective_path)
    mock_buffer.get_tail = MagicMock(return_value=tail_lines or [])
    rec.log_buffer = mock_buffer
    return rec


class MultiTaskTestApp(App[None]):
    """Minimal app that pushes a MultiTaskScreen on mount."""

    def __init__(self, ticket_id: str = "") -> None:
        super().__init__()
        self._ticket_id = ticket_id

    def on_mount(self) -> None:
        screen = MultiTaskScreen(ticket_id=self._ticket_id)
        self.push_screen(screen)


class SingleOperationTestApp(App[None]):
    """Minimal app that pushes a SingleOperationScreen on mount."""

    def __init__(self, ticket_id: str = "", log_path: str = "") -> None:
        super().__init__()
        self._ticket_id = ticket_id
        self._log_path = log_path

    def on_mount(self) -> None:
        screen = SingleOperationScreen(
            ticket_id=self._ticket_id,
            log_path=self._log_path,
        )
        self.push_screen(screen)


def _get_multi_screen(app: MultiTaskTestApp) -> MultiTaskScreen:
    screen = app.screen
    assert isinstance(screen, MultiTaskScreen)
    return screen


def _get_single_screen(app: SingleOperationTestApp) -> SingleOperationScreen:
    screen = app.screen
    assert isinstance(screen, SingleOperationScreen)
    return screen


# ===========================================================================
# Message construction tests
# ===========================================================================


class TestMessageConstruction:
    """Verify all attributes on each Message subclass."""

    def test_task_started_attributes(self) -> None:
        msg = TaskStarted(task_index=2, task_name="Build", timestamp=100.0)
        assert msg.task_index == 2
        assert msg.task_name == "Build"
        assert msg.timestamp == 100.0

    def test_task_output_attributes(self) -> None:
        msg = TaskOutput(task_index=1, task_name="Test", line="OK")
        assert msg.task_index == 1
        assert msg.task_name == "Test"
        assert msg.line == "OK"

    def test_task_finished_attributes(self) -> None:
        msg = TaskFinished(
            task_index=0,
            task_name="Deploy",
            status="success",
            duration=3.5,
            error=None,
            timestamp=42.0,
        )
        assert msg.task_index == 0
        assert msg.task_name == "Deploy"
        assert msg.status == "success"
        assert msg.duration == 3.5
        assert msg.error is None
        assert msg.timestamp == 42.0

    def test_task_finished_timestamp_defaults_to_zero(self) -> None:
        msg = TaskFinished(task_index=0, task_name="X", status="success", duration=0.0)
        assert msg.timestamp == 0.0

    def test_task_finished_with_error(self) -> None:
        msg = TaskFinished(
            task_index=1,
            task_name="Lint",
            status="failed",
            duration=1.0,
            error="syntax error",
        )
        assert msg.error == "syntax error"

    def test_run_finished_attributes(self) -> None:
        msg = RunFinished(total=5, success=3, failed=1, skipped=1)
        assert msg.total == 5
        assert msg.success == 3
        assert msg.failed == 1
        assert msg.skipped == 1

    def test_quit_requested(self) -> None:
        msg = QuitRequested()
        assert isinstance(msg, QuitRequested)

    def test_liveness_update_attributes(self) -> None:
        msg = LivenessUpdate(line="compiling module X")
        assert msg.line == "compiling module X"


# ===========================================================================
# convert_task_event tests
# ===========================================================================


class TestConvertTaskEvent:
    """Tests for the convert_task_event mapping function."""

    def test_run_started_returns_none(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.RUN_STARTED,
            task_index=0,
            task_name="",
            timestamp=time.time(),
            data={"total_tasks": 3},
        )
        assert convert_task_event(event) is None

    def test_task_started(self) -> None:
        ts = time.time()
        event = TaskEvent(
            event_type=TaskEventType.TASK_STARTED,
            task_index=1,
            task_name="Build",
            timestamp=ts,
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskStarted)
        assert msg.task_index == 1
        assert msg.task_name == "Build"
        assert msg.timestamp == ts

    def test_task_output(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.TASK_OUTPUT,
            task_index=0,
            task_name="Test",
            timestamp=time.time(),
            data={"line": "PASS test_foo"},
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskOutput)
        assert msg.line == "PASS test_foo"

    def test_task_output_missing_data_defaults(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.TASK_OUTPUT,
            task_index=0,
            task_name="Test",
            timestamp=time.time(),
            data=None,
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskOutput)
        assert msg.line == ""

    def test_task_finished_success(self) -> None:
        ts = time.time()
        event = TaskEvent(
            event_type=TaskEventType.TASK_FINISHED,
            task_index=2,
            task_name="Deploy",
            timestamp=ts,
            data={"status": "success", "duration": 4.2, "error": None},
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskFinished)
        assert msg.status == "success"
        assert msg.duration == 4.2
        assert msg.error is None
        assert msg.timestamp == ts

    def test_task_finished_failed(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.TASK_FINISHED,
            task_index=0,
            task_name="Lint",
            timestamp=time.time(),
            data={"status": "failed", "duration": 1.0, "error": "oops"},
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskFinished)
        assert msg.status == "failed"
        assert msg.error == "oops"

    def test_task_finished_skipped(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.TASK_FINISHED,
            task_index=3,
            task_name="Docs",
            timestamp=time.time(),
            data={"status": "skipped", "duration": 0.0, "error": None},
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskFinished)
        assert msg.status == "skipped"

    def test_task_finished_missing_data_defaults(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.TASK_FINISHED,
            task_index=0,
            task_name="X",
            timestamp=time.time(),
            data=None,
        )
        msg = convert_task_event(event)
        assert isinstance(msg, TaskFinished)
        assert msg.status == "failed"
        assert msg.duration == 0.0

    def test_run_finished(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.RUN_FINISHED,
            task_index=0,
            task_name="",
            timestamp=time.time(),
            data={
                "total_tasks": 4,
                "success_count": 2,
                "failed_count": 1,
                "skipped_count": 1,
            },
        )
        msg = convert_task_event(event)
        assert isinstance(msg, RunFinished)
        assert msg.total == 4
        assert msg.success == 2
        assert msg.failed == 1
        assert msg.skipped == 1

    def test_run_finished_missing_data_defaults(self) -> None:
        event = TaskEvent(
            event_type=TaskEventType.RUN_FINISHED,
            task_index=0,
            task_name="",
            timestamp=time.time(),
            data=None,
        )
        msg = convert_task_event(event)
        assert isinstance(msg, RunFinished)
        assert msg.total == 0
        assert msg.success == 0


# ===========================================================================
# MultiTaskScreen handler tests
# ===========================================================================


class TestMultiTaskScreenHandlers:
    """Tests for MultiTaskScreen message handlers."""

    @pytest.mark.timeout(10)
    async def test_task_started_sets_running(self) -> None:
        """TaskStarted sets record status to RUNNING."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING)
            screen.set_records(records)

            ts = time.time()
            screen.post_message(TaskStarted(task_index=0, task_name="Task 0", timestamp=ts))
            await pilot.pause()

            assert screen.records[0].status == TaskRunStatus.RUNNING
            assert screen.records[0].start_time == ts

    @pytest.mark.timeout(10)
    async def test_task_output_writes_to_log_buffer(self) -> None:
        """TaskOutput writes to the record's log_buffer."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            rec = _make_record_with_log_buffer(0, "Build", status=TaskRunStatus.RUNNING)
            screen.set_records([rec])

            screen.post_message(TaskOutput(task_index=0, task_name="Build", line="compiling..."))
            await pilot.pause()

            rec.log_buffer.write.assert_called_with("compiling...")  # type: ignore[union-attr]

    @pytest.mark.timeout(10)
    async def test_task_output_no_crash_without_log_buffer(self) -> None:
        """TaskOutput does not crash when record has no log_buffer."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.RUNNING)
            screen.set_records(records)

            screen.post_message(TaskOutput(task_index=0, task_name="Task 0", line="output"))
            await pilot.pause()
            # No crash = pass

    @pytest.mark.timeout(10)
    async def test_task_finished_success(self) -> None:
        """TaskFinished with 'success' sets record status to SUCCESS."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.RUNNING)
            screen.set_records(records)

            screen.post_message(
                TaskFinished(task_index=0, task_name="Task 0", status="success", duration=2.5)
            )
            await pilot.pause()

            assert screen.records[0].status == TaskRunStatus.SUCCESS

    @pytest.mark.timeout(10)
    async def test_task_finished_failed(self) -> None:
        """TaskFinished with 'failed' sets record status and error."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.RUNNING)
            screen.set_records(records)

            screen.post_message(
                TaskFinished(
                    task_index=0,
                    task_name="Task 0",
                    status="failed",
                    duration=1.0,
                    error="boom",
                )
            )
            await pilot.pause()

            assert screen.records[0].status == TaskRunStatus.FAILED
            assert screen.records[0].error == "boom"

    @pytest.mark.timeout(10)
    async def test_task_finished_skipped(self) -> None:
        """TaskFinished with 'skipped' sets record status to SKIPPED."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.RUNNING)
            screen.set_records(records)

            screen.post_message(
                TaskFinished(task_index=0, task_name="Task 0", status="skipped", duration=0.0)
            )
            await pilot.pause()

            assert screen.records[0].status == TaskRunStatus.SKIPPED

    @pytest.mark.timeout(10)
    async def test_task_finished_closes_log_buffer(self) -> None:
        """TaskFinished closes the log buffer and sets it to None."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            rec = _make_record_with_log_buffer(0, "Build", status=TaskRunStatus.RUNNING)
            mock_buffer = rec.log_buffer
            screen.set_records([rec])

            screen.post_message(
                TaskFinished(task_index=0, task_name="Build", status="success", duration=1.0)
            )
            await pilot.pause()

            mock_buffer.close.assert_called_once()  # type: ignore[union-attr]
            assert screen.records[0].log_buffer is None

    @pytest.mark.timeout(10)
    async def test_task_finished_uses_timestamp_fallback(self) -> None:
        """TaskFinished uses msg.timestamp when start_time is None."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.RUNNING)
            records[0].start_time = None  # force no start_time
            screen.set_records(records)

            screen.post_message(
                TaskFinished(
                    task_index=0,
                    task_name="Task 0",
                    status="success",
                    duration=2.0,
                    timestamp=1000.0,
                )
            )
            await pilot.pause()

            assert screen.records[0].end_time == 1000.0

    @pytest.mark.timeout(10)
    async def test_run_finished_sets_completed_and_summary(self) -> None:
        """RunFinished sets screen.completed and stores the summary."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            assert screen.completed is False
            assert screen.run_summary is None

            screen.post_message(RunFinished(total=2, success=2, failed=0, skipped=0))
            await pilot.pause()

            assert screen.completed is True
            assert screen.run_summary is not None
            assert screen.run_summary.total == 2
            assert screen.run_summary.success == 2
            assert screen.run_summary.failed == 0
            assert screen.run_summary.skipped == 0

    @pytest.mark.timeout(10)
    async def test_parallel_auto_select_first_running(self) -> None:
        """In parallel mode, first TaskStarted auto-selects that task."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            screen.parallel_mode = True
            records = _make_records(TaskRunStatus.PENDING, TaskRunStatus.PENDING)
            screen.set_records(records)

            screen.post_message(
                TaskStarted(task_index=1, task_name="Task 1", timestamp=time.time())
            )
            await pilot.pause()

            task_list = screen.query_one("#task-list")
            assert task_list.selected_index == 1  # type: ignore[attr-defined]

    @pytest.mark.timeout(10)
    async def test_parallel_auto_switch_on_finish(self) -> None:
        """In parallel mode, finishing the selected task switches to next running."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            screen.parallel_mode = True
            records = _make_records(
                TaskRunStatus.PENDING,
                TaskRunStatus.PENDING,
                TaskRunStatus.PENDING,
            )
            screen.set_records(records)

            # Start tasks 0 and 2
            screen.post_message(
                TaskStarted(task_index=0, task_name="Task 0", timestamp=time.time())
            )
            await pilot.pause()
            screen.post_message(
                TaskStarted(task_index=2, task_name="Task 2", timestamp=time.time())
            )
            await pilot.pause()

            # Task 0 should be auto-selected (first started)
            task_list = screen.query_one("#task-list")
            assert task_list.selected_index == 0  # type: ignore[attr-defined]

            # Finish task 0 — should auto-switch to task 2
            screen.post_message(
                TaskFinished(task_index=0, task_name="Task 0", status="success", duration=1.0)
            )
            await pilot.pause()

            assert task_list.selected_index == 2  # type: ignore[attr-defined]


# ===========================================================================
# SingleOperationScreen handler tests
# ===========================================================================


class TestSingleOperationScreenHandlers:
    """Tests for SingleOperationScreen message handlers."""

    @pytest.mark.timeout(10)
    async def test_liveness_update_delegates(self) -> None:
        """LivenessUpdate message updates the widget's liveness line."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_single_screen(app)

            screen.post_message(LivenessUpdate(line="compiling module X"))
            await pilot.pause()

            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.latest_liveness_line == "compiling module X"

    @pytest.mark.timeout(10)
    async def test_task_output_no_crash(self) -> None:
        """TaskOutput message on SingleOperationScreen does not crash."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_single_screen(app)

            screen.post_message(TaskOutput(task_index=0, task_name="Op", line="verbose line"))
            await pilot.pause()
            # No crash = pass


# ===========================================================================
# post_task_event bridge tests
# ===========================================================================


class TestPostTaskEventBridge:
    """Tests for the post_task_event bridge function."""

    @pytest.mark.timeout(10)
    async def test_async_context_posts_message(self) -> None:
        """post_task_event posts directly when in async context."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.PENDING)
            screen.set_records(records)

            event = TaskEvent(
                event_type=TaskEventType.TASK_STARTED,
                task_index=0,
                task_name="Task 0",
                timestamp=time.time(),
            )
            post_task_event(app, event)
            await pilot.pause()

            assert screen.records[0].status == TaskRunStatus.RUNNING

    @pytest.mark.timeout(10)
    async def test_run_started_is_noop(self) -> None:
        """post_task_event with RUN_STARTED does nothing."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            assert screen.completed is False

            event = TaskEvent(
                event_type=TaskEventType.RUN_STARTED,
                task_index=0,
                task_name="",
                timestamp=time.time(),
                data={"total_tasks": 3},
            )
            post_task_event(app, event)
            await pilot.pause()

            # No state change
            assert screen.completed is False

    @pytest.mark.timeout(10)
    async def test_thread_safe_post(self) -> None:
        """post_task_event works correctly from a background thread."""
        app = MultiTaskTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_multi_screen(app)
            records = _make_records(TaskRunStatus.PENDING)
            screen.set_records(records)

            event = TaskEvent(
                event_type=TaskEventType.TASK_STARTED,
                task_index=0,
                task_name="Task 0",
                timestamp=time.time(),
            )

            # Start thread — call_from_thread blocks until the event loop
            # processes the callback, so we must *not* join before yielding.
            t = threading.Thread(target=post_task_event, args=(app, event), daemon=True)
            t.start()

            # Yield to the event loop so it can process the call_from_thread
            # callback and the resulting message.
            await pilot.pause()
            await pilot.pause()
            t.join(timeout=5)

            assert screen.records[0].status == TaskRunStatus.RUNNING
