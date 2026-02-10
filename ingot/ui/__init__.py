"""UI components for INGOT.

This package contains:
- prompts: Questionary-based user input prompts
- menus: Interactive menu functions
- log_buffer: Memory-efficient log buffer with file backing
- plan_tui: StreamingOperationUI for single long-running operations
"""

from ingot.ui.log_buffer import TaskLogBuffer
from ingot.ui.menus import (
    MainMenuChoice,
    TaskReviewChoice,
    show_git_dirty_menu,
    show_main_menu,
    show_model_selection,
    show_task_checkboxes,
    show_task_review_menu,
)
from ingot.ui.plan_tui import StreamingOperationUI
from ingot.ui.prompts import (
    custom_style,
    prompt_checkbox,
    prompt_confirm,
    prompt_enter,
    prompt_input,
    prompt_select,
)

__all__ = [
    # Log Buffer
    "TaskLogBuffer",
    # Streaming Operation TUI
    "StreamingOperationUI",
    # Prompts
    "custom_style",
    "prompt_checkbox",
    "prompt_confirm",
    "prompt_enter",
    "prompt_input",
    "prompt_select",
    # Menus
    "MainMenuChoice",
    "TaskReviewChoice",
    "show_main_menu",
    "show_task_review_menu",
    "show_git_dirty_menu",
    "show_model_selection",
    "show_task_checkboxes",
]
