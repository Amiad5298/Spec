"""SingleOperationScreen — full screen for single-operation steps.

Composes :class:`SingleOperationWidget` with a :class:`Footer` and keybindings,
mirroring how :class:`MultiTaskScreen` composes its widgets.  Used for plan
generation, doc updates, test runs, and other single long-running operations.
"""

from __future__ import annotations

import os
import subprocess

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from ingot.ui.messages import LivenessUpdate, TaskOutput
from ingot.ui.widgets.single_operation import SingleOperationWidget


class SingleOperationScreen(Screen[None]):
    """Full-screen wrapper around SingleOperationWidget with footer."""

    DEFAULT_CSS = """
    SingleOperationScreen {
        layout: vertical;
    }
    SingleOperationScreen SingleOperationWidget {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("v", "toggle_verbose", "Verbose"),
        ("enter", "view_log", "View log"),
        ("q", "request_quit", "Cancel"),
    ]

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
        self._ticket_id = ticket_id
        self._log_path = log_path
        self._widget: SingleOperationWidget | None = None
        self._quit_requested: bool = False

    # -- composition ----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield SingleOperationWidget(
            ticket_id=self._ticket_id,
            log_path=self._log_path,
            id="single-op",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._widget = self.query_one("#single-op", SingleOperationWidget)

    # -- property delegation --------------------------------------------------

    def _require_widget(self) -> SingleOperationWidget:
        """Return the composed widget, raising if accessed before mount."""
        if self._widget is None:
            raise RuntimeError("SingleOperationScreen properties require the screen to be mounted")
        return self._widget

    @property
    def quit_requested(self) -> bool:
        """Whether the user has requested cancellation."""
        return self._quit_requested

    @property
    def status_message(self) -> str:
        return self._require_widget().status_message

    @status_message.setter
    def status_message(self, value: str) -> None:
        self._require_widget().status_message = value

    @property
    def ticket_id(self) -> str:
        return self._require_widget().ticket_id

    @ticket_id.setter
    def ticket_id(self, value: str) -> None:
        self._require_widget().ticket_id = value

    @property
    def verbose_mode(self) -> bool:
        return self._require_widget().verbose_mode

    @verbose_mode.setter
    def verbose_mode(self, value: bool) -> None:
        self._require_widget().verbose_mode = value

    @property
    def log_path(self) -> str:
        return self._require_widget().log_path

    @log_path.setter
    def log_path(self, value: str) -> None:
        self._require_widget().log_path = value

    # -- delegate methods -----------------------------------------------------

    def update_liveness(self, line: str) -> None:
        """Delegate liveness update to the widget."""
        self._require_widget().update_liveness(line)

    def write_log_line(self, line: str) -> None:
        """Delegate log line writing to the widget."""
        self._require_widget().write_log_line(line)

    # -- message handlers -----------------------------------------------------

    def on_liveness_update(self, msg: LivenessUpdate) -> None:
        self._require_widget().update_liveness(msg.line)

    def on_task_output(self, msg: TaskOutput) -> None:
        self._require_widget().write_log_line(msg.line)

    # -- actions --------------------------------------------------------------

    def action_toggle_verbose(self) -> None:
        w = self._require_widget()
        w.verbose_mode = not w.verbose_mode

    def action_view_log(self) -> None:
        if not self._log_path:
            return
        pager = os.environ.get("PAGER", "less")
        try:
            with self.app.suspend():
                subprocess.run([pager, self._log_path])  # noqa: S603
        except FileNotFoundError:
            self.notify(f"Pager '{pager}' not found", severity="error")

    def action_request_quit(self) -> None:
        from ingot.ui.screens.quit_modal import QuitConfirmModal

        def _on_result(confirmed: bool | None) -> None:
            if confirmed:
                self._quit_requested = True
                self.app.exit()

        self.app.push_screen(QuitConfirmModal("Cancel operation?"), callback=_on_result)


__all__ = ["SingleOperationScreen"]
