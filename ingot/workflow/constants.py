"""Workflow constants.

This module contains constants used across the workflow that are
not specific to any particular AI backend.

These constants define the canonical names for INGOT subagents
used across all workflow steps, plus default timeout values.
"""

# Subagent names for INGOT workflow
# These are the canonical identifiers used by workflow steps
INGOT_AGENT_PLANNER = "ingot-planner"
INGOT_AGENT_TASKLIST = "ingot-tasklist"
INGOT_AGENT_TASKLIST_REFINER = "ingot-tasklist-refiner"
INGOT_AGENT_IMPLEMENTER = "ingot-implementer"
INGOT_AGENT_REVIEWER = "ingot-reviewer"
INGOT_AGENT_FIXER = "ingot-implementer"  # Autofix reuses the implementer agent
INGOT_AGENT_DOC_UPDATER = "ingot-doc-updater"

# Default timeout values (seconds)
DEFAULT_EXECUTION_TIMEOUT = 60
FIRST_RUN_TIMEOUT = 120
ONBOARDING_SMOKE_TEST_TIMEOUT = 60

# Safety cap on plan/tasklist review iterations to prevent runaway loops.
MAX_REVIEW_ITERATIONS = 10


def noop_output_callback(_line: str) -> None:
    """No-op output callback for silent backend calls."""


__all__ = [
    # Subagent constants
    "INGOT_AGENT_PLANNER",
    "INGOT_AGENT_TASKLIST",
    "INGOT_AGENT_TASKLIST_REFINER",
    "INGOT_AGENT_IMPLEMENTER",
    "INGOT_AGENT_REVIEWER",
    "INGOT_AGENT_FIXER",
    "INGOT_AGENT_DOC_UPDATER",
    # Timeout constants
    "DEFAULT_EXECUTION_TIMEOUT",
    "FIRST_RUN_TIMEOUT",
    "ONBOARDING_SMOKE_TEST_TIMEOUT",
    # Review iteration limit
    "MAX_REVIEW_ITERATIONS",
    # Shared callbacks
    "noop_output_callback",
]
