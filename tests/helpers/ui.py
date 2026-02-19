"""Shared test helpers for Textual UI tests."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

from ingot.workflow.events import TaskRunRecord, TaskRunStatus


def make_records(*statuses: TaskRunStatus) -> list[TaskRunRecord]:
    """Create TaskRunRecord list with appropriate timestamps per status."""
    now = time.time()
    records: list[TaskRunRecord] = []
    for i, status in enumerate(statuses):
        rec = TaskRunRecord(task_index=i, task_name=f"Task {i}")
        rec.status = status
        if status in (TaskRunStatus.RUNNING, TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
            rec.start_time = now - 5
        if status in (TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
            rec.end_time = now
        records.append(rec)
    return records


def make_record_with_log_buffer(
    index: int,
    name: str,
    status: TaskRunStatus = TaskRunStatus.RUNNING,
    tail_lines: list[str] | None = None,
    log_path: str = "/tmp/test.log",
) -> TaskRunRecord:
    """Create a TaskRunRecord with a mock log_buffer."""
    now = time.time()
    rec = TaskRunRecord(task_index=index, task_name=name)
    rec.status = status
    if status in (TaskRunStatus.RUNNING, TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
        rec.start_time = now - 5
    if status in (TaskRunStatus.SUCCESS, TaskRunStatus.FAILED):
        rec.end_time = now

    mock_buffer = MagicMock()
    mock_buffer.log_path = Path(log_path)
    mock_buffer.get_tail = MagicMock(return_value=tail_lines or [])
    rec.log_buffer = mock_buffer
    return rec
