"""Log management utilities for Step 3 execution.

This module provides utilities for managing run log directories,
including creating timestamped directories and cleaning up old runs.
"""

import os
import re
import shutil
from pathlib import Path

from ingot.workflow.events import format_run_directory

# Matches timestamped run directory names: YYYYMMDD_HHMMSS
_TIMESTAMP_DIR_RE = re.compile(r"^\d{8}_\d{6}$")

# Default log retention count
DEFAULT_LOG_RETENTION = 10


def get_log_base_dir() -> Path:
    """Get the base directory for run logs.

    Returns:
        Path to the log base directory.
    """
    env_dir = os.environ.get("INGOT_LOG_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(".ingot/runs")


def create_run_log_dir(safe_ticket_id: str) -> Path:
    """Create a timestamped log directory for this run.

    Args:
        safe_ticket_id: Filesystem-safe ticket identifier (use ticket.safe_filename_stem).
            MUST be sanitized - raw ticket IDs may contain unsafe chars like '/'.

    Returns:
        Path to the created log directory.
    """
    base_dir = get_log_base_dir()
    ticket_dir = base_dir / safe_ticket_id
    run_dir = ticket_dir / format_run_directory()

    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def cleanup_old_runs(safe_ticket_id: str, keep_count: int = DEFAULT_LOG_RETENTION) -> None:
    """Remove old run directories beyond retention limit.

    Args:
        safe_ticket_id: Filesystem-safe ticket identifier (use ticket.safe_filename_stem).
            MUST be sanitized - raw ticket IDs may contain unsafe chars like '/'.
        keep_count: Number of runs to keep.
    """
    base_dir = get_log_base_dir()
    ticket_dir = base_dir / safe_ticket_id

    if not ticket_dir.exists():
        return

    # Get only timestamped run directories (YYYYMMDD_HHMMSS), ignoring
    # non-run subdirs like plan_generation/, test_execution/, doc_update/
    run_dirs = sorted(
        [d for d in ticket_dir.iterdir() if d.is_dir() and _TIMESTAMP_DIR_RE.match(d.name)],
        key=lambda d: d.name,
        reverse=True,
    )

    # Remove directories beyond retention limit
    for old_dir in run_dirs[keep_count:]:
        try:
            shutil.rmtree(old_dir)
        except Exception:
            pass  # Ignore cleanup errors


__all__ = [
    "DEFAULT_LOG_RETENTION",
    "get_log_base_dir",
    "create_run_log_dir",
    "cleanup_old_runs",
]
