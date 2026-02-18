"""LogPanelWidget — Textual widget for scrollable, streaming log output.

Wraps Textual's ``RichLog`` in a bordered widget with follow mode,
replacing the fixed-height ``render_log_panel()`` from ``ingot/ui/tui.py``.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import RichLog


class LogPanelWidget(Widget):
    """Scrollable log panel with follow mode and task-aware border title."""

    DEFAULT_CSS = """
    LogPanelWidget {
        height: 1fr;
        border: round green;
        padding: 0 1;
    }
    LogPanelWidget.paused {
        border: round yellow;
    }
    """

    # -- reactive attributes --------------------------------------------------

    follow_mode: reactive[bool] = reactive(True, repaint=False)
    task_name: reactive[str] = reactive("", repaint=False)

    # -- lifecycle ------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield RichLog(auto_scroll=True, markup=False, max_lines=1000)

    def on_mount(self) -> None:
        self.border_title = "LOG"
        self._update_border_subtitle()

    # -- watchers -------------------------------------------------------------

    def watch_follow_mode(self, value: bool) -> None:
        try:
            rich_log = self.query_one(RichLog)
        except NoMatches:
            return
        rich_log.auto_scroll = value
        if value:
            rich_log.scroll_end(animate=False)
            self.remove_class("paused")
        else:
            self.add_class("paused")
        self._update_border_subtitle()

    def watch_task_name(self, value: str) -> None:
        if value:
            self.border_title = f"LOG — {value}"
        else:
            self.border_title = "LOG"

    # -- public API -----------------------------------------------------------

    def write_line(self, line: str) -> None:
        """Append a single line to the log."""
        self.query_one(RichLog).write(line)

    def set_content(self, lines: list[str]) -> None:
        """Replace all log content with *lines*."""
        rich_log = self.query_one(RichLog)
        rich_log.clear()
        for line in lines:
            rich_log.write(line)

    def clear(self) -> None:
        """Remove all lines from the log."""
        self.query_one(RichLog).clear()

    # -- private helpers ------------------------------------------------------

    def _update_border_subtitle(self) -> None:
        if self.follow_mode:
            self.border_subtitle = "FOLLOW"
        else:
            self.border_subtitle = "PAUSED"


__all__ = ["LogPanelWidget"]
