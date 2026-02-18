"""QuitConfirmModal — inline quit confirmation overlay.

Replaces the stop-TUI-then-prompt-then-restart pattern with a native
Textual ModalScreen that confirms quit without leaving the TUI.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class QuitConfirmModal(ModalScreen[bool]):
    """Semi-transparent modal asking the user to confirm quit."""

    DEFAULT_CSS = """
    QuitConfirmModal {
        align: center middle;
    }

    QuitConfirmModal > Vertical {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    QuitConfirmModal > Vertical > Label {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    QuitConfirmModal > Vertical > Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }

    QuitConfirmModal > Vertical > Horizontal > Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        message: str = "Quit task execution?",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._message, id="quit-message")
            with Horizontal():
                yield Button("Continue", variant="success", id="btn-continue")
                yield Button("Yes, quit", variant="error", id="btn-quit")

    def on_mount(self) -> None:
        self.query_one("#btn-continue", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-quit":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


__all__ = ["QuitConfirmModal"]
