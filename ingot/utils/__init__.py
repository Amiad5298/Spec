"""Utility modules for INGOT.

This package contains:
- console: Rich-based terminal output utilities
- env_utils: Environment variable expansion utilities
- errors: Custom exceptions and exit codes
- error_analysis: Structured error parsing for better retry prompts
- logging: Logging configuration
- retry: Rate limit handling with exponential backoff
"""

from ingot.utils.console import (
    console,
    print_error,
    print_header,
    print_info,
    print_step,
    print_success,
    print_warning,
    show_banner,
)
from ingot.utils.env_utils import (
    SENSITIVE_KEY_PATTERNS,
    EnvVarExpansionError,
    expand_env_vars,
    expand_env_vars_strict,
    is_sensitive_key,
)
from ingot.utils.error_analysis import ErrorAnalysis, analyze_error_output
from ingot.utils.errors import (
    AuggieNotInstalledError,
    ExitCode,
    GitOperationError,
    IngotError,
    PlatformNotConfiguredError,
    UserCancelledError,
)
from ingot.utils.logging import log_command, log_message, setup_logging
from ingot.utils.retry import (
    RateLimitExceededError,
    calculate_backoff_delay,
    with_rate_limit_retry,
)

__all__ = [
    # Console
    "console",
    "print_error",
    "print_success",
    "print_warning",
    "print_info",
    "print_header",
    "print_step",
    "show_banner",
    # Env Utils
    "EnvVarExpansionError",
    "SENSITIVE_KEY_PATTERNS",
    "expand_env_vars",
    "expand_env_vars_strict",
    "is_sensitive_key",
    # Errors
    "ExitCode",
    "IngotError",
    "AuggieNotInstalledError",
    "PlatformNotConfiguredError",
    "UserCancelledError",
    "GitOperationError",
    # Error Analysis
    "ErrorAnalysis",
    "analyze_error_output",
    # Logging
    "setup_logging",
    "log_message",
    "log_command",
    # Retry
    "RateLimitExceededError",
    "calculate_backoff_delay",
    "with_rate_limit_retry",
]
