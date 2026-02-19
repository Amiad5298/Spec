"""Lightweight inline runner using Rich Live display.

Provides a compact 2-line inline progress display for single-operation
steps (plan generation, test execution, documentation update).  Replaces
the full-screen Textual TUI for these use-cases.

Display format::

    ⟳ Generating implementation plan...  (1m 23s)
      └─ Analyzing codebase structure...

The runner executes work in a background thread while the Rich ``Live``
display updates on the main thread.
"""

from __future__ import annotations

import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.live import Live
from rich.text import Text

from ingot.ui.log_buffer import TaskLogBuffer
from ingot.utils.console import console


@dataclass
class InlineRunner:
    """Lightweight inline runner with Rich Live progress display.

    API-compatible subset of TextualTaskRunner for single-operation mode.
    """

    status_message: str = "Processing..."
    ticket_id: str = ""

    # Private fields
    _log_path: Path | None = field(default=None, init=False, repr=False)
    _log_buffer: TaskLogBuffer | None = field(default=None, init=False, repr=False)
    _start_time: float = field(default=0.0, init=False, repr=False)
    _quit_by_user: bool = field(default=False, init=False, repr=False)
    _latest_line: str = field(default="", init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # =========================================================================
    # Setup
    # =========================================================================

    def set_log_path(self, path: Path) -> None:
        """Set log file path and create buffer."""
        self._log_path = path
        self._log_buffer = TaskLogBuffer(log_path=path)

    # =========================================================================
    # Core execution
    # =========================================================================

    def run_with_work(self, work_fn: Callable[[], Any]) -> Any:
        """Run work in a background thread with inline Live progress display.

        Args:
            work_fn: Zero-argument callable executed in the background thread.

        Returns:
            Whatever *work_fn* returns.

        Raises:
            Exception: Any exception raised by *work_fn* is re-raised.
        """
        self._start_time = time.time()
        self._quit_by_user = False
        self._latest_line = ""

        work_result: Any = None
        work_exception: BaseException | None = None
        done_event = threading.Event()

        def _do_work() -> None:
            nonlocal work_result, work_exception
            try:
                work_result = work_fn()
            except BaseException as exc:
                work_exception = exc
            finally:
                done_event.set()

        work_thread = threading.Thread(target=_do_work, daemon=True)

        # Install SIGINT handler to capture user cancellation
        original_sigint = signal.getsignal(signal.SIGINT)

        def _sigint_handler(signum: int, frame: Any) -> None:
            self._quit_by_user = True
            done_event.set()

        try:
            signal.signal(signal.SIGINT, _sigint_handler)

            work_thread.start()

            with Live(
                self._render(),
                console=console,
                refresh_per_second=4,
                transient=True,
            ) as live:
                while not done_event.wait(timeout=0.25):
                    live.update(self._render())
                # Final update
                live.update(self._render())

            work_thread.join(timeout=5.0 if self._quit_by_user else None)
        finally:
            signal.signal(signal.SIGINT, original_sigint)

            if self._log_buffer is not None:
                self._log_buffer.close()
                self._log_buffer = None

        if work_exception is not None:
            raise work_exception  # type: ignore[misc]
        return work_result

    # =========================================================================
    # Output handling
    # =========================================================================

    def handle_output_line(self, line: str) -> None:
        """Write line to log buffer and update the liveness indicator."""
        if self._log_buffer is not None:
            self._log_buffer.write(line)

        stripped = line.strip()
        if stripped:
            with self._lock:
                self._latest_line = stripped

    # =========================================================================
    # Quit handling
    # =========================================================================

    def check_quit_requested(self) -> bool:
        """Check if user requested cancellation (Ctrl+C)."""
        return self._quit_by_user

    def clear_quit_request(self) -> None:
        """Reset the quit request flag."""
        self._quit_by_user = False

    # =========================================================================
    # Summary
    # =========================================================================

    def print_summary(self, success: bool | None = None) -> None:
        """Print completion status after the Live display ends."""
        elapsed = self._format_elapsed_time()
        console.print()
        if success:
            console.print(f"[green]\u2713[/green] Operation completed in {elapsed}")
        elif success is False:
            console.print(f"[red]\u2717[/red] Operation failed after {elapsed}")
        else:
            console.print(f"[yellow]\u2298[/yellow] Operation cancelled after {elapsed}")
        if self._log_path:
            console.print(f"[dim]Logs saved to: {self._log_path}[/dim]")

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _render(self) -> Text:
        """Build the 2-line Rich Text for the Live display."""
        elapsed = self._format_elapsed_time()
        with self._lock:
            detail = self._latest_line

        text = Text()
        text.append("\u27f3 ", style="cyan")
        text.append(self.status_message, style="bold")
        text.append(f"  ({elapsed})", style="dim")
        if detail:
            # Truncate long lines to keep display compact
            max_detail = 80
            if len(detail) > max_detail:
                detail = detail[: max_detail - 1] + "\u2026"
            text.append("\n  \u2514\u2500 ", style="dim")
            text.append(detail, style="dim italic")
        return text

    def _format_elapsed_time(self) -> str:
        """Format elapsed time since start."""
        minutes, seconds = divmod(int(time.time() - self._start_time), 60)
        if minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"


__all__ = ["InlineRunner"]
