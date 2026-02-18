"""Textual Message types and event bridge for TaskEvent integration.

Defines Message subclasses that map to TaskEvent types, plus a bridge
function (``post_task_event``) that converts a TaskEvent into the
corresponding Message and posts it to the active Textual screen from
any thread.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from textual.message import Message

from ingot.workflow.events import TaskEvent, TaskEventType

if TYPE_CHECKING:
    from textual.app import App


# =============================================================================
# Message classes
# =============================================================================


class TaskStarted(Message):
    """A task has begun execution."""

    def __init__(self, task_index: int, task_name: str, timestamp: float) -> None:
        self.task_index = task_index
        self.task_name = task_name
        self.timestamp = timestamp
        super().__init__()


class TaskOutput(Message):
    """A task emitted an output line."""

    def __init__(self, task_index: int, task_name: str, line: str) -> None:
        self.task_index = task_index
        self.task_name = task_name
        self.line = line
        super().__init__()


class TaskFinished(Message):
    """A task completed execution."""

    def __init__(
        self,
        task_index: int,
        task_name: str,
        status: str,
        duration: float,
        error: str | None = None,
        timestamp: float = 0.0,
    ) -> None:
        self.task_index = task_index
        self.task_name = task_name
        self.status = status
        self.duration = duration
        self.error = error
        self.timestamp = timestamp
        super().__init__()


class RunFinished(Message):
    """All tasks in the run have completed."""

    def __init__(self, total: int, success: int, failed: int, skipped: int) -> None:
        self.total = total
        self.success = success
        self.failed = failed
        self.skipped = skipped
        super().__init__()


class QuitRequested(Message):
    """User requested to quit the TUI."""


class LivenessUpdate(Message):
    """Liveness indicator update for single-operation screens."""

    def __init__(self, line: str) -> None:
        self.line = line
        super().__init__()


# =============================================================================
# TaskEvent data-dict keys (shared with ingot.workflow.events factories)
# =============================================================================

_KEY_LINE = "line"
_KEY_STATUS = "status"
_KEY_DURATION = "duration"
_KEY_ERROR = "error"
_KEY_TOTAL_TASKS = "total_tasks"
_KEY_SUCCESS_COUNT = "success_count"
_KEY_FAILED_COUNT = "failed_count"
_KEY_SKIPPED_COUNT = "skipped_count"

# =============================================================================
# Bridge functions
# =============================================================================


def _is_in_async_context() -> bool:
    """Return True when called from within a running asyncio event loop."""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def convert_task_event(event: TaskEvent) -> Message | None:
    """Convert a ``TaskEvent`` into the corresponding Textual ``Message``.

    Returns ``None`` for ``RUN_STARTED`` (records are created before the
    screen exists, so no message is needed).
    """
    match event.event_type:
        case TaskEventType.TASK_STARTED:
            return TaskStarted(
                task_index=event.task_index,
                task_name=event.task_name,
                timestamp=event.timestamp,
            )

        case TaskEventType.TASK_OUTPUT:
            line = (event.data or {}).get(_KEY_LINE, "")
            return TaskOutput(
                task_index=event.task_index,
                task_name=event.task_name,
                line=line,
            )

        case TaskEventType.TASK_FINISHED:
            data = event.data or {}
            return TaskFinished(
                task_index=event.task_index,
                task_name=event.task_name,
                status=data.get(_KEY_STATUS, "failed"),
                duration=data.get(_KEY_DURATION, 0.0),
                error=data.get(_KEY_ERROR),
                timestamp=event.timestamp,
            )

        case TaskEventType.RUN_FINISHED:
            data = event.data or {}
            return RunFinished(
                total=data.get(_KEY_TOTAL_TASKS, 0),
                success=data.get(_KEY_SUCCESS_COUNT, 0),
                failed=data.get(_KEY_FAILED_COUNT, 0),
                skipped=data.get(_KEY_SKIPPED_COUNT, 0),
            )

        case _:
            # RUN_STARTED and unknown types → no message
            return None


def post_task_event(app: App, event: TaskEvent) -> None:  # type: ignore[type-arg]
    """Convert *event* and post the resulting message to the active screen.

    Posts to ``app.screen`` so the message reaches the Screen-level
    handlers (``on_task_started``, etc.).  Textual messages bubble UP
    the DOM, so posting to the App would bypass Screen handlers.

    Note: this targets whatever screen is on top of the stack at call
    time.  Callers must ensure the expected screen is active.

    Uses ``app.call_from_thread`` when called from a non-async (worker)
    thread, ensuring thread safety.  When already inside the async event
    loop, posts directly.
    """
    message = convert_task_event(event)
    if message is None:
        return

    def _post() -> None:
        app.screen.post_message(message)

    if _is_in_async_context():
        _post()
    else:
        app.call_from_thread(_post)


__all__ = [
    "TaskStarted",
    "TaskOutput",
    "TaskFinished",
    "RunFinished",
    "QuitRequested",
    "LivenessUpdate",
    "convert_task_event",
    "post_task_event",
]
