"""Textual-based task runner orchestrator.

Forwards task events to the active Textual screen via ``post_task_event``.

**Threading model (Python 3.14+ compatible)**:
The primary API is :meth:`TextualTaskRunner.run_with_work`, which runs the
Textual app on the **main thread** (required for POSIX signal handlers) and
executes the backend work in a **background thread**.  The legacy
``start()``/``stop()`` context-manager interface is retained for headless
testing only.

Supports two modes:
1. **Multi-task mode** (default): Uses :class:`MultiTaskScreen` for Step 3
   task execution with task list, navigation, and parallel execution.
2. **Single-operation mode**: Uses :class:`SingleOperationScreen` for
   Steps 1/4 with spinner, liveness indicator, and streaming output.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textual.app import App
from textual.screen import Screen

from ingot.ui.log_buffer import TaskLogBuffer
from ingot.ui.messages import post_task_event
from ingot.ui.screens.multi_task import MultiTaskScreen
from ingot.ui.screens.single_operation import SingleOperationScreen
from ingot.utils.console import console
from ingot.workflow.events import (
    TaskEvent,
    TaskRunRecord,
    TaskRunStatus,
    create_run_finished_event,
)

logger = logging.getLogger(__name__)


# =============================================================================
# TUI Detection
# =============================================================================


def should_use_tui(override: bool | None = None) -> bool:
    """Determine if TUI should be used based on CLI override or TTY auto-detection."""
    # CLI override takes precedence
    if override is not None:
        return override

    # Check environment variable
    env_setting = os.environ.get("INGOT_TUI", "auto").lower()

    if env_setting == "true":
        return True
    if env_setting == "false":
        return False
    return sys.stdout.isatty()


# =============================================================================
# Private Helpers
# =============================================================================


def _quit_with_confirmation(screen: Screen[None], message: str = "Quit?") -> None:
    """Show a quit confirmation modal and exit the app if confirmed."""
    from ingot.ui.screens.quit_modal import QuitConfirmModal

    def _on_result(confirmed: bool | None) -> None:
        if confirmed:
            app = screen.app
            if isinstance(app, _RunnerApp):
                app.quit_by_user = True
            app.exit()

    screen.app.push_screen(QuitConfirmModal(message), callback=_on_result)


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
        self.verbose_mode = self._runner.verbose_mode
        self._runner._app_ready.set()

    def action_request_quit(self) -> None:
        _quit_with_confirmation(self)


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
        self.status_message = self._runner.status_message
        self.verbose_mode = self._runner.verbose_mode
        self._runner._app_ready.set()

    def action_request_quit(self) -> None:
        _quit_with_confirmation(self, "Cancel operation?")


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
    """Textual-based task runner orchestrator.

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
    _quit_by_user: bool = field(default=False, init=False, repr=False)
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
            self._log_buffer = None

        self._quit_by_user = self._app.quit_by_user if self._app else self._quit_by_user
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

    def run_with_work(self, work_fn: Callable[[], Any]) -> Any:
        """Run TUI on the main thread while *work_fn* runs in a background thread.

        Textual's POSIX driver registers signal handlers (``SIGTSTP``,
        ``SIGCONT``), which Python requires to happen on the **main thread**.
        This method ensures the Textual app owns the main thread while the
        backend work executes in a daemon thread.

        When *work_fn* returns (or raises), the Textual app is automatically
        exited.  If the user quits the TUI first, the app exits immediately;
        the work thread is still joined so its result (or exception) is
        captured.

        Args:
            work_fn: Zero-argument callable executed in the background thread.
                It may call ``self.handle_output_line`` or ``self.handle_event``
                for thread-safe TUI updates.

        Returns:
            Whatever *work_fn* returns.

        Raises:
            RuntimeError: If the Textual app fails to become ready within 10 s.
            Exception: Any exception raised by *work_fn* is re-raised.
        """
        self._start_time = time.time()
        self._app_ready.clear()
        self._app_crashed = None

        app = _RunnerApp(
            runner=self,
            single_operation_mode=self.single_operation_mode,
        )
        self._app = app

        work_result: Any = None
        work_exception: BaseException | None = None

        def _do_work() -> None:
            nonlocal work_result, work_exception

            # Block until the screen is mounted and ready
            if not self._app_ready.wait(timeout=10):
                work_exception = RuntimeError("Textual app failed to start within 10 seconds")
                try:
                    app.call_from_thread(app.exit)
                except Exception:
                    pass
                return

            if self._app_crashed is not None:
                work_exception = RuntimeError(
                    f"Textual app crashed on startup: {self._app_crashed}"
                )
                return

            try:
                work_result = work_fn()
            except BaseException as exc:
                work_exception = exc
            finally:
                # Signal the Textual app to exit once work is done
                try:
                    app.call_from_thread(app.exit)
                except Exception:
                    pass

        work_thread = threading.Thread(target=_do_work, daemon=True)
        work_thread.start()

        # Run Textual on the MAIN thread – blocks until app.exit() is called
        try:
            app.run(headless=self.headless)
        except Exception as exc:
            # If the app itself crashes, unblock the work thread
            self._app_crashed = exc
            self._app_ready.set()
            logger.debug("Textual app crashed during run", exc_info=True)

        # Wait for the work thread to finish (backend calls may still be
        # in progress if the user quit the TUI early)
        work_thread.join()

        # Clean up resources (log buffer close is idempotent, safe if
        # stop() was also called via the legacy context-manager path)
        if self._log_buffer is not None:
            self._log_buffer.close()
            self._log_buffer = None
        self._quit_by_user = self._app.quit_by_user if self._app else False
        self._app = None

        if work_exception is not None:
            raise work_exception  # type: ignore[misc]
        return work_result

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

    def emit_run_finished(self) -> None:
        """Emit a RUN_FINISHED event derived from current record statuses."""
        success_count = sum(1 for r in self.records if r.status == TaskRunStatus.SUCCESS)
        failed_count = sum(1 for r in self.records if r.status == TaskRunStatus.FAILED)
        skipped_count = sum(1 for r in self.records if r.status == TaskRunStatus.SKIPPED)
        self.handle_event(
            create_run_finished_event(len(self.records), success_count, failed_count, skipped_count)
        )

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

        Returns ``True`` only if the user explicitly pressed quit in the TUI.
        """
        if self._app is not None:
            return self._app.quit_by_user
        return self._quit_by_user

    def clear_quit_request(self) -> None:
        """Reset the quit request flag."""
        self._quit_by_user = False
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

        Prints a Rich console summary of task results.

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
