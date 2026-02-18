"""Base Textual application shell for INGOT."""

from textual.app import App, ComposeResult
from textual.widgets import Placeholder


class IngotApp(App[None]):
    """Root Textual application for INGOT."""

    CSS_PATH = "ingot.tcss"
    TITLE = "INGOT"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Placeholder()
