"""Git utilities for Step 3 execution.

This module provides utilities for interacting with git during the
execution phase, including smart diff collection that handles large
changesets appropriately.

Key features:
- Baseline-anchored diffs: Capture a baseline ref at workflow start and
  generate diffs relative to that baseline for deterministic, scoped changes.
- Dirty working tree detection: Detect uncommitted changes before workflow
  modifications begin.
- Binary file handling: Gracefully handle binary files in diffs.
"""

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from spec.utils.console import print_warning


class DirtyTreePolicy(Enum):
    """Policy for handling dirty working tree at workflow start."""

    FAIL_FAST = "fail_fast"  # Fail immediately with clear error
    WARN_AND_CONTINUE = "warn_and_continue"  # Warn but continue (not recommended)


@dataclass
class DiffContext:
    """Context for generating baseline-anchored diffs.

    Attributes:
        baseline_ref: The git ref (commit SHA) captured at workflow start.
        has_initial_dirty_state: Whether the tree was dirty at baseline capture.
        policy: Policy for handling dirty working tree.
    """

    baseline_ref: str
    has_initial_dirty_state: bool = False
    policy: DirtyTreePolicy = DirtyTreePolicy.FAIL_FAST


class DirtyWorkingTreeError(Exception):
    """Raised when the working tree has uncommitted changes that would pollute diffs."""

    pass


def capture_baseline() -> str:
    """Capture the current HEAD as the baseline for diff operations.

    This should be called at the start of Step 3, before any modifications
    are made. The returned ref is used to scope all diffs to changes
    introduced by the current workflow.

    Returns:
        The current HEAD commit SHA.

    Raises:
        subprocess.CalledProcessError: If git command fails.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_dirty_working_tree(
    policy: DirtyTreePolicy = DirtyTreePolicy.FAIL_FAST,
) -> bool:
    """Check if the working tree has uncommitted changes.

    This is used to detect pre-existing dirty state before the workflow
    begins modifications. Checks for:
    - Unstaged changes to tracked files
    - Staged changes (index vs HEAD)
    - Untracked files

    Args:
        policy: How to handle a dirty working tree.

    Returns:
        True if the working tree is clean, False if dirty but continuing
        (only when policy is WARN_AND_CONTINUE).

    Raises:
        DirtyWorkingTreeError: If working tree is dirty and policy is FAIL_FAST.
    """
    # Check for unstaged changes (working tree vs index)
    result_unstaged = subprocess.run(
        ["git", "diff", "--quiet"],
        capture_output=True,
    )

    # Check for staged changes (index vs HEAD)
    result_staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
    )

    # Check for untracked files
    result_untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
    )
    has_untracked = bool(result_untracked.stdout.strip())

    is_dirty = (
        result_unstaged.returncode != 0
        or result_staged.returncode != 0
        or has_untracked
    )

    if is_dirty:
        if policy == DirtyTreePolicy.FAIL_FAST:
            # Get status for error message
            status_result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
            )
            status_output = status_result.stdout.strip() if status_result.returncode == 0 else ""

            raise DirtyWorkingTreeError(
                "Working tree has uncommitted changes that would pollute diffs.\n"
                "Please commit or stash your changes before running this workflow.\n\n"
                "Uncommitted changes:\n"
                f"{status_output}\n\n"
                "To stash changes: git stash push -m 'WIP before spec workflow'\n"
                "To commit changes: git add -A && git commit -m 'WIP'"
            )
        else:
            print_warning(
                "Working tree has uncommitted changes. "
                "Diffs may include unrelated modifications."
            )
            return False

    return True


def get_diff_from_baseline(
    baseline_ref: str,
    *,
    stat_only: bool = False,
    no_color: bool = True,
    no_ext_diff: bool = True,
) -> tuple[str, bool]:
    """Get diff output between baseline and current HEAD/working tree.

    Generates a diff scoped to changes introduced since the baseline ref.
    Uses --no-color and --no-ext-diff for clean, parseable output.

    Args:
        baseline_ref: The baseline commit SHA to diff from.
        stat_only: If True, return only stat summary (for large diffs).
        no_color: If True, disable color codes in output (default: True).
        no_ext_diff: If True, disable external diff tools (default: True).

    Returns:
        Tuple of (diff_output, git_error) where:
        - diff_output is the diff text
        - git_error is True if git command failed
    """
    cmd = ["git", "diff"]

    if no_color:
        cmd.append("--no-color")
    if no_ext_diff:
        cmd.append("--no-ext-diff")
    if stat_only:
        cmd.append("--stat")

    # Diff from baseline to HEAD (committed changes only)
    # If there are uncommitted changes, they're included in the working tree diff
    cmd.extend([baseline_ref, "HEAD"])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        print_warning(f"Git diff from baseline failed: {stderr}")
        return "", True

    return result.stdout, False


def get_working_tree_diff_from_baseline(
    baseline_ref: str,
    *,
    stat_only: bool = False,
    no_color: bool = True,
    no_ext_diff: bool = True,
) -> tuple[str, bool]:
    """Get diff including uncommitted working tree changes from baseline.

    This variant includes all changes - both committed since baseline AND
    uncommitted working tree modifications.

    Args:
        baseline_ref: The baseline commit SHA to diff from.
        stat_only: If True, return only stat summary.
        no_color: If True, disable color codes.
        no_ext_diff: If True, disable external diff tools.

    Returns:
        Tuple of (diff_output, git_error).
    """
    cmd = ["git", "diff"]

    if no_color:
        cmd.append("--no-color")
    if no_ext_diff:
        cmd.append("--no-ext-diff")
    if stat_only:
        cmd.append("--stat")

    # Diff from baseline to working tree (includes uncommitted changes)
    cmd.append(baseline_ref)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "unknown error"
        print_warning(f"Git diff from baseline failed: {stderr}")
        return "", True

    return result.stdout, False


def filter_binary_files_from_diff(diff_output: str) -> str:
    """Filter binary file entries from diff output to avoid token issues.

    Binary files in diffs appear as:
    "Binary files a/path and b/path differ"

    These are replaced with a marker that indicates a binary file changed
    without including the raw binary content.

    Args:
        diff_output: Raw git diff output.

    Returns:
        Filtered diff with binary content markers.
    """
    # Pattern matches "Binary files a/... and b/... differ"
    binary_pattern = re.compile(
        r"Binary files a/(.+?) and b/(.+?) differ",
        re.MULTILINE,
    )

    def replace_binary(match: re.Match) -> str:
        path = match.group(2)  # Use the "b/" (new) path
        return f"[BINARY FILE CHANGED: {path}]"

    return binary_pattern.sub(replace_binary, diff_output)


def parse_stat_total_lines(stat_output: str) -> int:
    """Parse total changed lines from git diff --stat output.

    The stat output ends with a summary line like:
    "10 files changed, 500 insertions(+), 100 deletions(-)"

    Args:
        stat_output: Output from git diff --stat

    Returns:
        Total lines changed (insertions + deletions)
    """
    # Match the summary line at the end of stat output
    # Pattern: "X file(s) changed, Y insertion(s)(+), Z deletion(s)(-)"
    match = re.search(
        r"(\d+)\s+insertions?\(\+\).*?(\d+)\s+deletions?\(-\)",
        stat_output,
    )
    if match:
        return int(match.group(1)) + int(match.group(2))

    # Try matching insertions only
    match = re.search(r"(\d+)\s+insertions?\(\+\)", stat_output)
    if match:
        return int(match.group(1))

    # Try matching deletions only
    match = re.search(r"(\d+)\s+deletions?\(-\)", stat_output)
    if match:
        return int(match.group(1))

    return 0


def parse_stat_file_count(stat_output: str) -> int:
    """Parse number of changed files from git diff --stat output.

    Args:
        stat_output: Output from git diff --stat

    Returns:
        Number of files changed
    """
    match = re.search(r"(\d+)\s+files?\s+changed", stat_output)
    if match:
        return int(match.group(1))
    return 0


def get_smart_diff(max_lines: int = 2000, max_files: int = 20) -> tuple[str, bool, bool]:
    """Get diff output, using --stat only for large changes.

    Implements smart diff strategy to handle large diffs that could
    exceed AI context window limits. For large changes, returns only
    the stat summary and instructs the reviewer to inspect specific
    files as needed.

    Args:
        max_lines: Maximum lines before falling back to stat-only (default: 2000)
        max_files: Maximum files before falling back to stat-only (default: 20)

    Returns:
        Tuple of (diff_output, is_truncated, git_error) where:
        - is_truncated is True if only stat output was returned due to large changeset
        - git_error is True if git command failed (diff may be unreliable)
    """
    # First get stat output to assess change size
    stat_result = subprocess.run(
        ["git", "diff", "--stat"],
        capture_output=True,
        text=True,
    )

    # Check for git errors
    if stat_result.returncode != 0:
        stderr = stat_result.stderr.strip() if stat_result.stderr else "unknown error"
        print_warning(f"Git diff --stat failed (exit code {stat_result.returncode}): {stderr}")
        # Return empty with error flag - caller should warn but continue
        return "", False, True

    stat_output = stat_result.stdout

    if not stat_output.strip():
        # No changes - return empty (not an error, just empty diff)
        return "", False, False

    # Parse stat to get counts
    lines_changed = parse_stat_total_lines(stat_output)
    files_changed = parse_stat_file_count(stat_output)

    # Check if diff is too large
    if lines_changed > max_lines or files_changed > max_files:
        # Return stat-only with instructions
        truncated_output = f"""## Git Diff Summary (Large Changeset)

{stat_output}

**Note**: This changeset is large ({files_changed} files, {lines_changed} lines changed).
To review specific files in detail, use: `git diff -- <file_path>`
Focus on files most critical to the implementation plan."""
        return truncated_output, True, False

    # Small enough for full diff
    full_result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True,
    )

    # Check for git errors on full diff
    if full_result.returncode != 0:
        stderr = full_result.stderr.strip() if full_result.stderr else "unknown error"
        print_warning(f"Git diff failed (exit code {full_result.returncode}): {stderr}")
        # Fall back to stat output with error flag
        return stat_output, True, True

    return full_result.stdout, False, False


def get_smart_diff_from_baseline(
    baseline_ref: str,
    *,
    max_lines: int = 2000,
    max_files: int = 20,
    include_working_tree: bool = True,
) -> tuple[str, bool, bool]:
    """Get baseline-anchored diff output, using --stat only for large changes.

    Like get_smart_diff(), but scopes changes to those introduced since the
    baseline ref. This ensures diffs don't include pre-existing dirty changes.

    Args:
        baseline_ref: The baseline commit SHA to diff from.
        max_lines: Maximum lines before falling back to stat-only (default: 2000)
        max_files: Maximum files before falling back to stat-only (default: 20)
        include_working_tree: If True, include uncommitted changes in diff.
            If False, only show committed changes since baseline.

    Returns:
        Tuple of (diff_output, is_truncated, git_error) where:
        - diff_output is the diff text (filtered for binary files)
        - is_truncated is True if only stat output was returned due to large changeset
        - git_error is True if git command failed (diff may be unreliable)
    """
    # Choose diff function based on whether we include working tree
    if include_working_tree:
        stat_output, stat_error = get_working_tree_diff_from_baseline(
            baseline_ref, stat_only=True
        )
    else:
        stat_output, stat_error = get_diff_from_baseline(
            baseline_ref, stat_only=True
        )

    # Check for git errors
    if stat_error:
        return "", False, True

    if not stat_output.strip():
        # No changes - return empty (not an error, just empty diff)
        return "", False, False

    # Parse stat to get counts
    lines_changed = parse_stat_total_lines(stat_output)
    files_changed = parse_stat_file_count(stat_output)

    # Check if diff is too large
    if lines_changed > max_lines or files_changed > max_files:
        # Return stat-only with instructions
        truncated_output = f"""## Git Diff Summary (Large Changeset)

{stat_output}

**Note**: This changeset is large ({files_changed} files, {lines_changed} lines changed).
To review specific files in detail, use: `git diff {baseline_ref} -- <file_path>`
Focus on files most critical to the implementation plan."""
        return truncated_output, True, False

    # Small enough for full diff
    if include_working_tree:
        full_output, full_error = get_working_tree_diff_from_baseline(baseline_ref)
    else:
        full_output, full_error = get_diff_from_baseline(baseline_ref)

    # Check for git errors on full diff
    if full_error:
        # Fall back to stat output with error flag
        return stat_output, True, True

    # Filter binary file content to avoid token issues
    filtered_output = filter_binary_files_from_diff(full_output)

    return filtered_output, False, False


# Backwards-compatible aliases (underscore-prefixed)
_parse_stat_total_lines = parse_stat_total_lines
_parse_stat_file_count = parse_stat_file_count
_get_smart_diff = get_smart_diff


__all__ = [
    # Baseline-anchored diff functions
    "DirtyTreePolicy",
    "DiffContext",
    "DirtyWorkingTreeError",
    "capture_baseline",
    "check_dirty_working_tree",
    "get_diff_from_baseline",
    "get_working_tree_diff_from_baseline",
    "filter_binary_files_from_diff",
    "get_smart_diff_from_baseline",
    # Legacy functions (still usable for simple cases)
    "parse_stat_total_lines",
    "parse_stat_file_count",
    "get_smart_diff",
    # Backwards-compatible aliases
    "_parse_stat_total_lines",
    "_parse_stat_file_count",
    "_get_smart_diff",
]

