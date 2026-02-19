"""Tests for InlineRunner — lightweight inline progress display."""

from __future__ import annotations

import time
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from ingot.ui.inline_runner import InlineRunner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_console() -> tuple[Console, StringIO]:
    """Create a Rich Console that writes to a StringIO buffer."""
    buf = StringIO()
    con = Console(file=buf, force_terminal=True, width=120)
    return con, buf


# ===========================================================================
# TestSetup
# ===========================================================================


class TestSetup:
    """Tests for default values and setup methods."""

    def test_default_values(self) -> None:
        runner = InlineRunner()
        assert runner.status_message == "Processing..."
        assert runner.ticket_id == ""
        assert runner._log_path is None
        assert runner._log_buffer is None
        assert runner._quit_by_user is False

    def test_set_log_path_creates_buffer(self, tmp_path: Path) -> None:
        runner = InlineRunner()
        log_path = tmp_path / "op.log"
        runner.set_log_path(log_path)

        assert runner._log_path == log_path
        assert runner._log_buffer is not None
        assert runner._log_buffer.log_path == log_path
        runner._log_buffer.close()


# ===========================================================================
# TestRunWithWork
# ===========================================================================


class TestRunWithWork:
    """Tests for run_with_work()."""

    @pytest.mark.timeout(15)
    def test_returns_work_result(self) -> None:
        runner = InlineRunner()

        with patch("ingot.ui.inline_runner.console"):
            result = runner.run_with_work(lambda: 42)

        assert result == 42

    @pytest.mark.timeout(15)
    def test_returns_tuple_result(self) -> None:
        runner = InlineRunner()

        with patch("ingot.ui.inline_runner.console"):
            result = runner.run_with_work(lambda: (True, "output text"))

        assert result == (True, "output text")

    @pytest.mark.timeout(15)
    def test_propagates_exception(self) -> None:
        runner = InlineRunner()

        def _failing_work() -> None:
            raise ValueError("boom")

        with patch("ingot.ui.inline_runner.console"):
            with pytest.raises(ValueError, match="boom"):
                runner.run_with_work(_failing_work)

    @pytest.mark.timeout(15)
    def test_quit_false_after_normal_completion(self) -> None:
        runner = InlineRunner()

        with patch("ingot.ui.inline_runner.console"):
            runner.run_with_work(lambda: None)

        assert runner.check_quit_requested() is False


# ===========================================================================
# TestHandleOutputLine
# ===========================================================================


class TestHandleOutputLine:
    """Tests for handle_output_line()."""

    def test_writes_to_log_buffer(self, tmp_path: Path) -> None:
        runner = InlineRunner()
        log_path = tmp_path / "output.log"
        runner.set_log_path(log_path)

        runner.handle_output_line("Line 1")
        runner.handle_output_line("Line 2")

        # Flush and close to ensure data is on disk
        runner._log_buffer.close()  # type: ignore[union-attr]

        content = log_path.read_text()
        assert "Line 1" in content
        assert "Line 2" in content

    def test_updates_latest_line(self) -> None:
        runner = InlineRunner()
        runner.handle_output_line("first")
        runner.handle_output_line("second")

        assert runner._latest_line == "second"

    def test_blank_lines_ignored(self) -> None:
        runner = InlineRunner()
        runner.handle_output_line("visible")
        runner.handle_output_line("   ")

        assert runner._latest_line == "visible"

    def test_safe_without_buffer(self) -> None:
        runner = InlineRunner()
        # Should not raise
        runner.handle_output_line("orphan line")


# ===========================================================================
# TestPrintSummary
# ===========================================================================


class TestPrintSummary:
    """Tests for print_summary()."""

    def test_success_message(self) -> None:
        runner = InlineRunner()
        runner._start_time = time.time() - 5

        con, buf = _capture_console()
        with patch("ingot.ui.inline_runner.console", con):
            runner.print_summary(success=True)

        output = buf.getvalue()
        assert "completed" in output

    def test_failure_message(self) -> None:
        runner = InlineRunner()
        runner._start_time = time.time() - 3

        con, buf = _capture_console()
        with patch("ingot.ui.inline_runner.console", con):
            runner.print_summary(success=False)

        output = buf.getvalue()
        assert "failed" in output

    def test_cancel_message(self) -> None:
        runner = InlineRunner()
        runner._start_time = time.time() - 2

        con, buf = _capture_console()
        with patch("ingot.ui.inline_runner.console", con):
            runner.print_summary(success=None)

        output = buf.getvalue()
        assert "cancelled" in output

    def test_log_path_display(self, tmp_path: Path) -> None:
        runner = InlineRunner()
        runner._log_path = tmp_path / "op.log"
        runner._start_time = time.time()

        con, buf = _capture_console()
        with patch("ingot.ui.inline_runner.console", con):
            runner.print_summary(success=True)

        output = buf.getvalue()
        assert "Logs saved to" in output
