"""Step 3: Execute Implementation - Two-Phase Execution Model.

This module implements the third step of the workflow - executing
the task list with a two-phase execution model:

Phase 1: Sequential execution of fundamental tasks (dependencies, order matters)
Phase 2: Parallel execution of independent tasks (can run concurrently)

Philosophy: Trust the AI. If it returns success, it succeeded.
Don't nanny it with file checks and retry loops.

Each task runs in its own clean context (using dont_save_session=True)
to maintain focus and avoid context pollution.

Supports two display modes:
- TUI mode: Rich interactive display with task list and log panels
- Fallback mode: Simple line-based output for CI/non-TTY environments

Helper modules:
- git_utils: Git diff collection and parsing
- review: Code review prompting and status parsing
- autofix: Auto-fix logic for review feedback
- log_management: Run log directory management
- prompts: Task execution prompt templates
"""

import functools
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ingot.integrations.backends.base import AIBackend
from ingot.integrations.backends.errors import BackendRateLimitError
from ingot.integrations.git import find_repo_root, get_current_branch
from ingot.ui.log_buffer import TaskLogBuffer
from ingot.ui.prompts import prompt_confirm
from ingot.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
)
from ingot.utils.retry import (
    RateLimitExceededError,
    with_rate_limit_retry,
)
from ingot.workflow.events import (
    create_task_finished_event,
    create_task_output_event,
    create_task_started_event,
    format_log_filename,
)
from ingot.workflow.git_utils import (
    DirtyWorkingTreeError,
    capture_baseline,
    check_dirty_working_tree,
)
from ingot.workflow.log_management import (
    cleanup_old_runs,
    create_run_log_dir,
    get_log_base_dir,
)
from ingot.workflow.prompts import (
    POST_IMPLEMENTATION_TEST_PROMPT,
    build_self_correction_prompt,
    build_task_prompt,
)
from ingot.workflow.review import ReviewOutcome, run_phase_review
from ingot.workflow.state import WorkflowState
from ingot.workflow.tasks import (
    Task,
    get_pending_fundamental_tasks,
    get_pending_independent_tasks,
    get_pending_tasks,
    mark_task_complete,
    parse_task_list,
)

# Type alias for task status
TaskStatus = Literal["success", "failed", "skipped"]

# Log directory names for workflow steps
LOG_DIR_TEST_EXECUTION = "test_execution"


@dataclass
class Step3Result:
    """Result of Step 3 execution."""

    success: bool
    needs_replan: bool = False
    replan_feedback: str = ""


@dataclass
class SelfCorrectionResult:
    """Result of task execution with self-correction loop."""

    success: bool
    final_output: str = ""
    attempt_count: int = 1
    total_attempts: int = 1


@functools.lru_cache(maxsize=8)
def _get_repo_root(cwd: str | None = None) -> Path:
    """Get repository root, falling back to the provided cwd or Path.cwd()."""
    return find_repo_root() or (Path(cwd) if cwd else Path.cwd())


def _capture_baseline_for_diffs(state: WorkflowState) -> bool:
    """Capture baseline ref and check for dirty working tree.

    This must be called at the start of Step 3 before any modifications.
    It captures the current HEAD as the baseline for all subsequent diff
    operations, ensuring diffs are scoped to changes introduced by this
    workflow run.

    The dirty tree policy is read from state.dirty_tree_policy:
    - FAIL_FAST: Abort if working tree is dirty (default, recommended)
    - WARN_AND_CONTINUE: Warn but continue (diffs may include unrelated changes)

    """
    # Check for dirty working tree before capturing baseline
    try:
        is_clean = check_dirty_working_tree(policy=state.dirty_tree_policy)
        if not is_clean:
            # WARN_AND_CONTINUE policy - tree is dirty but we continue
            print_warning(
                "Continuing with dirty working tree. Review diffs may include pre-existing changes."
            )
    except DirtyWorkingTreeError as e:
        # FAIL_FAST policy - abort on dirty tree
        print_error(str(e))
        return False

    # Capture baseline ref
    try:
        baseline_ref = capture_baseline()
        state.diff_baseline_ref = baseline_ref
        print_info(f"Captured baseline for diff operations: {baseline_ref[:8]}")
        return True
    except Exception as e:
        print_error(f"Failed to capture git baseline: {e}")
        return False


def step_3_execute(
    state: WorkflowState,
    *,
    backend: AIBackend,
    use_tui: bool | None = None,
    verbose: bool = False,
) -> Step3Result:
    """Execute Step 3: Two-phase task execution.

    Phase 1: Sequential execution of fundamental tasks
    Phase 2: Parallel execution of independent tasks

    Supports two modes:
    - TUI mode: Rich interactive display with task list and log panels
    - Fallback mode: Simple line-based output for CI/non-TTY environments

    Before execution begins, captures a baseline git ref to ensure all
    subsequent diff operations are scoped to changes introduced by this
    workflow run. Fails fast if the working tree has uncommitted changes.

    """
    print_header("Step 3: Execute Implementation")

    # Capture baseline and check for dirty working tree
    # This MUST happen before any modifications begin
    if not _capture_baseline_for_diffs(state):
        print_error("Cannot proceed with dirty working tree.")
        print_info("Please commit or stash uncommitted changes first.")
        return Step3Result(success=False)

    # Verify task list exists
    tasklist_path = state.get_tasklist_path()
    if not tasklist_path.exists():
        print_error(f"Task list not found: {tasklist_path}")
        return Step3Result(success=False)

    # Parse all tasks
    tasks = parse_task_list(tasklist_path.read_text())

    # Disable parallel execution if backend doesn't support it
    if not backend.supports_parallel:
        state.parallel_execution_enabled = False

    # Separate into phases
    pending_fundamental = get_pending_fundamental_tasks(tasks)
    pending_independent = get_pending_independent_tasks(tasks)

    # Handle legacy task lists (no categorization = all fundamental)
    if not pending_fundamental and not pending_independent:
        # Legacy mode: treat all as fundamental
        pending_fundamental = get_pending_tasks(tasks)
        pending_independent = []

    total_pending = len(pending_fundamental) + len(pending_independent)
    if total_pending == 0:
        print_success("All tasks already completed!")
        return Step3Result(success=True)

    print_info(
        f"Found {len(pending_fundamental)} fundamental + "
        f"{len(pending_independent)} independent tasks"
    )

    # Setup (use safe_filename_stem for filesystem operations)
    plan_path = state.get_plan_path()
    log_dir = create_run_log_dir(state.ticket.safe_filename_stem)
    cleanup_old_runs(state.ticket.safe_filename_stem)

    failed_tasks: list[str] = []

    # Determine execution mode
    from ingot.ui.tui import _should_use_tui

    use_tui_mode = _should_use_tui(use_tui)

    # PHASE 1: Execute fundamental tasks sequentially
    if pending_fundamental:
        print_header("Phase 1: Fundamental Tasks (Sequential)")

        if use_tui_mode:
            phase1_failed = _execute_with_tui(
                state,
                pending_fundamental,
                plan_path,
                tasklist_path,
                log_dir,
                backend=backend,
                verbose=verbose,
                phase="fundamental",
            )
        else:
            phase1_failed = _execute_fallback(
                state, pending_fundamental, plan_path, tasklist_path, log_dir, backend=backend
            )

        failed_tasks.extend(phase1_failed)

        # If fail_fast and we had failures, stop here
        if failed_tasks and state.fail_fast:
            print_error("Phase 1 failures with fail_fast enabled. Stopping.")
            return Step3Result(success=False)

    # PHASE 2: Execute independent tasks in parallel
    if pending_independent and state.parallel_execution_enabled:
        print_header("Phase 2: Independent Tasks (Parallel)")

        if use_tui_mode:
            phase2_failed = _execute_parallel_with_tui(
                state,
                pending_independent,
                plan_path,
                tasklist_path,
                log_dir,
                backend=backend,
                verbose=verbose,
            )
        else:
            phase2_failed = _execute_parallel_fallback(
                state, pending_independent, plan_path, tasklist_path, log_dir, backend=backend
            )

        failed_tasks.extend(phase2_failed)
    elif pending_independent:
        # Parallel disabled, run sequentially
        print_info("Parallel execution disabled. Running independent tasks sequentially.")
        if use_tui_mode:
            phase2_failed = _execute_with_tui(
                state,
                pending_independent,
                plan_path,
                tasklist_path,
                log_dir,
                backend=backend,
                verbose=verbose,
                phase="independent",
            )
        else:
            phase2_failed = _execute_fallback(
                state, pending_independent, plan_path, tasklist_path, log_dir, backend=backend
            )
        failed_tasks.extend(phase2_failed)

    # Handle failures
    if failed_tasks:
        if not prompt_confirm(
            "Some tasks failed. Proceed to post-implementation steps?",
            default=True,
        ):
            print_info("Exiting Step 3 early due to task failures.")
            return Step3Result(success=False)

    # Post-execution steps
    _show_summary(state, failed_tasks)
    _run_post_implementation_tests(state, backend)

    # REVIEW CHECKPOINT
    # Single review of all changes after all tasks and tests complete,
    # right before commit instructions. Validates complete implementation
    # against the Step 1 spec as a whole.
    if state.enable_phase_review:
        review_outcome, review_feedback = run_phase_review(
            state, log_dir, phase="final", backend=backend
        )
        if review_outcome == ReviewOutcome.STOP:
            print_warning(
                "Workflow stopped after final review. Please address issues before committing."
            )
            return Step3Result(success=False)
        elif review_outcome == ReviewOutcome.REPLAN:
            print_info("Re-planning requested. Restarting execution after plan update.")
            return Step3Result(success=False, needs_replan=True, replan_feedback=review_feedback)
        # CONTINUE falls through

    print_info(f"Task logs saved to: {log_dir}")

    return Step3Result(success=len(failed_tasks) == 0)


def _execute_with_tui(
    state: WorkflowState,
    pending: list[Task],
    plan_path: Path,
    tasklist_path: Path,
    log_dir: Path,
    *,
    backend: AIBackend,
    verbose: bool = False,
    phase: str = "sequential",
) -> list[str]:
    """Execute tasks with TUI display (sequential mode)."""
    # Lazy import to avoid circular dependency
    from ingot.ui.tui import TaskRunnerUI

    failed_tasks: list[str] = []
    user_quit: bool = False

    # Initialize TUI
    tui = TaskRunnerUI(ticket_id=state.ticket.id, verbose_mode=verbose)
    tui.initialize_records([t.name for t in pending])
    tui.set_log_dir(log_dir)

    # Create log buffers for each task
    for i, task in enumerate(pending):
        log_filename = format_log_filename(i, task.name)
        log_path = log_dir / log_filename
        record = tui.get_record(i)
        if record:
            record.log_buffer = TaskLogBuffer(log_path)

    with tui:
        for i, task in enumerate(pending):
            # Check for quit request before starting next task
            if tui.check_quit_requested():
                # Stop TUI temporarily to show prompt
                tui.stop()
                if prompt_confirm("Quit task execution?", default=False):
                    user_quit = True
                    tui.mark_remaining_skipped(i)
                    break
                else:
                    # User changed their mind, continue
                    tui.clear_quit_request()
                    tui.start()

            record = tui.get_record(i)
            if not record:
                continue

            # Emit task started event
            start_event = create_task_started_event(i, task.name)
            tui.handle_event(start_event)

            # Execute task with retry wrapper (sequential mode, not parallel)
            def make_callback(idx: int, name: str) -> Callable[[str], None]:
                def cb(line: str) -> None:
                    tui.handle_event(create_task_output_event(idx, name, line))

                return cb

            success = _execute_task_with_retry(
                state,
                task,
                plan_path,
                backend=backend,
                callback=make_callback(i, task.name),
                is_parallel=False,
            )

            # Check for quit request during task execution
            if tui.check_quit_requested():
                # Task finished naturally, check if user still wants to quit
                tui.stop()
                if prompt_confirm("Task completed. Quit execution?", default=False):
                    user_quit = True
                    # Emit task finished event first
                    duration = record.elapsed_time
                    status: TaskStatus = "success" if success else "failed"
                    finish_event = create_task_finished_event(
                        i,
                        task.name,
                        status,
                        duration,
                        error=None if success else "Task returned failure",
                    )
                    tui.handle_event(finish_event)
                    if success:
                        mark_task_complete(tasklist_path, task.name)
                        state.mark_task_complete(task.name)
                    else:
                        failed_tasks.append(task.name)
                    tui.mark_remaining_skipped(i + 1)
                    break
                else:
                    tui.clear_quit_request()
                    tui.start()

            # Emit task finished event
            duration = record.elapsed_time
            task_status: TaskStatus = "success" if success else "failed"
            finish_event = create_task_finished_event(
                i,
                task.name,
                task_status,
                duration,
                error=None if success else "Task returned failure",
            )
            tui.handle_event(finish_event)

            if success:
                mark_task_complete(tasklist_path, task.name)
                state.mark_task_complete(task.name)
            else:
                failed_tasks.append(task.name)
                if state.fail_fast:
                    tui.mark_remaining_skipped(i + 1)
                    break

    tui.print_summary()
    if user_quit:
        print_info("Execution stopped by user request.")
    return failed_tasks


def _execute_fallback(
    state: WorkflowState,
    pending: list[Task],
    plan_path: Path,
    tasklist_path: Path,
    log_dir: Path,
    *,
    backend: AIBackend,
) -> list[str]:
    """Execute tasks with fallback (non-TUI) display."""
    failed_tasks: list[str] = []

    for i, task in enumerate(pending):
        print_step(f"[{i + 1}/{len(pending)}] {task.name}")

        # Create log buffer for this task
        log_filename = format_log_filename(i, task.name)
        log_path = log_dir / log_filename

        with TaskLogBuffer(log_path) as log_buffer:
            # Callback that writes to log and prints to stdout
            def output_callback(line: str) -> None:
                log_buffer.write(line)
                console.print(line)

            # Execute with retry wrapper (sequential mode, not parallel)
            success = _execute_task_with_retry(
                state,
                task,
                plan_path,
                backend=backend,
                callback=output_callback,
                is_parallel=False,
            )

        if success:
            mark_task_complete(tasklist_path, task.name)
            state.mark_task_complete(task.name)
            print_success(f"Task completed: {task.name}")
        else:
            failed_tasks.append(task.name)
            print_warning(f"Task returned failure: {task.name}")
            if state.fail_fast:
                print_error("Stopping: fail_fast enabled")
                break

    return failed_tasks


def _execute_parallel_fallback(
    state: WorkflowState,
    tasks: list[Task],
    plan_path: Path,
    tasklist_path: Path,
    log_dir: Path,
    *,
    backend: AIBackend,
) -> list[str]:
    """Execute independent tasks in parallel (non-TUI mode) with rate limit handling."""
    from ingot.workflow.parallel_executor import (
        _execute_parallel_fallback as _parallel_fallback_impl,
    )

    return _parallel_fallback_impl(
        state,
        tasks,
        plan_path,
        tasklist_path,
        log_dir,
        backend=backend,
        execute_task_with_retry=_execute_task_with_retry,
    )


def _execute_parallel_with_tui(
    state: WorkflowState,
    tasks: list[Task],
    plan_path: Path,
    tasklist_path: Path,
    log_dir: Path,
    *,
    backend: AIBackend,
    verbose: bool = False,
) -> list[str]:
    """Execute independent tasks in parallel with TUI display and rate limit handling."""
    from ingot.workflow.parallel_executor import (
        _execute_parallel_with_tui as _parallel_tui_impl,
    )

    return _parallel_tui_impl(
        state,
        tasks,
        plan_path,
        tasklist_path,
        log_dir,
        backend=backend,
        verbose=verbose,
        execute_task_with_retry=_execute_task_with_retry,
    )


def _execute_task(
    state: WorkflowState,
    task: Task,
    plan_path: Path,
    backend: AIBackend,
) -> bool:
    """Execute a single task using the ingot-implementer agent.

    Optimistic execution model:
    - Trust AI exit codes
    - No file verification
    - No retry loops
    - Minimal prompt - agent has full instructions
    """
    # Build minimal prompt - pass plan path reference, not full content
    # The agent uses codebase-retrieval to read relevant sections
    prompt = build_task_prompt(
        task,
        plan_path,
        is_parallel=False,
        user_context=state.user_context,
        repo_root=_get_repo_root(os.getcwd()),
    )

    try:
        success, output = backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["implementer"],
            output_callback=lambda _line: None,
            dont_save_session=True,
        )
        if not success and backend.detect_rate_limit(output):
            raise BackendRateLimitError(
                "Rate limit detected", output=output, backend_name=backend.name
            )
        if success:
            print_success(f"Task completed: {task.name}")
        else:
            print_warning(f"Task returned failure: {task.name}")
        return success
    except BackendRateLimitError:
        raise  # Let retry decorator handle
    except Exception as e:
        print_error(f"Task execution crashed: {e}")
        return False


def _execute_task_with_callback(
    state: WorkflowState,
    task: Task,
    plan_path: Path,
    *,
    backend: AIBackend,
    callback: Callable[[str], None],
    is_parallel: bool = False,
) -> bool:
    """Execute a single task with streaming output callback using ingot-implementer agent.

    Uses backend.run_with_callback() for streaming output.
    Each output line is passed to the callback function.

    Raises:
        BackendRateLimitError: If the output indicates a rate limit error.
    """
    # Build minimal prompt - pass plan path reference, not full content
    # The agent uses codebase-retrieval to read relevant sections
    prompt = build_task_prompt(
        task,
        plan_path,
        is_parallel=is_parallel,
        user_context=state.user_context,
        repo_root=_get_repo_root(os.getcwd()),
    )

    try:
        success, output = backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["implementer"],
            output_callback=callback,
            dont_save_session=True,
        )
        if not success and backend.detect_rate_limit(output):
            raise BackendRateLimitError(
                "Rate limit detected", output=output, backend_name=backend.name
            )
        return success
    except BackendRateLimitError:
        raise  # Let retry decorator handle
    except Exception as e:
        callback(f"[ERROR] Task execution crashed: {e}")
        return False


def _run_backend_capturing_output(
    state: WorkflowState,
    prompt: str,
    *,
    backend: AIBackend,
    callback: Callable[[str], None] | None = None,
    error_label: str = "Task execution",
) -> tuple[bool, str]:
    """Run a prompt via the backend and capture its output.

    Shared helper for initial task execution and correction attempts.
    Each invocation uses dont_save_session=True, so the agent starts a
    fresh session — correction attempts rely solely on the prompt text
    for context about previous failures.

    Returns:
        Tuple of (success, output).

    Raises:
        BackendRateLimitError: If the output indicates a rate limit error.
    """
    try:
        success, output = backend.run_with_callback(
            prompt,
            subagent=state.subagent_names["implementer"],
            output_callback=callback or (lambda _line: None),
            dont_save_session=True,
        )
        if not success and backend.detect_rate_limit(output):
            raise BackendRateLimitError(
                "Rate limit detected", output=output, backend_name=backend.name
            )
        return success, output
    except BackendRateLimitError:
        raise
    except Exception as e:
        error_msg = f"[ERROR] {error_label} crashed: {e}"
        if callback:
            callback(error_msg)
        return False, error_msg


def _execute_task_with_self_correction(
    state: WorkflowState,
    task: Task,
    plan_path: Path,
    *,
    backend: AIBackend,
    callback: Callable[[str], None] | None = None,
    is_parallel: bool = False,
) -> SelfCorrectionResult:
    """Execute a task with self-correction loop.

    On failure, feeds the error output back to the agent as a new prompt,
    giving it another chance to fix its mistakes. This is distinct from
    rate-limit retry (which retries the same prompt after a delay).

    Note: Each attempt (initial + corrections) runs in a fresh session
    (dont_save_session=True), so the agent has no conversation memory
    across attempts — only the error output embedded in the prompt.

    BackendRateLimitError propagates through to the outer retry handler.
    """
    max_corrections = state.max_self_corrections

    # If self-correction disabled, delegate directly
    if max_corrections <= 0:
        if callback:
            success = _execute_task_with_callback(
                state,
                task,
                plan_path,
                backend=backend,
                callback=callback,
                is_parallel=is_parallel,
            )
        else:
            success = _execute_task(state, task, plan_path, backend)
        return SelfCorrectionResult(success=success)

    total_attempts = 1 + max_corrections

    def _emit(msg: str, level: str = "info") -> None:
        if callback:
            callback(msg)
        else:
            if level == "info":
                print_info(msg)
            elif level == "success":
                print_success(msg)
            elif level == "warning":
                print_warning(msg)

    # First attempt — capture output for potential correction
    prompt = build_task_prompt(
        task,
        plan_path,
        is_parallel=is_parallel,
        user_context=state.user_context,
        repo_root=_get_repo_root(os.getcwd()),
    )
    success, output = _run_backend_capturing_output(
        state,
        prompt,
        backend=backend,
        callback=callback,
    )

    if success:
        return SelfCorrectionResult(
            success=True,
            final_output=output,
            attempt_count=1,
            total_attempts=total_attempts,
        )

    # Self-correction loop
    for attempt in range(1, max_corrections + 1):
        info_msg = (
            f"[SELF-CORRECTION {attempt}/{max_corrections}] "
            f"Task '{task.name}' failed. Attempting correction..."
        )
        _emit(info_msg, "info")

        correction_prompt = build_self_correction_prompt(
            task,
            plan_path,
            output,
            attempt=attempt,
            max_attempts=max_corrections,
            is_parallel=is_parallel,
            user_context=state.user_context,
            repo_root=_get_repo_root(os.getcwd()),
            ticket_title=state.ticket.title,
            ticket_description=state.ticket.description,
        )

        success, output = _run_backend_capturing_output(
            state,
            correction_prompt,
            backend=backend,
            callback=callback,
            error_label="Correction attempt",
        )

        if success:
            success_msg = (
                f"[SELF-CORRECTION {attempt}/{max_corrections}] "
                f"Task '{task.name}' succeeded after correction."
            )
            _emit(success_msg, "success")
            return SelfCorrectionResult(
                success=True,
                final_output=output,
                attempt_count=1 + attempt,
                total_attempts=total_attempts,
            )

    # All corrections exhausted
    fail_msg = (
        f"[SELF-CORRECTION] Task '{task.name}' failed after "
        f"{max_corrections} correction attempt(s)."
    )
    _emit(fail_msg, "warning")
    return SelfCorrectionResult(
        success=False,
        final_output=output,
        attempt_count=1 + max_corrections,
        total_attempts=total_attempts,
    )


def _execute_task_with_retry(
    state: WorkflowState,
    task: Task,
    plan_path: Path,
    *,
    backend: AIBackend,
    callback: Callable[[str], None] | None = None,
    is_parallel: bool = False,
) -> bool:
    """Execute a task with rate limit retry handling.

    Wraps the core execution with exponential backoff retry logic
    to handle API rate limits during parallel execution.
    """
    config = state.rate_limit_config

    def _emit(msg: str, level: str = "info") -> None:
        if callback:
            callback(msg)
        else:
            if level == "info":
                print_info(msg)
            elif level == "warning":
                print_warning(msg)
            elif level == "error":
                print_error(msg)

    # Skip retry wrapper if retries disabled
    if config.max_retries <= 0:
        try:
            result = _execute_task_with_self_correction(
                state,
                task,
                plan_path,
                backend=backend,
                callback=callback,
                is_parallel=is_parallel,
            )
            return result.success
        except BackendRateLimitError:
            # No retries available — treat as failure
            _emit("[FAILED] Rate limit detected but retries are disabled", "warning")
            return False

    def log_retry(attempt: int, delay: float, error: Exception) -> None:
        """Log retry attempts."""
        _emit(
            f"[RETRY {attempt}/{config.max_retries}] Rate limited. Waiting {delay:.1f}s...",
            "warning",
        )

    @with_rate_limit_retry(config, on_retry=log_retry)
    def execute_with_retry() -> bool:
        result = _execute_task_with_self_correction(
            state,
            task,
            plan_path,
            backend=backend,
            callback=callback,
            is_parallel=is_parallel,
        )
        return result.success

    try:
        return execute_with_retry()
    except RateLimitExceededError as e:
        _emit(f"[FAILED] Task exhausted all retries: {e}", "error")
        return False


def _show_summary(state: WorkflowState, failed_tasks: list[str] | None = None) -> None:
    """Show execution summary."""
    console.print()
    print_header("Execution Summary")

    console.print(f"[bold]Ticket:[/bold] {state.ticket.id}")
    console.print(f"[bold]Branch:[/bold] {state.branch_name or get_current_branch()}")
    console.print(f"[bold]Tasks completed:[/bold] {len(state.completed_tasks)}")
    console.print(f"[bold]Checkpoints:[/bold] {len(state.checkpoint_commits)}")

    if failed_tasks:
        console.print(f"[bold]Tasks with issues:[/bold] {len(failed_tasks)}")

    if state.completed_tasks:
        console.print()
        console.print("[bold]Completed tasks:[/bold]")
        for task in state.completed_tasks:
            console.print(f"  [green]✓[/green] {task}")

    if failed_tasks:
        console.print()
        console.print("[bold]Tasks with issues:[/bold]")
        for task in failed_tasks:
            console.print(f"  [yellow]![/yellow] {task}")

    console.print()

    # Add helpful note about git staging
    console.print(
        "[dim]Note: Generated files may appear as 'Unversioned' (if new) or "
        "'Modified' (if existing).[/dim]"
    )
    console.print(
        "[dim]      You need to manually review and [bold]git add[/bold] them "
        "before committing.[/dim]"
    )
    console.print()


def _run_post_implementation_tests(state: WorkflowState, backend: AIBackend) -> None:
    """Run post-implementation verification tests using AI.

    Finds and runs tests that cover the code changed in this Step 3 run.
    This includes both modified test files AND tests that cover modified source files.
    Does NOT run the full project test suite.

    Uses TaskRunnerUI in single-operation mode to provide a consistent
    collapsible UI with verbose toggle, matching the UX of Steps 1 and 3.
    """
    from ingot.ui.tui import TaskRunnerUI
    from ingot.workflow.events import format_run_directory

    # Prompt user to run tests
    if not prompt_confirm("Run tests for changes made in this run?", default=True):
        print_info("Skipping tests")
        return

    print_step("Running Tests for Changed Code via AI")

    # Create log directory for test execution (use safe_filename_stem for paths)
    log_dir = get_log_base_dir() / state.ticket.safe_filename_stem / LOG_DIR_TEST_EXECUTION
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{format_run_directory()}.log"

    # Create UI with collapsible panel and verbose toggle (single-operation mode)
    ui = TaskRunnerUI(
        status_message="Running tests for changed code...",
        ticket_id=state.ticket.id,  # Keep original ID for display
        single_operation_mode=True,
    )
    ui.set_log_path(log_path)

    try:
        with ui:
            success, _ = backend.run_with_callback(
                POST_IMPLEMENTATION_TEST_PROMPT,
                subagent=state.subagent_names["implementer"],
                output_callback=ui.handle_output_line,
                dont_save_session=True,
            )

            # Check if user requested quit
            if ui.check_quit_requested():
                print_warning("Test execution cancelled by user.")
                return

        ui.print_summary(success)

        if not success:
            print_info("Review test output above to identify issues")
    except Exception as e:
        print_error(f"Failed to run tests: {e}")


__all__ = [
    "SelfCorrectionResult",
    "Step3Result",
    "step_3_execute",
    "LOG_DIR_TEST_EXECUTION",
]
