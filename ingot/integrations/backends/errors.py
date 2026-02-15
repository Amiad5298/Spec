"""Backend-related errors.

Generic error types that apply to all AI backends. These errors provide
a unified error handling interface across Auggie, Claude, Cursor, and
other backends.

All errors inherit from IngotError to leverage exit code semantics and
the existing exception hierarchy.

Note: BackendRateLimitError is defined in ingot.utils.errors to break
circular imports. It is re-exported here as backends/errors is the
natural import location for backend error types.
"""

from ingot.utils.errors import (
    BackendRateLimitError as BackendRateLimitError,
)
from ingot.utils.errors import (
    IngotError,
)


class BackendNotInstalledError(IngotError):
    """Raised when backend CLI is not installed.

    This error is raised when attempting to use a backend whose CLI
    tool is not found in the system PATH.

    Example:
        >>> raise BackendNotInstalledError(
        ...     "Claude CLI is not installed. Install with: npm install -g @anthropic/claude-code"
        ... )
    """

    pass


class BackendNotConfiguredError(IngotError):
    """Raised when no AI backend is configured.

    This error is raised when neither CLI --backend flag nor persisted
    AI_BACKEND config is set. Users should run 'ingot init' to configure
    a backend or use --backend flag.

    Example:
        >>> raise BackendNotConfiguredError(
        ...     "No AI backend configured. Run 'ingot init' or use --backend flag."
        ... )
    """

    pass


class BackendTimeoutError(IngotError):
    """Raised when backend execution times out.

    This error is raised when a backend operation exceeds the configured
    timeout duration. Carries the timeout value for user feedback.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded (if known)

    Example:
        >>> raise BackendTimeoutError(
        ...     "Backend execution timed out after 120 seconds",
        ...     timeout_seconds=120.0,
        ... )
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize the timeout error.

        Args:
            message: Error message describing the timeout
            timeout_seconds: The timeout duration that was exceeded
        """
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


__all__ = [
    "BackendRateLimitError",
    "BackendNotInstalledError",
    "BackendNotConfiguredError",
    "BackendTimeoutError",
]
