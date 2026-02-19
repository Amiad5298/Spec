"""Tests for TextualTaskRunner — Textual-based task runner orchestrator."""

from __future__ import annotations

import threading
import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from ingot.ui.textual_runner import TextualTaskRunner
from ingot.workflow.events import (
    TaskRunStatus,
    create_task_finished_event,
    create_task_started_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_console() -> tuple[Console, StringIO]:
    """Create a Rich Console that writes to a StringIO buffer."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=True, width=120)
    return con, buf


# ===========================================================================
# TestInitialization
# ===========================================================================


class TestInitialization:
    """Tests for setup methods that run before start()."""

    def test_initialize_records_creates_records(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["Task A", "Task B", "Task C"])

        assert len(runner.records) == 3
        assert runner.records[0].task_name == "Task A"
        assert runner.records[1].task_index == 1
        assert all(r.status == TaskRunStatus.PENDING for r in runner.records)

    def test_set_log_dir(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner()
        log_dir = tmp_path / "logs"
        runner.set_log_dir(log_dir)

        assert runner._log_dir == log_dir

    def test_set_log_path_creates_buffer(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner()
        log_path = tmp_path / "op.log"
        runner.set_log_path(log_path)

        assert runner._log_path == log_path
        assert runner._log_buffer is not None
        assert runner._log_buffer.log_path == log_path
        runner._log_buffer.close()

    def test_set_parallel_mode(self) -> None:
        runner = TextualTaskRunner()
        assert runner.parallel_mode is False

        runner.set_parallel_mode(True)
        assert runner.parallel_mode is True

        runner.set_parallel_mode(False)
        assert runner.parallel_mode is False

    def test_get_record_valid_index(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["A", "B"])

        record = runner.get_record(0)
        assert record is not None
        assert record.task_name == "A"

    def test_get_record_invalid_index(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["A"])

        assert runner.get_record(-1) is None
        assert runner.get_record(5) is None

    def test_get_record_empty(self) -> None:
        runner = TextualTaskRunner()
        assert runner.get_record(0) is None

    def test_default_values(self) -> None:
        runner = TextualTaskRunner()
        assert runner.ticket_id == ""
        assert runner.verbose_mode is False
        assert runner.single_operation_mode is False
        assert runner.status_message == "Processing..."
        assert runner.parallel_mode is False
        assert runner.records == []


# ===========================================================================
# TestContextManager
# ===========================================================================


class TestContextManager:
    """Tests for __enter__/__exit__ lifecycle."""

    @pytest.mark.timeout(15)
    def test_context_manager_starts_and_stops(self) -> None:
        runner = TextualTaskRunner(ticket_id="TEST-1", headless=True)
        runner.initialize_records(["Task 1"])

        with runner:
            assert runner._app is not None
            assert runner._app_thread is not None

        # After exit, app should be cleaned up
        assert runner._app is None
        assert runner._app_thread is None

    @pytest.mark.timeout(15)
    def test_context_manager_single_op_mode(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner(
            ticket_id="TEST-2",
            single_operation_mode=True,
            headless=True,
        )
        log_path = tmp_path / "test.log"
        runner.set_log_path(log_path)

        with runner:
            assert runner._app is not None

        assert runner._app is None

    @pytest.mark.timeout(15)
    def test_start_sets_start_time(self) -> None:
        runner = TextualTaskRunner(headless=True)
        runner.initialize_records(["Task 1"])

        before = time.time()
        with runner:
            after = time.time()
            assert before <= runner._start_time <= after


# ===========================================================================
# TestMultiTaskMode
# ===========================================================================


class TestMultiTaskMode:
    """Tests for multi-task mode event handling."""

    @pytest.mark.timeout(15)
    def test_handle_event_task_started(self) -> None:
        runner = TextualTaskRunner(ticket_id="TEST-3", headless=True)
        runner.initialize_records(["Task A", "Task B"])

        with runner:
            event = create_task_started_event(0, "Task A")
            runner.handle_event(event)
            # Give the Textual thread time to process
            time.sleep(0.3)

        # After stop, record should be RUNNING
        assert runner.records[0].status == TaskRunStatus.RUNNING
        assert runner.records[0].start_time is not None

    @pytest.mark.timeout(15)
    def test_handle_event_task_finished(self) -> None:
        runner = TextualTaskRunner(ticket_id="TEST-4", headless=True)
        runner.initialize_records(["Task A"])

        with runner:
            # Start the task first
            start_event = create_task_started_event(0, "Task A")
            runner.handle_event(start_event)
            time.sleep(0.2)

            # Finish the task
            finish_event = create_task_finished_event(0, "Task A", "success", 1.5)
            runner.handle_event(finish_event)
            time.sleep(0.2)

        assert runner.records[0].status == TaskRunStatus.SUCCESS

    @pytest.mark.timeout(15)
    def test_handle_event_task_failed(self) -> None:
        runner = TextualTaskRunner(ticket_id="TEST-5", headless=True)
        runner.initialize_records(["Task A"])

        with runner:
            start_event = create_task_started_event(0, "Task A")
            runner.handle_event(start_event)
            time.sleep(0.2)

            finish_event = create_task_finished_event(
                0, "Task A", "failed", 2.0, error="Something broke"
            )
            runner.handle_event(finish_event)
            time.sleep(0.2)

        assert runner.records[0].status == TaskRunStatus.FAILED
        assert runner.records[0].error == "Something broke"

    @pytest.mark.timeout(15)
    def test_mark_remaining_skipped(self) -> None:
        runner = TextualTaskRunner(ticket_id="TEST-6", headless=True)
        runner.initialize_records(["Task A", "Task B", "Task C"])

        with runner:
            # Start and finish task 0
            runner.handle_event(create_task_started_event(0, "Task A"))
            time.sleep(0.2)
            runner.handle_event(create_task_finished_event(0, "Task A", "failed", 1.0))
            time.sleep(0.2)

            # Mark remaining as skipped
            runner.mark_remaining_skipped(1)
            time.sleep(0.2)

        assert runner.records[0].status == TaskRunStatus.FAILED
        assert runner.records[1].status == TaskRunStatus.SKIPPED
        assert runner.records[2].status == TaskRunStatus.SKIPPED


# ===========================================================================
# TestSingleOperationMode
# ===========================================================================


class TestSingleOperationMode:
    """Tests for single-operation mode."""

    @pytest.mark.timeout(15)
    def test_handle_output_line_writes_to_buffer(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner(
            single_operation_mode=True,
            headless=True,
        )
        log_path = tmp_path / "output.log"
        runner.set_log_path(log_path)

        with runner:
            runner.handle_output_line("Line 1")
            runner.handle_output_line("Line 2")
            time.sleep(0.3)

        # Log buffer should have written to disk
        assert log_path.exists()
        content = log_path.read_text()
        assert "Line 1" in content
        assert "Line 2" in content

    @pytest.mark.timeout(15)
    def test_handle_output_line_without_buffer(self) -> None:
        """handle_output_line is safe without a log buffer."""
        runner = TextualTaskRunner(
            single_operation_mode=True,
            headless=True,
        )

        with runner:
            # Should not raise
            runner.handle_output_line("orphan line")
            time.sleep(0.1)


# ===========================================================================
# TestParallelMode
# ===========================================================================


class TestParallelMode:
    """Tests for parallel mode support."""

    @pytest.mark.timeout(15)
    def test_handle_event_from_multiple_threads(self) -> None:
        runner = TextualTaskRunner(ticket_id="PAR-1", headless=True)
        runner.initialize_records(["Task A", "Task B", "Task C"])
        runner.set_parallel_mode(True)

        with runner:
            threads = []
            for i, name in enumerate(["Task A", "Task B", "Task C"]):
                t = threading.Thread(
                    target=runner.handle_event,
                    args=(create_task_started_event(i, name),),
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=5)

            time.sleep(0.5)

        # All tasks should be RUNNING (or processed)
        running_count = sum(1 for r in runner.records if r.status == TaskRunStatus.RUNNING)
        assert running_count == 3


# ===========================================================================
# TestQuitHandling
# ===========================================================================


class TestQuitHandling:
    """Tests for quit detection and clearing."""

    @pytest.mark.timeout(15)
    def test_quit_initially_false(self) -> None:
        runner = TextualTaskRunner(headless=True)
        runner.initialize_records(["Task 1"])

        with runner:
            assert runner.check_quit_requested() is False

    @pytest.mark.timeout(15)
    def test_quit_true_after_app_exit(self) -> None:
        runner = TextualTaskRunner(headless=True)
        runner.initialize_records(["Task 1"])

        with runner:
            # Simulate user quit by setting the flag
            runner._app.quit_by_user = True  # type: ignore[union-attr]
            assert runner.check_quit_requested() is True

    @pytest.mark.timeout(15)
    def test_clear_quit_request(self) -> None:
        runner = TextualTaskRunner(headless=True)
        runner.initialize_records(["Task 1"])

        with runner:
            runner._app.quit_by_user = True  # type: ignore[union-attr]
            assert runner.check_quit_requested() is True

            runner.clear_quit_request()
            assert runner.check_quit_requested() is False

    def test_quit_true_when_app_is_none(self) -> None:
        runner = TextualTaskRunner()
        # No app started
        assert runner.check_quit_requested() is True


# ===========================================================================
# TestPrintSummary
# ===========================================================================


class TestPrintSummary:
    """Tests for print_summary output."""

    def test_multi_task_success_summary(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["Task A", "Task B"])
        runner.records[0].status = TaskRunStatus.SUCCESS
        runner.records[1].status = TaskRunStatus.SUCCESS
        runner._start_time = time.time() - 10

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary()

        output = buf.getvalue()
        assert "Execution Complete" in output
        assert "Succeeded" in output
        assert "2" in output

    def test_multi_task_mixed_summary(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["A", "B", "C"])
        runner.records[0].status = TaskRunStatus.SUCCESS
        runner.records[1].status = TaskRunStatus.FAILED
        runner.records[2].status = TaskRunStatus.SKIPPED
        runner._start_time = time.time() - 5

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary()

        output = buf.getvalue()
        assert "Succeeded" in output
        assert "Failed" in output
        assert "Skipped" in output

    def test_multi_task_with_log_dir(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["A"])
        runner.records[0].status = TaskRunStatus.SUCCESS
        runner.set_log_dir(tmp_path / "logs")
        runner._start_time = time.time()

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary()

        output = buf.getvalue()
        assert "Logs saved to" in output

    def test_single_op_success_summary(self) -> None:
        runner = TextualTaskRunner(single_operation_mode=True)
        runner._start_time = time.time() - 5

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary(success=True)

        output = buf.getvalue()
        assert "completed" in output

    def test_single_op_failure_summary(self) -> None:
        runner = TextualTaskRunner(single_operation_mode=True)
        runner._start_time = time.time() - 3

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary(success=False)

        output = buf.getvalue()
        assert "failed" in output

    def test_single_op_cancel_summary(self) -> None:
        runner = TextualTaskRunner(single_operation_mode=True)
        runner._start_time = time.time() - 2

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary(success=None)

        output = buf.getvalue()
        assert "cancelled" in output

    def test_single_op_with_log_path(self, tmp_path: Path) -> None:
        runner = TextualTaskRunner(single_operation_mode=True)
        runner._log_path = tmp_path / "op.log"
        runner._start_time = time.time()

        con, buf = _capture_console()
        with patch("ingot.ui.textual_runner.console", con):
            runner.print_summary(success=True)

        output = buf.getvalue()
        assert "Logs saved to" in output


# ===========================================================================
# TestEdgeCases
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and robustness."""

    @pytest.mark.timeout(15)
    def test_double_stop_is_safe(self) -> None:
        runner = TextualTaskRunner(headless=True)
        runner.initialize_records(["Task 1"])
        runner.start()
        runner.stop()
        runner.stop()  # Should not raise

    def test_handle_event_after_stop(self) -> None:
        runner = TextualTaskRunner()
        event = create_task_started_event(0, "Task A")
        # No app running — should not raise
        runner.handle_event(event)

    def test_handle_event_after_stop_from_edge_case(self) -> None:
        runner = TextualTaskRunner()
        event = create_task_started_event(0, "Task A")
        runner.handle_event(event)  # Should not raise

    def test_handle_output_line_after_stop(self) -> None:
        runner = TextualTaskRunner(single_operation_mode=True)
        runner.handle_output_line("late line")  # Should not raise

    def test_clear_quit_no_app(self) -> None:
        runner = TextualTaskRunner()
        runner.clear_quit_request()  # Should not raise

    def test_mark_remaining_skipped_no_app(self) -> None:
        runner = TextualTaskRunner()
        runner.initialize_records(["A", "B"])
        runner.mark_remaining_skipped(0)

        assert runner.records[0].status == TaskRunStatus.SKIPPED
        assert runner.records[1].status == TaskRunStatus.SKIPPED

    def test_format_elapsed_time_seconds(self) -> None:
        runner = TextualTaskRunner()
        runner._start_time = time.time() - 42
        elapsed = runner._format_elapsed_time()
        assert elapsed == "42s"

    def test_format_elapsed_time_minutes(self) -> None:
        runner = TextualTaskRunner()
        runner._start_time = time.time() - 125  # 2m 5s
        elapsed = runner._format_elapsed_time()
        assert "2m" in elapsed
