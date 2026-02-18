"""Tests for LogPanelWidget — the Textual scrollable log panel widget."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import RichLog

from ingot.ui.widgets.log_panel import LogPanelWidget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class LogPanelTestApp(App[None]):
    """Minimal app that mounts a LogPanelWidget for testing."""

    def compose(self) -> ComposeResult:
        yield LogPanelWidget()


# ===========================================================================
# Writing tests
# ===========================================================================


class TestWriting:
    """Tests for write_line and content accumulation."""

    @pytest.mark.timeout(10)
    async def test_write_line_adds_content(self) -> None:
        """write_line appends a line to the RichLog."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("hello world")
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 1

    @pytest.mark.timeout(10)
    async def test_multiple_writes_accumulate(self) -> None:
        """Multiple write_line calls accumulate lines."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("line 1")
            widget.write_line("line 2")
            widget.write_line("line 3")
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 3

    @pytest.mark.timeout(10)
    async def test_write_empty_string(self) -> None:
        """Writing an empty string still adds a line."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("")
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 1


# ===========================================================================
# Follow mode tests
# ===========================================================================


class TestFollowMode:
    """Tests for follow mode toggling."""

    @pytest.mark.timeout(10)
    async def test_default_is_true(self) -> None:
        """Follow mode defaults to True."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            assert widget.follow_mode is True

    @pytest.mark.timeout(10)
    async def test_toggle_updates_auto_scroll(self) -> None:
        """Toggling follow_mode updates RichLog.auto_scroll."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            rich_log = widget.query_one(RichLog)
            assert rich_log.auto_scroll is True

            widget.follow_mode = False
            assert rich_log.auto_scroll is False

            widget.follow_mode = True
            assert rich_log.auto_scroll is True

    @pytest.mark.timeout(10)
    async def test_paused_css_class_toggled(self) -> None:
        """CSS class 'paused' is added/removed with follow mode."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            assert not widget.has_class("paused")

            widget.follow_mode = False
            assert widget.has_class("paused")

            widget.follow_mode = True
            assert not widget.has_class("paused")

    @pytest.mark.timeout(10)
    async def test_border_subtitle_reflects_state(self) -> None:
        """Border subtitle shows FOLLOW or PAUSED."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            assert widget.border_subtitle == "FOLLOW"

            widget.follow_mode = False
            assert widget.border_subtitle == "PAUSED"

            widget.follow_mode = True
            assert widget.border_subtitle == "FOLLOW"


# ===========================================================================
# set_content tests
# ===========================================================================


class TestSetContent:
    """Tests for set_content replacing log contents."""

    @pytest.mark.timeout(10)
    async def test_replaces_existing_content(self) -> None:
        """set_content replaces previously written lines."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("old line 1")
            widget.write_line("old line 2")

            widget.set_content(["new line 1", "new line 2", "new line 3"])
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 3

    @pytest.mark.timeout(10)
    async def test_empty_list_clears(self) -> None:
        """set_content with empty list clears all lines."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("some line")

            widget.set_content([])
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 0


# ===========================================================================
# Clear tests
# ===========================================================================


class TestClear:
    """Tests for clear method."""

    @pytest.mark.timeout(10)
    async def test_removes_all_lines(self) -> None:
        """clear() removes all lines from the log."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("line 1")
            widget.write_line("line 2")

            widget.clear()
            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 0

    @pytest.mark.timeout(10)
    async def test_can_write_after_clearing(self) -> None:
        """Writing after clear works normally."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.write_line("before")
            widget.clear()
            widget.write_line("after")

            rich_log = widget.query_one(RichLog)
            assert len(rich_log.lines) == 1


# ===========================================================================
# Border title tests
# ===========================================================================


class TestBorderTitle:
    """Tests for border title updates."""

    @pytest.mark.timeout(10)
    async def test_default_title(self) -> None:
        """Default border title is 'LOG'."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            assert widget.border_title == "LOG"

    @pytest.mark.timeout(10)
    async def test_title_with_task_name(self) -> None:
        """Setting task_name updates the border title."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.task_name = "Build project"
            assert widget.border_title == "LOG — Build project"

    @pytest.mark.timeout(10)
    async def test_reactive_update_on_change(self) -> None:
        """Changing task_name reactively updates the border title."""
        app = LogPanelTestApp()
        async with app.run_test():
            widget = app.query_one(LogPanelWidget)
            widget.task_name = "Task A"
            assert widget.border_title == "LOG — Task A"

            widget.task_name = "Task B"
            assert widget.border_title == "LOG — Task B"

            widget.task_name = ""
            assert widget.border_title == "LOG"
