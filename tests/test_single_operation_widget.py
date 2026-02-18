"""Tests for SingleOperationWidget — spinner + liveness display widget."""

from __future__ import annotations

import time

import pytest
from textual.app import App, ComposeResult
from textual.widgets import RichLog, Static

from ingot.ui.widgets.single_operation import (
    MAX_LIVENESS_WIDTH,
    SingleOperationWidget,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SingleOpTestApp(App[None]):
    """Minimal app that mounts a SingleOperationWidget for testing."""

    def __init__(
        self,
        ticket_id: str = "",
        log_path: str = "",
        status_message: str = "",
    ) -> None:
        super().__init__()
        self._ticket_id = ticket_id
        self._log_path = log_path
        self._status_message = status_message

    def compose(self) -> ComposeResult:
        widget = SingleOperationWidget(
            ticket_id=self._ticket_id,
            log_path=self._log_path,
        )
        widget.status_message = self._status_message
        yield widget


# ===========================================================================
# Defaults
# ===========================================================================


class TestDefaults:
    """Tests for default state after mount."""

    @pytest.mark.timeout(10)
    async def test_default_verbose_false(self) -> None:
        """verbose_mode defaults to False."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert widget.verbose_mode is False

    @pytest.mark.timeout(10)
    async def test_default_status_empty(self) -> None:
        """status_message defaults to empty string."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert widget.status_message == ""

    @pytest.mark.timeout(10)
    async def test_border_title_with_ticket_id(self) -> None:
        """Border title includes ticket_id when provided."""
        app = SingleOpTestApp(ticket_id="AMI-42")
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert widget.border_title == "⟳ AMI-42"

    @pytest.mark.timeout(10)
    async def test_border_title_without_ticket_id(self) -> None:
        """Border title shows 'Operation' when no ticket_id."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert widget.border_title == "⟳ Operation"

    @pytest.mark.timeout(10)
    async def test_no_verbose_css_class(self) -> None:
        """Widget does not have 'verbose' CSS class by default."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert not widget.has_class("verbose")


# ===========================================================================
# Status message
# ===========================================================================


class TestStatusMessage:
    """Tests for status_message reactive updates."""

    @pytest.mark.timeout(10)
    async def test_status_updates_display(self) -> None:
        """Setting status_message updates #status-line."""
        app = SingleOpTestApp(status_message="Generating plan...")
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            status = widget.query_one("#status-line", Static)
            assert "Generating plan..." in str(status.content)

    @pytest.mark.timeout(10)
    async def test_status_change(self) -> None:
        """Changing status_message reactively updates display."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.status_message = "Running tests..."
            status = widget.query_one("#status-line", Static)
            assert "Running tests..." in str(status.content)

    @pytest.mark.timeout(10)
    async def test_empty_message_shows_elapsed_only(self) -> None:
        """Empty status_message still shows elapsed time."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.status_message = ""
            status = widget.query_one("#status-line", Static)
            # Should contain elapsed time (e.g. "0s")
            assert "s" in str(status.content)


# ===========================================================================
# Elapsed time
# ===========================================================================


class TestElapsedTime:
    """Tests for _format_elapsed_time (pure logic, no Textual app needed)."""

    def test_seconds_only_format(self) -> None:
        """Under a minute shows seconds only."""
        widget = SingleOperationWidget()
        widget._start_time = time.monotonic() - 5
        result = widget._format_elapsed_time()
        assert result == "5s"

    def test_minutes_format(self) -> None:
        """Over a minute shows 'Xm YYs' format."""
        widget = SingleOperationWidget()
        widget._start_time = time.monotonic() - 83  # 1m 23s
        result = widget._format_elapsed_time()
        assert result == "1m 23s"

    def test_zero_seconds(self) -> None:
        """Just started shows '0s'."""
        widget = SingleOperationWidget()
        widget._start_time = time.monotonic()
        result = widget._format_elapsed_time()
        assert result == "0s"


# ===========================================================================
# Liveness
# ===========================================================================


class TestLiveness:
    """Tests for liveness indicator updates."""

    @pytest.mark.timeout(10)
    async def test_initial_waiting_message(self) -> None:
        """Initially shows 'Waiting for output...'."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            liveness = widget.query_one("#liveness-line", Static)
            assert "Waiting for output..." in str(liveness.content)

    @pytest.mark.timeout(10)
    async def test_update_liveness_shows_line(self) -> None:
        """update_liveness shows the provided line."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.update_liveness("Building module X...")
            liveness = widget.query_one("#liveness-line", Static)
            assert "Building module X..." in str(liveness.content)
            assert "►" in str(liveness.content)

    @pytest.mark.timeout(10)
    async def test_truncation_at_max_width(self) -> None:
        """Long lines are truncated at MAX_LIVENESS_WIDTH."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            long_line = "x" * 100
            widget.update_liveness(long_line)
            liveness = widget.query_one("#liveness-line", Static)
            assert "…" in str(liveness.content)

    @pytest.mark.timeout(10)
    async def test_whitespace_stripping(self) -> None:
        """Leading/trailing whitespace is stripped from liveness lines."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.update_liveness("  spaced text  ")
            liveness = widget.query_one("#liveness-line", Static)
            assert "spaced text" in str(liveness.content)

    @pytest.mark.timeout(10)
    async def test_empty_string_shows_waiting(self) -> None:
        """Empty string reverts to 'Waiting for output...'."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.update_liveness("something")
            widget.update_liveness("")
            liveness = widget.query_one("#liveness-line", Static)
            assert "Waiting for output..." in str(liveness.content)

    @pytest.mark.timeout(10)
    async def test_stores_latest_line(self) -> None:
        """update_liveness stores the line in latest_liveness_line."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            widget.update_liveness("latest output")
            assert widget.latest_liveness_line == "latest output"


# ===========================================================================
# Verbose mode
# ===========================================================================


class TestVerboseMode:
    """Tests for verbose mode toggling."""

    @pytest.mark.timeout(10)
    async def test_css_class_toggle(self) -> None:
        """Setting verbose_mode adds/removes 'verbose' CSS class."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert not widget.has_class("verbose")

            widget.verbose_mode = True
            assert widget.has_class("verbose")

            widget.verbose_mode = False
            assert not widget.has_class("verbose")

    @pytest.mark.timeout(10)
    async def test_richlog_has_verbose_log_class(self) -> None:
        """RichLog has the 'verbose-log' CSS class for toggling."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            rich_log = widget.query_one(RichLog)
            assert rich_log.has_class("verbose-log")

    @pytest.mark.timeout(10)
    async def test_liveness_has_class(self) -> None:
        """Liveness line has the 'liveness-line' CSS class."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            liveness = widget.query_one("#liveness-line", Static)
            assert liveness.has_class("liveness-line")


# ===========================================================================
# Write log line
# ===========================================================================


class TestWriteLogLine:
    """Tests for write_log_line appending to RichLog."""

    @pytest.mark.timeout(10)
    async def test_adds_to_richlog(self) -> None:
        """write_log_line appends to the RichLog (verbose mode makes it visible)."""
        app = SingleOpTestApp()
        async with app.run_test() as pilot:
            widget = app.query_one(SingleOperationWidget)
            widget.verbose_mode = True
            await pilot.pause()
            widget.write_log_line("hello world")
            await pilot.pause()
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 1

    @pytest.mark.timeout(10)
    async def test_multiple_lines_accumulate(self) -> None:
        """Multiple write_log_line calls accumulate."""
        app = SingleOpTestApp()
        async with app.run_test() as pilot:
            widget = app.query_one(SingleOperationWidget)
            widget.verbose_mode = True
            await pilot.pause()
            widget.write_log_line("line 1")
            widget.write_log_line("line 2")
            widget.write_log_line("line 3")
            await pilot.pause()
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 3


# ===========================================================================
# Log path
# ===========================================================================


class TestLogPath:
    """Tests for log path display."""

    @pytest.mark.timeout(10)
    async def test_path_displayed(self) -> None:
        """Log path is shown when provided."""
        app = SingleOpTestApp(log_path="/tmp/ingot.log")
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            log_path = widget.query_one("#log-path-line", Static)
            assert "/tmp/ingot.log" in str(log_path.content)
            assert "Logs:" in str(log_path.content)

    @pytest.mark.timeout(10)
    async def test_no_path_empty(self) -> None:
        """No log path results in empty display."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            log_path = widget.query_one("#log-path-line", Static)
            assert str(log_path.content) == ""


# ===========================================================================
# Lifecycle
# ===========================================================================


class TestLifecycle:
    """Tests for timer lifecycle management."""

    @pytest.mark.timeout(10)
    async def test_timer_starts_on_mount(self) -> None:
        """Elapsed timer is started on mount."""
        app = SingleOpTestApp()
        async with app.run_test():
            widget = app.query_one(SingleOperationWidget)
            assert widget._elapsed_timer is not None

    @pytest.mark.timeout(10)
    async def test_timer_stops_on_unmount(self) -> None:
        """Elapsed timer is stopped on unmount."""
        app = SingleOpTestApp()
        async with app.run_test() as pilot:
            widget = app.query_one(SingleOperationWidget)
            assert widget._elapsed_timer is not None
            widget.remove()
            await pilot.pause()
            assert widget._elapsed_timer is None


# ===========================================================================
# Truncation (pure unit tests)
# ===========================================================================


class TestTruncation:
    """Pure unit tests for _truncate_line."""

    def test_short_line_unchanged(self) -> None:
        """Lines shorter than max_width are returned unchanged."""
        widget = SingleOperationWidget()
        assert widget._truncate_line("hello") == "hello"

    def test_exact_width_unchanged(self) -> None:
        """Lines exactly at max_width are returned unchanged."""
        widget = SingleOperationWidget()
        line = "x" * MAX_LIVENESS_WIDTH
        assert widget._truncate_line(line) == line

    def test_long_line_truncated(self) -> None:
        """Lines over max_width are truncated with ellipsis."""
        widget = SingleOperationWidget()
        line = "x" * (MAX_LIVENESS_WIDTH + 10)
        result = widget._truncate_line(line)
        assert len(result) == MAX_LIVENESS_WIDTH
        assert result.endswith("…")

    def test_custom_width(self) -> None:
        """Custom max_width is respected."""
        widget = SingleOperationWidget()
        result = widget._truncate_line("abcdefghij", max_width=5)
        assert result == "abcd…"
        assert len(result) == 5
