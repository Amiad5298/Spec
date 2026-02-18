"""TaskListWidget — Textual widget for displaying task execution status.

Provides a Textual widget with reactive state, keyboard navigation, and
spinner animation for visualizing task execution progress.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
from textual.message import Message
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

from ingot.workflow.events import TaskRunRecord, TaskRunStatus


class TaskListWidget(Widget):
    """Displays a list of tasks with live status, spinners, and keyboard nav."""

    DEFAULT_CSS = """
    TaskListWidget {
        height: auto;
        padding: 0 1;
    }
    """

    can_focus = True

    BINDINGS = [
        ("j", "cursor_down", "Down"),
        ("down", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("up", "cursor_up", "Up"),
    ]

    # -- reactive attributes --------------------------------------------------

    records: reactive[list[TaskRunRecord]] = reactive(list, recompose=False)
    selected_index: reactive[int] = reactive(-1, repaint=True)
    parallel_mode: reactive[bool] = reactive(False, repaint=True)

    # -- custom message --------------------------------------------------------

    class Selected(Message):
        """Emitted when the highlighted task changes."""

        def __init__(self, index: int) -> None:
            self.index = index
            super().__init__()

    # -- constructor -----------------------------------------------------------

    def __init__(
        self,
        ticket_id: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.ticket_id = ticket_id
        self._spinners: dict[int, Spinner] = {}
        self._spinner_timer: Timer | None = None

    # -- lifecycle -------------------------------------------------------------

    def on_mount(self) -> None:
        self._spinner_timer = self.set_interval(1 / 10, self._tick_spinner, pause=True)

    def on_unmount(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None
        self._spinners.clear()

    # -- spinner management ----------------------------------------------------

    def _sync_spinner(self, record: TaskRunRecord) -> None:
        """Create or remove a spinner for *record*, keyed by ``task_index``."""
        key = record.task_index
        if record.status == TaskRunStatus.RUNNING:
            if key not in self._spinners:
                self._spinners[key] = Spinner("dots", style=record.get_status_color())
        else:
            self._spinners.pop(key, None)

    def _ensure_spinner_timer_running(self) -> None:
        """Resume the spinner timer when any task is RUNNING, pause otherwise."""
        has_running = any(r.status == TaskRunStatus.RUNNING for r in self.records)
        if self._spinner_timer is not None:
            if has_running:
                self._spinner_timer.resume()
            else:
                self._spinner_timer.pause()

    def _tick_spinner(self) -> None:
        """Called by the interval timer to trigger a repaint for spinner frames."""
        self.refresh()

    # -- public helpers --------------------------------------------------------

    def update_record(self, index: int, record: TaskRunRecord) -> None:
        """Update a single record in-place, sync its spinner, and repaint."""
        if 0 <= index < len(self.records):
            self.records[index] = record
            self._sync_spinner(record)
            self._ensure_spinner_timer_running()
            self.mutate_reactive(TaskListWidget.records)

    def set_records(self, records: list[TaskRunRecord]) -> None:
        """Replace all records and rebuild the spinner cache."""
        self.records = list(records)
        self._spinners.clear()
        for rec in self.records:
            self._sync_spinner(rec)
        self._ensure_spinner_timer_running()

    # -- keyboard actions ------------------------------------------------------

    def action_cursor_down(self) -> None:
        n = len(self.records)
        if n == 0:
            return
        if self.selected_index < 0:
            self.selected_index = 0
        elif self.selected_index < n - 1:
            self.selected_index += 1
        self.post_message(self.Selected(self.selected_index))

    def action_cursor_up(self) -> None:
        n = len(self.records)
        if n == 0:
            return
        if self.selected_index < 0:
            self.selected_index = n - 1
        elif self.selected_index > 0:
            self.selected_index -= 1
        self.post_message(self.Selected(self.selected_index))

    # -- render ----------------------------------------------------------------

    def render(self) -> Panel:
        """Build a Rich ``Panel`` containing the task table."""
        table = Table(
            show_header=False,
            box=None,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Status", width=3)
        table.add_column("Task", ratio=1)
        table.add_column("Duration", width=10, justify="right")

        running_count = sum(1 for r in self.records if r.status == TaskRunStatus.RUNNING)

        for i, record in enumerate(self.records):
            icon = record.get_status_icon()
            color = record.get_status_color()

            # Status cell: cached spinner for RUNNING, static icon otherwise
            cached_spinner = (
                self._spinners.get(record.task_index)
                if record.status == TaskRunStatus.RUNNING
                else None
            )
            status_cell: Spinner | Text = (
                cached_spinner if cached_spinner else Text(icon, style=color)
            )

            # Task name styling
            name_style = ""
            if i == self.selected_index:
                name_style = "reverse"
            elif record.status == TaskRunStatus.RUNNING:
                name_style = "bold"

            # Running indicator
            name_text = record.task_name
            if record.status == TaskRunStatus.RUNNING and self.parallel_mode:
                name_text = f"{name_text} ⚡"
            elif record.status == TaskRunStatus.RUNNING:
                name_text = f"{name_text} ← Running"

            # Duration
            duration_text = ""
            if record.status in (
                TaskRunStatus.RUNNING,
                TaskRunStatus.SUCCESS,
                TaskRunStatus.FAILED,
            ):
                duration_text = f"[dim]{record.format_duration()}[/dim]"

            table.add_row(
                status_cell,
                Text(name_text, style=name_style),
                Text.from_markup(duration_text),
            )

        # Header
        total = len(self.records)
        completed = sum(1 for r in self.records if r.status == TaskRunStatus.SUCCESS)

        if self.parallel_mode and running_count > 0:
            header = f"TASKS [{self.ticket_id}] [{completed}/{total}] [⚡ {running_count} parallel]"
        elif self.ticket_id:
            header = f"TASKS [{self.ticket_id}] [{completed}/{total} tasks]"
        else:
            header = f"TASKS [{completed}/{total} tasks]"

        return Panel(
            table,
            title=header,
            border_style="blue",
        )


__all__ = ["TaskListWidget"]
