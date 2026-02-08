"""Claude Code CLI integration for SPEC.

This module provides the Claude Code CLI wrapper, installation checking,
rate limit detection, and command execution.

Key difference from Auggie: Subagent instructions use --append-system-prompt
instead of being embedded in the user prompt. This is a cleaner separation
native to Claude Code CLI.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

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
        )
        log_command("claude --version", result.returncode)

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


def _load_subagent_prompt(subagent: str) -> str | None:
    """Load subagent prompt from agent definition file.

    Reads the markdown file from .augment/agents/{subagent}.md,
    strips any YAML frontmatter, and returns the body only.

    Args:
        subagent: Name of the subagent

    Returns:
        The prompt body (without frontmatter) if found, None otherwise
    """
    agent_path = Path(".augment/agents") / f"{subagent}.md"
    if not agent_path.exists():
        return None

    try:
        content = agent_path.read_text()

        # Strip YAML frontmatter if present
        if content.startswith("---"):
            # Find the closing --- marker
            end_marker = content.find("---", 3)
            if end_marker != -1:
                body = content[end_marker + 3 :].strip()
                return body if body else None

        return content.strip() if content.strip() else None
    except OSError:
        return None


def _parse_frontmatter_model(subagent: str) -> str | None:
    """Extract model from subagent YAML frontmatter.

    Args:
        subagent: Name of the subagent

    Returns:
        Model string from frontmatter, or None if not found
    """
    agent_path = Path(".augment/agents") / f"{subagent}.md"
    if not agent_path.exists():
        return None

    try:
        content = agent_path.read_text()
        if not content.startswith("---"):
            return None

        end_marker = content.find("---", 3)
        if end_marker == -1:
            return None

        frontmatter_str = content[3:end_marker].strip()
        # Simple key: value parsing (same as auggie.py pattern)
        for line in frontmatter_str.split("\n"):
            line = line.strip()
            if line.startswith("model:"):
                _, _, value = line.partition(":")
                model = value.strip()
                return model if model else None
        return None
    except OSError:
        return None


class ClaudeClient:
    """Wrapper for Claude Code CLI commands.

    Attributes:
        model: Default model to use for commands
    """

    def __init__(self, model: str = "") -> None:
        """Initialize the Claude client.

        Args:
            model: Default model to use for commands
        """
        self.model = model

    def _build_command(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        print_mode: bool = False,
        dont_save_session: bool = False,
    ) -> list[str]:
        """Build claude command list.

        When a subagent is specified, the subagent prompt is injected via
        --append-system-prompt (keeping the user prompt clean). The model
        from the subagent frontmatter is used if no explicit model is given.

        Args:
            prompt: The prompt to send to Claude
            subagent: Subagent name (loads prompt from .augment/agents/{name}.md)
            model: Override model for this command
            print_mode: Use -p (print) flag
            dont_save_session: Use --no-session-persistence flag

        Returns:
            List of command arguments for subprocess
        """
        cmd = [CLAUDE_CLI_NAME]

        if print_mode:
            cmd.append("-p")

        # Determine model: explicit > subagent frontmatter > instance default
        effective_model = model or self.model
        if not effective_model and subagent:
            frontmatter_model = _parse_frontmatter_model(subagent)
            if frontmatter_model:
                effective_model = frontmatter_model

        if effective_model:
            cmd.extend(["--model", effective_model])

        if dont_save_session:
            cmd.append("--no-session-persistence")

        # Inject subagent prompt via --append-system-prompt
        if subagent:
            subagent_prompt = _load_subagent_prompt(subagent)
            if subagent_prompt:
                cmd.extend(["--append-system-prompt", subagent_prompt])

        # Prompt as final positional argument
        cmd.append(prompt)
        return cmd

    def run_with_callback(
        self,
        prompt: str,
        *,
        output_callback: Callable[[str], None],
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
    ) -> tuple[bool, str]:
        """Run with streaming output callback.

        Uses subprocess.Popen with line-by-line output processing.
        Each line is passed to output_callback AND collected for return.

        Args:
            prompt: The prompt to send to Claude
            output_callback: Callback function invoked for each output line
            subagent: Subagent name
            model: Override model for this command
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Tuple of (success: bool, full_output: str)
        """
        cmd = self._build_command(
            prompt,
            subagent=subagent,
            model=model,
            print_mode=True,
            dont_save_session=dont_save_session,
        )

        log_message(f"Running claude command with callback: {' '.join(cmd[:3])}...")

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
        log_command(" ".join(cmd), process.returncode)

        return process.returncode == 0, "".join(output_lines)

    def run_print_with_output(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
    ) -> tuple[bool, str]:
        """Run with -p flag, return success status and captured output.

        Uses run_with_callback internally to both display and capture output.

        Args:
            prompt: The prompt to send
            subagent: Subagent name
            model: Override model for this command
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Tuple of (success: bool, output: str)
        """
        return self.run_with_callback(
            prompt,
            output_callback=lambda line: print(line),
            subagent=subagent,
            model=model,
            dont_save_session=dont_save_session,
        )

    def run_print_quiet(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
    ) -> str:
        """Run with -p flag quietly, return output only.

        Args:
            prompt: The prompt to send
            subagent: Subagent name
            model: Override model for this command
            dont_save_session: If True, use --no-session-persistence

        Returns:
            Command stdout
        """
        cmd = self._build_command(
            prompt,
            subagent=subagent,
            model=model,
            print_mode=True,
            dont_save_session=dont_save_session,
        )

        log_message(f"Running claude command quietly: {' '.join(cmd[:3])}...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        log_command(" ".join(cmd), result.returncode)

        return str(result.stdout) if result.stdout else ""


__all__ = [
    "CLAUDE_CLI_NAME",
    "ClaudeClient",
    "check_claude_installed",
    "_looks_like_rate_limit",
    "_load_subagent_prompt",
    "_parse_frontmatter_model",
]
