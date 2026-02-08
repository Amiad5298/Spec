"""Claude Code CLI integration for SPEC.

This module provides the Claude Code CLI wrapper, installation checking,
rate limit detection, and command execution.

Key difference from Auggie: Subagent instructions use --append-system-prompt
instead of being embedded in the user prompt. This is a cleaner separation
native to Claude Code CLI.

Note on ARG_MAX: The --append-system-prompt flag passes content inline on
the command line. Very long subagent prompts could hit OS argument limits.
The Claude CLI does not currently support --append-system-prompt-file, so
there is no file-based alternative. Subagent prompts should be kept concise.
"""

import shutil
import subprocess
from collections.abc import Callable

from spec.utils.logging import log_command, log_message

CLAUDE_CLI_NAME = "claude"


def check_claude_installed() -> tuple[bool, str]:
    """Check if Claude Code CLI is installed and accessible.

    Returns:
        (is_valid, message) tuple where message is the version string
        if installed, or an error message if not.
    """
    if not shutil.which(CLAUDE_CLI_NAME):
        return False, "Claude Code CLI is not installed or not in PATH"

    try:
        result = subprocess.run(
            [CLAUDE_CLI_NAME, "--version"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        log_command(f"{CLAUDE_CLI_NAME} --version", result.returncode)

        version_output = result.stdout.strip() or result.stderr.strip()
        if result.returncode == 0 and version_output:
            return True, version_output

        return False, "Claude Code CLI found but could not determine version"
    except Exception as e:
        log_message(f"Failed to check Claude Code CLI: {e}")
        return False, f"Error checking Claude Code CLI: {e}"


def _looks_like_rate_limit(output: str) -> bool:
    """Heuristic check for rate limit errors in Claude/Anthropic output.

    Detects rate limit errors by checking for common HTTP status codes
    and rate limit keywords in the output.

    Args:
        output: The output string to check

    Returns:
        True if the output looks like a rate limit error
    """
    output_lower = output.lower()
    patterns = [
        "429",
        "rate limit",
        "rate_limit",
        "overloaded",
        "529",
        "too many requests",
        "quota exceeded",
        "throttl",
        "502",
        "503",
        "504",
        "capacity",
    ]
    return any(p in output_lower for p in patterns)


class ClaudeClient:
    """Wrapper for Claude Code CLI commands.

    This is a thin subprocess wrapper. Model resolution and subagent parsing
    are handled by ClaudeBackend (via BaseBackend). The client accepts
    pre-resolved values.

    Attributes:
        model: Default model to use for commands
    """

    def __init__(self, model: str = "") -> None:
        """Initialize the Claude client.

        Args:
            model: Default model to use for commands
        """
        self.model = model

    def build_command(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        print_mode: bool = False,
        dont_save_session: bool = False,
    ) -> list[str]:
        """Build claude command list.

        All parameters are pre-resolved by the caller (typically ClaudeBackend).
        This method just assembles the CLI arguments.

        Args:
            prompt: The prompt to send to Claude
            model: Resolved model name (None = use instance default)
            system_prompt: Resolved subagent prompt body (injected via --append-system-prompt)
            print_mode: Use -p (print) flag
            dont_save_session: Use --no-session-persistence flag

        Returns:
            List of command arguments for subprocess
        """
        cmd = [CLAUDE_CLI_NAME]

        if print_mode:
            cmd.append("-p")

        # Use explicit model or fall back to instance default
        effective_model = model or self.model
        if effective_model:
            cmd.extend(["--model", effective_model])

        if dont_save_session:
            cmd.append("--no-session-persistence")

        # Inject subagent prompt via --append-system-prompt
        if system_prompt:
            cmd.extend(["--append-system-prompt", system_prompt])

        # Prompt as final positional argument
        cmd.append(prompt)
        return cmd

    def run_with_callback(
        self,
        prompt: str,
        *,
        output_callback: Callable[[str], None],
        model: str | None = None,
        system_prompt: str | None = None,
        dont_save_session: bool = False,
    ) -> tuple[bool, str]:
        """Run with streaming output callback.

        Uses subprocess.Popen with line-by-line output processing.
        Each line is passed to output_callback AND collected for return.

        Args:
            prompt: The prompt to send to Claude
            output_callback: Callback function invoked for each output line
            model: Resolved model name
            system_prompt: Resolved subagent prompt body
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Tuple of (success: bool, full_output: str)
        """
        cmd = self.build_command(
            prompt,
            model=model,
            system_prompt=system_prompt,
            print_mode=True,
            dont_save_session=dont_save_session,
        )

        log_message(f"Running {CLAUDE_CLI_NAME} with callback (streaming)")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
        )

        output_lines: list[str] = []
        if process.stdout is not None:
            for line in process.stdout:
                stripped = line.rstrip("\n")
                output_callback(stripped)
                output_lines.append(line)

        process.wait()
        log_command(CLAUDE_CLI_NAME, process.returncode)

        return process.returncode == 0, "".join(output_lines)

    def run_print_with_output(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        dont_save_session: bool = False,
    ) -> tuple[bool, str]:
        """Run with -p flag, return success status and captured output.

        Captures output silently (no stdout printing). The backend layer
        does not own terminal output; SPEC owns the TUI.

        Args:
            prompt: The prompt to send
            model: Resolved model name
            system_prompt: Resolved subagent prompt body
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Tuple of (success: bool, output: str)
        """
        cmd = self.build_command(
            prompt,
            model=model,
            system_prompt=system_prompt,
            print_mode=True,
            dont_save_session=dont_save_session,
        )

        log_message(f"Running {CLAUDE_CLI_NAME} with output capture")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        log_command(CLAUDE_CLI_NAME, result.returncode)

        success = result.returncode == 0
        output = result.stdout or ""

        # Include stderr context when CLI fails with no stdout
        if not success and not output and result.stderr:
            output = result.stderr

        return success, output

    def run_print_quiet(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system_prompt: str | None = None,
        dont_save_session: bool = False,
    ) -> str:
        """Run with -p flag quietly, return output only.

        Args:
            prompt: The prompt to send
            model: Resolved model name
            system_prompt: Resolved subagent prompt body
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Command stdout (or stderr if stdout is empty and command failed)
        """
        cmd = self.build_command(
            prompt,
            model=model,
            system_prompt=system_prompt,
            print_mode=True,
            dont_save_session=dont_save_session,
        )

        log_message(f"Running {CLAUDE_CLI_NAME} quietly")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        log_command(CLAUDE_CLI_NAME, result.returncode)

        output = result.stdout or ""

        # Include stderr context when CLI fails with no stdout
        if not output and result.returncode != 0 and result.stderr:
            output = result.stderr

        return output


__all__ = [
    "CLAUDE_CLI_NAME",
    "ClaudeClient",
    "check_claude_installed",
]
