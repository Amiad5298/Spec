"""SingleOperationWidget — Textual widget for spinner + liveness display.

Ports the single-operation rendering logic from ``ingot/ui/tui.py`` into a
proper Textual widget with compose pattern, reactive state, and verbose mode
toggling.
"""

from __future__ import annotations

import time

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import RichLog, Static

MAX_LIVENESS_WIDTH = 70


class SingleOperationWidget(Widget):
    """Displays a single long-running operation with spinner and liveness."""

    DEFAULT_CSS = """
    SingleOperationWidget {
        height: auto;
        border: round blue;
        padding: 0 1;
    }
    SingleOperationWidget.verbose {
        border: round green;
    }
    SingleOperationWidget .verbose-log {
        display: none;
        height: 12;
    }
    SingleOperationWidget.verbose .verbose-log {
        display: block;
    }
    SingleOperationWidget.verbose .liveness-line {
        display: none;
    }
    """

    # -- reactive attributes --------------------------------------------------

    status_message: reactive[str] = reactive("", repaint=False)
    verbose_mode: reactive[bool] = reactive(False, repaint=False)

    # -- constructor -----------------------------------------------------------

    def __init__(
        self,
        ticket_id: str = "",
        log_path: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.ticket_id = ticket_id
        self.log_path = log_path
        self._start_time: float = time.monotonic()
        self._elapsed_timer: Timer | None = None
        self._latest_liveness_line: str = ""

    # -- lifecycle -------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Static("", id="status-line")
        yield Static("", id="liveness-line", classes="liveness-line")
        yield RichLog(auto_scroll=True, markup=False, max_lines=500, classes="verbose-log")
        yield Static("", id="log-path-line")

    def on_mount(self) -> None:
        header = f"⟳ {self.ticket_id}" if self.ticket_id else "⟳ Operation"
        self.border_title = header
        self._update_status_display()
        self._update_liveness_display("")
        self._update_log_path_display()
        self._elapsed_timer = self.set_interval(1, self._tick_elapsed)

    def on_unmount(self) -> None:
        if self._elapsed_timer is not None:
            self._elapsed_timer.stop()
            self._elapsed_timer = None

    # -- watchers --------------------------------------------------------------

    def watch_status_message(self, value: str) -> None:
        self._update_status_display()

    def watch_verbose_mode(self, value: bool) -> None:
        if value:
            self.add_class("verbose")
        else:
            self.remove_class("verbose")

    # -- public API ------------------------------------------------------------

    def update_liveness(self, line: str) -> None:
        """Update the liveness indicator with the latest output line."""
        self._latest_liveness_line = line
        self._update_liveness_display(line)

    def write_log_line(self, line: str) -> None:
        """Append a line to the verbose RichLog."""
        try:
            self.query_one(RichLog).write(line)
        except NoMatches:
            pass

    # -- private helpers -------------------------------------------------------

    def _format_elapsed_time(self) -> str:
        """Format elapsed time since start (e.g. '1m 23s' or '5s')."""
        elapsed = time.monotonic() - self._start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        if minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"

    @staticmethod
    def _truncate_line(line: str, max_width: int = MAX_LIVENESS_WIDTH) -> str:
        """Truncate a line to max width with ellipsis."""
        if len(line) <= max_width:
            return line
        return line[: max_width - 1] + "…"

    def _tick_elapsed(self) -> None:
        """Timer callback to refresh the status display with updated elapsed."""
        self._update_status_display()

    def _update_status_display(self) -> None:
        """Update the #status-line Static with message and elapsed time."""
        try:
            status_static = self.query_one("#status-line", Static)
        except NoMatches:
            return
        elapsed = self._format_elapsed_time()
        msg = self.status_message
        if msg:
            status_static.update(f"[bold]{msg}[/bold] [dim]{elapsed}[/dim]")
        else:
            status_static.update(f"[dim]{elapsed}[/dim]")

    def _update_liveness_display(self, line: str) -> None:
        """Update the #liveness-line Static."""
        try:
            liveness_static = self.query_one("#liveness-line", Static)
        except NoMatches:
            return
        stripped = line.strip() if line else ""
        if stripped:
            truncated = self._truncate_line(stripped)
            liveness_static.update(f"[dim cyan]► [/dim cyan][dim]{truncated}[/dim]")
        else:
            liveness_static.update("[dim]Waiting for output...[/dim]")

    def _update_log_path_display(self) -> None:
        """Update the #log-path-line Static with the log file path."""
        try:
            log_path_static = self.query_one("#log-path-line", Static)
        except NoMatches:
            return
        if self.log_path:
            log_path_static.update(f"[dim]Logs: [/dim][dim italic]{self.log_path}[/dim italic]")
        else:
            log_path_static.update("")


__all__ = ["SingleOperationWidget"]
