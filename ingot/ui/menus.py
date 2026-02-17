"""Interactive menus for INGOT.

This module provides menu functions for the main menu, task review,
git dirty state handling, and model selection.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import questionary

from ingot.integrations.backends.base import BackendModel
from ingot.integrations.git import DirtyStateAction
from ingot.ui.prompts import custom_style
from ingot.utils.console import console, print_header, print_info
from ingot.utils.errors import UserCancelledError
from ingot.utils.logging import log_message

if TYPE_CHECKING:
    from ingot.integrations.backends.base import AIBackend

_MANUAL_ENTRY = object()


class MainMenuChoice(Enum):
    """Main menu choices."""

    START_WORKFLOW = "start"
    CONFIGURE = "configure"
    SHOW_CONFIG = "show_config"
    HELP = "help"
    QUIT = "quit"


def show_main_menu() -> MainMenuChoice:
    """Display main menu and get user choice.

    Returns:
        Selected MainMenuChoice

    Raises:
        UserCancelledError: If user cancels
    """
    print_header("Main Menu")

    choices = [
        questionary.Choice("Start AI-Assisted Workflow", value=MainMenuChoice.START_WORKFLOW),
        questionary.Choice("Configure Settings", value=MainMenuChoice.CONFIGURE),
        questionary.Choice("Show Current Configuration", value=MainMenuChoice.SHOW_CONFIG),
        questionary.Choice("Help", value=MainMenuChoice.HELP),
        questionary.Choice("Quit", value=MainMenuChoice.QUIT),
    ]

    try:
        result = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            raise UserCancelledError("User cancelled main menu")

        log_message(f"Main menu selection: {result.value}")
        # Cast to expected type since questionary returns Any
        return MainMenuChoice(result.value)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


class ReviewChoice(Enum):
    """Review menu choices (shared by plan and task review)."""

    APPROVE = "approve"
    REGENERATE = "regenerate"
    EDIT = "edit"
    ABORT = "abort"


# Backwards-compatible aliases
TaskReviewChoice = ReviewChoice
PlanReviewChoice = ReviewChoice


def _show_review_menu(
    *,
    item_label: str,
    approve_text: str,
    regenerate_text: str,
    edit_text: str,
    prompt_text: str,
    cancel_message: str,
) -> ReviewChoice:
    """Shared review menu implementation.

    Args:
        item_label: Label for logging (e.g. "Plan review", "Task review").
        approve_text: Display text for the approve choice.
        regenerate_text: Display text for the regenerate choice.
        edit_text: Display text for the edit choice.
        prompt_text: The question prompt displayed to the user.
        cancel_message: Error message when user cancels.

    Returns:
        Selected ReviewChoice.

    Raises:
        UserCancelledError: If user cancels.
    """
    choices = [
        questionary.Choice(approve_text, value=ReviewChoice.APPROVE),
        questionary.Choice(regenerate_text, value=ReviewChoice.REGENERATE),
        questionary.Choice(edit_text, value=ReviewChoice.EDIT),
        questionary.Choice("Abort workflow", value=ReviewChoice.ABORT),
    ]

    try:
        result = questionary.select(
            prompt_text,
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            raise UserCancelledError(cancel_message)

        log_message(f"{item_label} selection: {result.value}")
        return ReviewChoice(result.value)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


def show_task_review_menu() -> ReviewChoice:
    """Display task review menu.

    Returns:
        Selected ReviewChoice

    Raises:
        UserCancelledError: If user cancels
    """
    return _show_review_menu(
        item_label="Task review",
        approve_text="Approve task list and continue",
        regenerate_text="Regenerate task list",
        edit_text="Edit task list manually",
        prompt_text="Review the task list above. What would you like to do?",
        cancel_message="User cancelled task review",
    )


def show_plan_review_menu() -> ReviewChoice:
    """Display plan review menu.

    Returns:
        Selected ReviewChoice

    Raises:
        UserCancelledError: If user cancels
    """
    return _show_review_menu(
        item_label="Plan review",
        approve_text="Approve plan and continue",
        regenerate_text="Regenerate plan with feedback",
        edit_text="Edit plan manually",
        prompt_text="Review the plan above. What would you like to do?",
        cancel_message="User cancelled plan review",
    )


def show_git_dirty_menu(context: str) -> DirtyStateAction:
    """Display menu for handling uncommitted changes.

    Args:
        context: Description of pending operation

    Returns:
        Selected DirtyStateAction

    Raises:
        UserCancelledError: If user cancels
    """
    print_info(f"You have uncommitted changes before: {context}")
    console.print()

    choices = [
        questionary.Choice("Stash changes (recommended)", value=DirtyStateAction.STASH),
        questionary.Choice("Commit changes", value=DirtyStateAction.COMMIT),
        questionary.Choice("Discard changes (DANGEROUS)", value=DirtyStateAction.DISCARD),
        questionary.Choice("Continue anyway (not recommended)", value=DirtyStateAction.CONTINUE),
        questionary.Choice("Abort", value=DirtyStateAction.ABORT),
    ]

    try:
        result = questionary.select(
            "How would you like to handle uncommitted changes?",
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            raise UserCancelledError("User cancelled dirty state menu")

        log_message(f"Dirty state selection: {result.value}")
        # Cast to expected type since questionary returns Any
        return DirtyStateAction(result.value)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


class CommitFailureChoice(Enum):
    """Commit failure menu choices."""

    RETRY = "retry"
    SKIP = "skip"


def show_commit_failure_menu(error_message: str) -> CommitFailureChoice:
    """Display menu for handling a failed commit.

    Args:
        error_message: The error message from the failed commit.

    Returns:
        Selected CommitFailureChoice.

    Raises:
        UserCancelledError: If user cancels.
    """
    print_info(f"Commit failed: {error_message}")
    console.print()

    choices = [
        questionary.Choice("Retry commit", value=CommitFailureChoice.RETRY),
        questionary.Choice("Skip commit and continue", value=CommitFailureChoice.SKIP),
    ]

    try:
        result = questionary.select(
            "How would you like to proceed?",
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            raise UserCancelledError("User cancelled commit failure menu")

        log_message(f"Commit failure selection: {result.value}")
        return CommitFailureChoice(result.value)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


def show_model_selection(
    current_model: str = "",
    purpose: str = "default",
    backend: AIBackend | None = None,
) -> str | None:
    """Display model selection menu.

    Args:
        current_model: Currently selected model
        purpose: Purpose description (e.g., "planning", "implementation")
        backend: Optional backend instance to fetch models from.
            If provided, uses backend.list_models(). Falls back to
            manual text input when no models are available.

    Returns:
        Selected model ID or None if cancelled

    Raises:
        UserCancelledError: If user cancels
    """
    print_header(f"Select Model for {purpose.title()}")

    models: list[BackendModel] = []
    if backend is not None:
        with console.status("Fetching available models...", spinner="dots"):
            models = backend.list_models()

    if backend is None:
        print_info("No backend configured. Enter model ID manually.")
        from ingot.ui.prompts import prompt_input

        return prompt_input("Enter model ID", default=current_model)

    if not models:
        print_info("Could not retrieve model list. Enter model ID manually.")
        from ingot.ui.prompts import prompt_input

        return prompt_input("Enter model ID", default=current_model)

    choices = []
    for model in models:
        label = f"{model.name} [{model.id}]"
        if model.id == current_model:
            label += " (current)"
        choices.append(questionary.Choice(label, value=model.id))

    choices.append(questionary.Choice("Enter model ID manually...", value=_MANUAL_ENTRY))
    choices.append(questionary.Choice("Keep current / Skip", value=None))

    try:
        result = questionary.select(
            f"Select model for {purpose}:",
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            return current_model or None

        if result is _MANUAL_ENTRY:
            from ingot.ui.prompts import prompt_input

            return prompt_input("Enter model ID", default=current_model)

        log_message(f"Model selection for {purpose}: {result}")
        return str(result)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


def show_task_checkboxes(
    tasks: list[str],
    completed: list[str] | None = None,
) -> list[str]:
    """Display task checkboxes for selection.

    Args:
        tasks: List of task names
        completed: List of already completed tasks

    Returns:
        List of selected task names

    Raises:
        UserCancelledError: If user cancels
    """
    completed = completed or []

    choices = []
    for task in tasks:
        is_done = task in completed
        choices.append(
            questionary.Choice(
                task,
                checked=is_done,
                disabled="(completed)" if is_done else None,
            )
        )

    try:
        result = questionary.checkbox(
            "Select tasks to mark as complete:",
            choices=choices,
            style=custom_style,
        ).ask()

        if result is None:
            raise UserCancelledError("User cancelled task selection")

        log_message(f"Tasks selected: {result}")
        return list(result)

    except KeyboardInterrupt as e:
        raise UserCancelledError("User cancelled with Ctrl+C") from e


__all__ = [
    "CommitFailureChoice",
    "MainMenuChoice",
    "PlanReviewChoice",
    "ReviewChoice",
    "TaskReviewChoice",
    "show_commit_failure_menu",
    "show_main_menu",
    "show_plan_review_menu",
    "show_task_review_menu",
    "show_git_dirty_menu",
    "show_model_selection",
    "show_task_checkboxes",
]
