"""Textual-based task runner orchestrator.

Wraps a Textual App running in a background thread, providing the same
public API as :class:`TaskRunnerUI` so workflow code can be swapped
with minimal changes.

Supports two modes:
1. **Multi-task mode** (default): Uses :class:`MultiTaskScreen` for Step 3
   task execution with task list, navigation, and parallel execution.
2. **Single-operation mode**: Uses :class:`SingleOperationScreen` for
   Steps 1/4 with spinner, liveness indicator, and streaming output.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from textual.app import App

from ingot.ui.log_buffer import TaskLogBuffer
from ingot.ui.messages import post_task_event
from ingot.ui.screens.multi_task import MultiTaskScreen
from ingot.ui.screens.single_operation import SingleOperationScreen
from ingot.utils.console import console
from ingot.workflow.events import TaskEvent, TaskRunRecord, TaskRunStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Private Screen Subclasses
# =============================================================================


class _ReadyMultiTaskScreen(MultiTaskScreen):
    """MultiTaskScreen that signals readiness and tracks quit requests."""

    def __init__(
        self,
        runner: TextualTaskRunner,
        ticket_id: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(ticket_id=ticket_id, name=name, id=id, classes=classes)
        self._runner = runner

    def on_mount(self) -> None:
        super().on_mount()
        # Initialize records from runner and set parallel mode
        if self._runner.records:
            self.set_records(self._runner.records)
        self.parallel_mode = self._runner.parallel_mode
        self._runner._app_ready.set()

    def action_request_quit(self) -> None:
        app = self.app
        if isinstance(app, _RunnerApp):
            app.quit_by_user = True
        super().action_request_quit()


class _ReadySingleOpScreen(SingleOperationScreen):
    """SingleOperationScreen that signals readiness and tracks quit requests."""

    def __init__(
        self,
        runner: TextualTaskRunner,
        ticket_id: str = "",
        log_path: str = "",
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(ticket_id=ticket_id, log_path=log_path, name=name, id=id, classes=classes)
        self._runner = runner

    def on_mount(self) -> None:
        super().on_mount()
        self._runner._app_ready.set()

    def action_request_quit(self) -> None:
        app = self.app
        if isinstance(app, _RunnerApp):
            app.quit_by_user = True
        super().action_request_quit()


# =============================================================================
# Private App Class
# =============================================================================


class _RunnerApp(App[None]):
    """Textual App that hosts the appropriate screen for the runner."""

    def __init__(
        self,
        runner: TextualTaskRunner,
        single_operation_mode: bool = False,
    ) -> None:
        super().__init__()
        self._runner = runner
        self._single_operation_mode = single_operation_mode
        self.quit_by_user: bool = False

    def on_mount(self) -> None:
        if self._single_operation_mode:
            log_path = str(self._runner._log_path) if self._runner._log_path else ""
            self.push_screen(
                _ReadySingleOpScreen(
                    runner=self._runner,
                    ticket_id=self._runner.ticket_id,
                    log_path=log_path,
                )
            )
        else:
            self.push_screen(
                _ReadyMultiTaskScreen(
                    runner=self._runner,
                    ticket_id=self._runner.ticket_id,
                )
            )


# =============================================================================
# TextualTaskRunner
# =============================================================================


@dataclass
class TextualTaskRunner:
    """Textual-based task runner matching TaskRunnerUI's public API.

    Runs a Textual App in a background thread and forwards events to
    the active screen via ``post_task_event``.  Records are shared
    mutable objects — the screen's message handlers mutate them directly
    and ``stop()`` joins the app thread, ensuring all mutations are
    visible to the main thread afterward.
    """

    ticket_id: str = ""
    verbose_mode: bool = False
    single_operation_mode: bool = False
    status_message: str = "Processing..."
    parallel_mode: bool = False
    records: list[TaskRunRecord] = field(default_factory=list)

    # Private fields
    _log_dir: Path | None = field(default=None, init=False, repr=False)
    _log_path: Path | None = field(default=None, init=False, repr=False)
    _log_buffer: TaskLogBuffer | None = field(default=None, init=False, repr=False)
    _start_time: float = field(default=0.0, init=False, repr=False)
    _app: _RunnerApp | None = field(default=None, init=False, repr=False)
    _app_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _app_ready: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _app_crashed: Exception | None = field(default=None, init=False, repr=False)
    headless: bool = field(default=False, init=True, repr=False)

    # =========================================================================
    # Setup methods (before start)
    # =========================================================================

    def initialize_records(self, task_names: list[str]) -> None:
        """Initialize task run records from task names."""
        self.records = [
            TaskRunRecord(task_index=i, task_name=name) for i, name in enumerate(task_names)
        ]

    def set_log_dir(self, log_dir: Path) -> None:
        """Set the log directory for this run (multi-task mode)."""
        self._log_dir = log_dir

    def set_log_path(self, path: Path) -> None:
        """Set log file path and create buffer (single-operation mode)."""
        self._log_path = path
        self._log_buffer = TaskLogBuffer(log_path=path)

    def set_parallel_mode(self, enabled: bool) -> None:
        """Enable or disable parallel execution display mode."""
        self.parallel_mode = enabled

    def get_record(self, task_index: int) -> TaskRunRecord | None:
        """Get a task record by index."""
        if 0 <= task_index < len(self.records):
            return self.records[task_index]
        return None

    # =========================================================================
    # Lifecycle (start / stop / context manager)
    # =========================================================================

    def start(self) -> None:
        """Start the Textual app in a background thread.

        Blocks until the screen is mounted and ready, or raises
        ``RuntimeError`` on timeout or crash.
        """
        self._start_time = time.time()
        self._app_ready.clear()
        self._app_crashed = None

        app = _RunnerApp(
            runner=self,
            single_operation_mode=self.single_operation_mode,
        )
        self._app = app

        def _run_app() -> None:
            try:
                app.run(headless=self.headless)
            except Exception as exc:
                self._app_crashed = exc
                self._app_ready.set()  # Unblock the main thread

        self._app_thread = threading.Thread(target=_run_app, daemon=True)
        self._app_thread.start()

        # Wait for the screen to mount
        if not self._app_ready.wait(timeout=10):
            raise RuntimeError("Textual app failed to start within 10 seconds")

        if self._app_crashed is not None:
            raise RuntimeError(f"Textual app crashed on startup: {self._app_crashed}")

    def stop(self) -> None:
        """Stop the Textual app and clean up resources.

        Safe to call multiple times (idempotent).
        """
        if self._app is not None:
            try:
                self._app.call_from_thread(self._app.exit)
            except Exception:
                logger.debug("Failed to exit app (may already be closed)", exc_info=True)

        if self._app_thread is not None:
            self._app_thread.join(timeout=5)
            self._app_thread = None

        if self._log_buffer is not None:
            self._log_buffer.close()

        self._app = None

    def __enter__(self) -> TextualTaskRunner:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self.stop()

    # =========================================================================
    # Event forwarding
    # =========================================================================

    def handle_event(self, event: TaskEvent) -> None:
        """Forward a task event to the Textual screen (thread-safe).

        Uses ``call_from_thread`` internally, so this blocks until
        the message is processed by the Textual event loop.
        """
        if self._app is None:
            return
        try:
            post_task_event(self._app, event)
        except Exception:
            logger.debug("Failed to post event (app may be shutting down)", exc_info=True)

    def post_event(self, event: TaskEvent) -> None:
        """Thread-safe event posting — identical to ``handle_event``.

        Provided for API compatibility with ``TaskRunnerUI.post_event``
        which is used by the parallel executor.
        """
        self.handle_event(event)

    def refresh(self) -> None:
        """No-op — Textual auto-refreshes on message receipt.

        Provided for API compatibility with ``TaskRunnerUI.refresh``
        which is called by the parallel executor's pump loop.
        """

    # =========================================================================
    # Single-operation callback
    # =========================================================================

    def handle_output_line(self, line: str) -> None:
        """Callback for AI output lines (single-operation mode).

        Writes to log buffer (disk), then updates the screen display.
        """
        if self._log_buffer is not None:
            self._log_buffer.write(line)

        if self._app is None:
            return

        def _update_screen() -> None:
            screen = self._app.screen  # type: ignore[union-attr]
            if isinstance(screen, _ReadySingleOpScreen | SingleOperationScreen):
                screen.write_log_line(line)
                if line.strip():
                    screen.update_liveness(line)

        try:
            self._app.call_from_thread(_update_screen)
        except Exception:
            logger.debug("Failed to update screen (app may be shutting down)", exc_info=True)

    # =========================================================================
    # Quit handling
    # =========================================================================

    def check_quit_requested(self) -> bool:
        """Check if the user has requested to quit.

        Returns ``True`` if the user pressed quit in the TUI, or if the
        app is no longer running.
        """
        if self._app is None:
            return True
        return self._app.quit_by_user

    def clear_quit_request(self) -> None:
        """Reset the quit request flag."""
        if self._app is not None:
            self._app.quit_by_user = False

    # =========================================================================
    # State management
    # =========================================================================

    def mark_remaining_skipped(self, from_index: int) -> None:
        """Mark remaining pending tasks as skipped (for fail_fast).

        Updates the shared records and syncs each to the screen.
        """
        for i in range(from_index, len(self.records)):
            record = self.records[i]
            if record.status == TaskRunStatus.PENDING:
                record.status = TaskRunStatus.SKIPPED
                if self._app is not None:
                    try:
                        idx = i  # Capture for closure

                        def _sync(idx: int = idx, record: TaskRunRecord = record) -> None:
                            screen = self._app.screen  # type: ignore[union-attr]
                            if isinstance(screen, _ReadyMultiTaskScreen | MultiTaskScreen):
                                screen.update_record(idx, record)

                        self._app.call_from_thread(_sync)
                    except Exception:
                        logger.debug(
                            "Failed to sync skipped record (app may be shutting down)",
                            exc_info=True,
                        )

    def print_summary(self, success: bool | None = None) -> None:
        """Print execution summary after stop().

        Replicates ``TaskRunnerUI.print_summary`` logic exactly using
        Rich console output.

        Args:
            success: For single-operation mode, whether operation succeeded.
                     For multi-task mode, ignored (determined from records).
        """
        if self.single_operation_mode:
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
            return

        # Multi-task mode summary
        success_count = sum(1 for r in self.records if r.status == TaskRunStatus.SUCCESS)
        failed_count = sum(1 for r in self.records if r.status == TaskRunStatus.FAILED)
        skipped_count = sum(1 for r in self.records if r.status == TaskRunStatus.SKIPPED)

        console.print()
        console.print("[bold]Execution Complete[/bold]")
        console.print(f"  [green]\u2713 Succeeded:[/green] {success_count}")
        if failed_count > 0:
            console.print(f"  [red]\u2717 Failed:[/red] {failed_count}")
        if skipped_count > 0:
            console.print(f"  [yellow]\u2298 Skipped:[/yellow] {skipped_count}")

        if self._log_dir:
            console.print()
            console.print(f"[dim]Logs saved to: {self._log_dir}[/dim]")

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _format_elapsed_time(self) -> str:
        """Format elapsed time since start."""
        minutes, seconds = divmod(int(time.time() - self._start_time), 60)
        if minutes > 0:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"


__all__ = ["TextualTaskRunner"]
