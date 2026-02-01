"""AI Backend protocol and base types.

This module defines the contract for AI backend integrations:
- AIBackend: Protocol for all backend implementations
- BaseBackend: Abstract base class with shared logic (Phase 1.3)

All backends execute in non-interactive mode for deterministic behavior.
User input is collected via the TUI, then included in prompts.
"""

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from spec.config.fetch_config import AgentPlatform


@runtime_checkable
class AIBackend(Protocol):
    """Protocol for AI backend integrations.

    This defines the contract for AI providers (Auggie, Claude Code, Cursor).
    Each backend wraps its respective CLI tool.

    All methods execute in non-interactive mode for deterministic behavior.
    User input is collected via the TUI, then included in prompts.

    Note: This protocol does NOT include run_print() (interactive mode).
    SPEC owns interactive UX; backends operate in streaming/print mode only.

    Example:
        >>> def run_workflow(backend: AIBackend) -> None:
        ...     success, output = backend.run_with_callback(
        ...         "Generate a plan",
        ...         output_callback=print,
        ...         subagent="spec-planner",
        ...     )
        ...     if not success:
        ...         if backend.detect_rate_limit(output):
        ...             raise BackendRateLimitError(...)
    """

    @property
    def name(self) -> str:
        """Human-readable backend name.

        Examples: 'Auggie', 'Claude Code', 'Cursor'
        """
        ...

    @property
    def platform(self) -> AgentPlatform:
        """The agent platform enum value.

        Returns the AgentPlatform enum member for this backend.
        Used for configuration and logging.
        """
        ...

    @property
    def supports_parallel(self) -> bool:
        """Whether this backend supports parallel execution.

        If False, Step 3 falls back to sequential task execution.
        If True, Step 3 can spawn concurrent backend invocations.

        Note: This property indicates capability, not a setting.
        Use --no-parallel CLI flag to disable parallel execution
        even for backends that support it.
        """
        ...

    def run_with_callback(
        self,
        prompt: str,
        *,
        output_callback: Callable[[str], None],
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Execute prompt with streaming output (non-interactive).

        This is the primary execution method. Output is streamed line-by-line
        to the callback while also being accumulated for the return value.

        Args:
            prompt: The prompt to send to the AI
            output_callback: Called for each line of output (stripped of newline)
            subagent: Subagent name (loads prompt from .augment/agents/{name}.md)
            model: Model override (best-effort, safely ignored if unsupported)
            dont_save_session: If True, isolate this execution (no session persistence)
            timeout_seconds: Maximum execution time (None = no timeout)

        Returns:
            Tuple of (success, full_output) where:
            - success: True if command returned exit code 0
            - full_output: All output lines joined (preserves newlines)

        Raises:
            BackendTimeoutError: If timeout_seconds is exceeded
            BackendNotInstalledError: If CLI is not installed
        """
        ...

    def run_print_with_output(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Execute prompt (non-interactive) and return output.

        Convenience method that wraps run_with_callback with a default
        print callback. Output is printed to stdout as it streams.

        Args:
            prompt: The prompt to send to the AI
            subagent: Subagent name (loads prompt from .augment/agents/{name}.md)
            model: Model override (best-effort, safely ignored if unsupported)
            dont_save_session: If True, isolate this execution
            timeout_seconds: Maximum execution time (None = no timeout)

        Returns:
            Tuple of (success, full_output)
        """
        ...

    def run_print_quiet(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> str:
        """Execute prompt quietly (non-interactive) and return output only.

        No output is printed during execution. This is used for background
        operations where only the final result matters.

        Args:
            prompt: The prompt to send to the AI
            subagent: Subagent name (loads prompt from .augment/agents/{name}.md)
            model: Model override (best-effort, safely ignored if unsupported)
            dont_save_session: If True, isolate this execution
            timeout_seconds: Maximum execution time (None = no timeout)

        Returns:
            The full output as a string (success is not indicated)

        Note:
            Callers must check the content to determine success/failure.
            This matches the existing AuggieClient.run_print_quiet() behavior.
        """
        ...

    def run_streaming(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Execute prompt in streaming/print mode (non-interactive).

        This replaces interactive run_print() usage. User input should be
        collected via TUI first, then included in the prompt.

        Args:
            prompt: The prompt to send (with any user input already included)
            subagent: Subagent name (loads prompt from .augment/agents/{name}.md)
            model: Model override (best-effort, safely ignored if unsupported)
            timeout_seconds: Maximum execution time (None = no timeout)

        Returns:
            Tuple of (success, full_output)
        """
        ...

    def check_installed(self) -> tuple[bool, str]:
        """Check if the backend CLI is installed and functional.

        Verifies that the CLI executable is available in PATH and can
        execute a basic command (typically --version).

        Returns:
            Tuple of (is_installed, message) where:
            - is_installed: True if CLI is available and functional
            - message: Version string if installed, error message if not

        Example:
            >>> installed, msg = backend.check_installed()
            >>> if not installed:
            ...     raise BackendNotInstalledError(msg)
        """
        ...

    def detect_rate_limit(self, output: str) -> bool:
        """Check if output indicates a rate limit error.

        Backend-specific pattern matching for rate limit detection.
        Each backend implements patterns appropriate for its provider.

        Args:
            output: The output text to check

        Returns:
            True if output contains rate limit indicators

        Example patterns:
            - HTTP 429 status codes
            - "rate limit", "rate_limit"
            - "quota exceeded"
            - "too many requests"
            - "throttle", "throttling"
        """
        ...

    def supports_parallel_execution(self) -> bool:
        """Whether this backend can handle concurrent invocations.

        Returns the value of the `supports_parallel` property.
        This method exists for explicit API clarity in workflow code.

        Returns:
            True if multiple CLI invocations can run concurrently
        """
        ...

    def close(self) -> None:
        """Release any resources held by the backend.

        Called when workflow completes or on cleanup.
        Default implementation is no-op for stateless backends.

        Implementations may:
        - Terminate subprocess connections
        - Close file handles
        - Clean up temporary files
        """
        ...
