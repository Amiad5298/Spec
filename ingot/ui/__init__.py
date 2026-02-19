"""UI components for INGOT.

This package contains:
- prompts: Questionary-based user input prompts
- menus: Interactive menu functions
- log_buffer: Memory-efficient log buffer with file backing
"""

from ingot.ui.inline_runner import InlineRunner
from ingot.ui.log_buffer import TaskLogBuffer
from ingot.ui.menus import (
    MainMenuChoice,
    ReviewChoice,
    show_git_dirty_menu,
    show_main_menu,
    show_model_selection,
    show_plan_review_menu,
    show_task_checkboxes,
    show_task_review_menu,
)
from ingot.ui.prompts import (
    custom_style,
    prompt_checkbox,
    prompt_confirm,
    prompt_enter,
    prompt_input,
    prompt_select,
)

__all__ = [
    # Inline Runner
    "InlineRunner",
    # Log Buffer
    "TaskLogBuffer",
    # Prompts
    "custom_style",
    "prompt_checkbox",
    "prompt_confirm",
    "prompt_enter",
    "prompt_input",
    "prompt_select",
    # Menus
    "MainMenuChoice",
    "ReviewChoice",
    "show_main_menu",
    "show_plan_review_menu",
    "show_task_review_menu",
    "show_git_dirty_menu",
    "show_model_selection",
    "show_task_checkboxes",
]
