"""MultiTaskScreen — split-pane layout composing task list and log panel.

Replaces the ``_render_multi_task_layout()`` helper in ``ingot/ui/tui.py``
with a native Textual Screen that composes :class:`TaskListWidget` and
:class:`LogPanelWidget` side by side.
"""

from __future__ import annotations

import os
import subprocess

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ingot.ui.widgets.log_panel import LogPanelWidget
from ingot.ui.widgets.task_list import TaskListWidget
from ingot.workflow.events import TaskRunRecord

_DEFAULT_TAIL_LINES = 15
_VERBOSE_TAIL_LINES = 50


class MultiTaskScreen(Screen[None]):
    """Split-pane screen with task list (left) and log panel (right)."""

    DEFAULT_CSS = """
    MultiTaskScreen {
        layout: vertical;
    }
    MultiTaskScreen Horizontal {
        height: 1fr;
    }
    MultiTaskScreen TaskListWidget {
        width: 2fr;
        height: 1fr;
    }
    MultiTaskScreen LogPanelWidget {
        width: 3fr;
    }
    """

    BINDINGS = [
        ("enter", "view_log", "View log"),
        ("f", "toggle_follow", "Follow"),
        ("v", "toggle_verbose", "Verbose"),
        ("l", "show_log_path", "Log path"),
        ("q", "request_quit", "Quit"),
    ]

    verbose_mode: reactive[bool] = reactive(False)

    def __init__(
        self,
        ticket_id: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._ticket_id = ticket_id

    # -- composition ----------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield TaskListWidget(ticket_id=self._ticket_id, id="task-list")
            yield LogPanelWidget(id="log-panel")
        yield Footer()

    def on_mount(self) -> None:
        self._task_list = self.query_one("#task-list", TaskListWidget)
        self._log_panel = self.query_one("#log-panel", LogPanelWidget)
        self._task_list.focus()

    # -- property delegation --------------------------------------------------

    @property
    def ticket_id(self) -> str:
        return self._task_list.ticket_id

    @ticket_id.setter
    def ticket_id(self, value: str) -> None:
        self._task_list.ticket_id = value

    @property
    def parallel_mode(self) -> bool:
        return self._task_list.parallel_mode

    @parallel_mode.setter
    def parallel_mode(self, value: bool) -> None:
        self._task_list.parallel_mode = value

    @property
    def records(self) -> list[TaskRunRecord]:
        return self._task_list.records

    # -- delegate methods -----------------------------------------------------

    def set_records(self, records: list[TaskRunRecord]) -> None:
        self._task_list.set_records(records)

    def update_record(self, index: int, record: TaskRunRecord) -> None:
        self._task_list.update_record(index, record)
        # Refresh log panel if the updated record is currently selected
        if self._task_list.selected_index == index:
            self._update_log_panel(index)

    # -- message handlers -----------------------------------------------------

    def on_task_list_widget_selected(self, event: TaskListWidget.Selected) -> None:
        self._update_log_panel(event.index)

    # -- actions --------------------------------------------------------------

    def action_view_log(self) -> None:
        record = self._get_selected_record()
        if record is None or record.log_buffer is None:
            return
        log_path = str(record.log_buffer.log_path)
        pager = os.environ.get("PAGER", "less")
        try:
            with self.app.suspend():
                subprocess.run([pager, log_path])  # noqa: S603
        except FileNotFoundError:
            self.notify(f"Pager '{pager}' not found", severity="error")

    def action_toggle_follow(self) -> None:
        self._log_panel.follow_mode = not self._log_panel.follow_mode

    def action_toggle_verbose(self) -> None:
        self.verbose_mode = not self.verbose_mode
        # Refresh the log panel with the new tail length
        if self._task_list.selected_index >= 0:
            self._update_log_panel(self._task_list.selected_index)

    def action_show_log_path(self) -> None:
        record = self._get_selected_record()
        if record is not None and record.log_buffer is not None:
            self.notify(str(record.log_buffer.log_path))

    def action_request_quit(self) -> None:
        self.app.exit()

    # -- private helpers ------------------------------------------------------

    def _update_log_panel(self, index: int) -> None:
        record = self._get_record_at(index)
        if record is None:
            return
        self._log_panel.task_name = record.task_name
        if record.log_buffer is not None:
            n = _VERBOSE_TAIL_LINES if self.verbose_mode else _DEFAULT_TAIL_LINES
            self._log_panel.set_content(record.log_buffer.get_tail(n))
        else:
            self._log_panel.set_content([])

    def _get_selected_record(self) -> TaskRunRecord | None:
        return self._get_record_at(self._task_list.selected_index)

    def _get_record_at(self, index: int) -> TaskRunRecord | None:
        if 0 <= index < len(self._task_list.records):
            return self._task_list.records[index]
        return None


__all__ = ["MultiTaskScreen"]
