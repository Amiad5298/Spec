"""TUI for single long-running streaming operations.

.. deprecated::
    This module is deprecated. Use ``TaskRunnerUI`` from ``spec.ui.tui``
    with ``single_operation_mode=True`` instead.

This module provides a deprecated wrapper around TaskRunnerUI for
backward compatibility. New code should import TaskRunnerUI directly::

    from spec.ui.tui import TaskRunnerUI

    ui = TaskRunnerUI(
        status_message="Processing...",
        ticket_id="TICKET-123",
        single_operation_mode=True,
    )
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from spec.ui.tui import (
    DEFAULT_VERBOSE_LINES,
    MAX_LIVENESS_WIDTH,
    REFRESH_RATE,
    TaskRunnerUI,
)

# Re-export constants for backward compatibility
__all__ = [
    "StreamingOperationUI",
    "DEFAULT_VERBOSE_LINES",
    "MAX_LIVENESS_WIDTH",
    "REFRESH_RATE",
]

if TYPE_CHECKING:
    pass


class StreamingOperationUI:
    """Deprecated TUI for single long-running streaming operations.

    .. deprecated::
        Use ``TaskRunnerUI`` with ``single_operation_mode=True`` instead.
        This class is a thin wrapper for backward compatibility.

    Example migration::

        # Old (deprecated):
        from spec.ui.plan_tui import StreamingOperationUI
        ui = StreamingOperationUI(status_message="Running...", ticket_id="T-1")
        if ui.quit_requested:
            ...

        # New (recommended):
        from spec.ui.tui import TaskRunnerUI
        ui = TaskRunnerUI(status_message="Running...", ticket_id="T-1",
                          single_operation_mode=True)
        if ui.check_quit_requested():
            ...
    """

    def __init__(
        self,
        status_message: str = "Processing...",
        ticket_id: str = "",
        verbose_mode: bool = False,
    ) -> None:
        """Initialize StreamingOperationUI (deprecated).

        Args:
            status_message: Message to display next to spinner.
            ticket_id: Ticket ID for display in header.
            verbose_mode: Whether to show full log output.
        """
        warnings.warn(
            "StreamingOperationUI is deprecated. Use TaskRunnerUI with "
            "single_operation_mode=True instead. See spec.ui.tui module.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._tui = TaskRunnerUI(
            status_message=status_message,
            ticket_id=ticket_id,
            verbose_mode=verbose_mode,
            single_operation_mode=True,
        )

    @property
    def quit_requested(self) -> bool:
        """Check if quit was requested (deprecated property).

        .. deprecated::
            Use ``check_quit_requested()`` method instead for thread safety.
        """
        return self._tui.check_quit_requested()

    @quit_requested.setter
    def quit_requested(self, value: bool) -> None:
        """Set quit requested (deprecated, for backward compatibility)."""
        if value:
            # Trigger internal quit by calling private method (for compat only)
            self._tui._handle_quit()
        else:
            self._tui.clear_quit_request()

    def check_quit_requested(self) -> bool:
        """Thread-safe check if quit was requested.

        Returns:
            True if quit was requested.
        """
        return self._tui.check_quit_requested()

    def set_log_path(self, path: Path) -> None:
        """Set log file path and create buffer.

        Args:
            path: Path to the log file.
        """
        self._tui.set_log_path(path)

    def handle_output_line(self, line: str) -> None:
        """Callback for AI output lines.

        Args:
            line: A single line of AI output.
        """
        self._tui.handle_output_line(line)

    def start(self) -> None:
        """Start the TUI display."""
        self._tui.start()

    def stop(self) -> None:
        """Stop the TUI display."""
        self._tui.stop()

    def __enter__(self) -> StreamingOperationUI:
        """Context manager entry."""
        self._tui.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self._tui.stop()

    def refresh(self) -> None:
        """Refresh the display."""
        self._tui.refresh()

    def print_summary(self, success: bool) -> None:
        """Print summary after completion.

        Args:
            success: Whether the operation completed successfully.
        """
        self._tui.print_summary(success)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "StreamingOperationUI",
]
