"""Tests for spec.integrations.claude module - ClaudeClient class."""

from unittest.mock import MagicMock, patch

from spec.integrations.claude import (
    CLAUDE_CLI_NAME,
    ClaudeClient,
    _load_subagent_prompt,
    _looks_like_rate_limit,
    check_claude_installed,
)


class TestClaudeClientBuildCommand:
    """Tests for ClaudeClient._build_command() method."""

    def test_basic_structure(self):
        """Basic command: claude -p <prompt>."""
        client = ClaudeClient()
        cmd = client._build_command("test prompt", print_mode=True)

        assert cmd[0] == CLAUDE_CLI_NAME
        assert "-p" in cmd
        assert cmd[-1] == "test prompt"

    def test_model_flag_when_model_set(self):
        """--model flag included when model is set on client."""
        client = ClaudeClient(model="claude-3-opus")
        cmd = client._build_command("test prompt", print_mode=True)

        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "claude-3-opus"

    def test_model_flag_when_model_passed(self):
        """--model flag uses per-call model override."""
        client = ClaudeClient()
        cmd = client._build_command("test prompt", model="claude-3-sonnet", print_mode=True)

        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "claude-3-sonnet"

    def test_no_session_persistence_flag(self):
        """--no-session-persistence when dont_save_session=True."""
        client = ClaudeClient()
        cmd = client._build_command("test prompt", dont_save_session=True, print_mode=True)

        assert "--no-session-persistence" in cmd

    def test_no_session_persistence_flag_absent(self):
        """No --no-session-persistence when dont_save_session=False."""
        client = ClaudeClient()
        cmd = client._build_command("test prompt", dont_save_session=False, print_mode=True)

        assert "--no-session-persistence" not in cmd

    def test_append_system_prompt_when_subagent_provided(self, tmp_path, monkeypatch):
        """--append-system-prompt when subagent found."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "spec-planner.md"
        agent_file.write_text("You are a planning agent.")

        monkeypatch.chdir(tmp_path)

        client = ClaudeClient()
        cmd = client._build_command("test prompt", subagent="spec-planner", print_mode=True)

        assert "--append-system-prompt" in cmd
        idx = cmd.index("--append-system-prompt")
        assert cmd[idx + 1] == "You are a planning agent."

    def test_subagent_not_found_no_append(self, tmp_path, monkeypatch):
        """No --append-system-prompt when subagent file not found."""
        monkeypatch.chdir(tmp_path)

        client = ClaudeClient()
        cmd = client._build_command("test prompt", subagent="nonexistent", print_mode=True)

        assert "--append-system-prompt" not in cmd

    def test_subagent_strips_frontmatter(self, tmp_path, monkeypatch):
        """Subagent frontmatter is stripped, only body used in --append-system-prompt."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "test-agent.md"
        agent_file.write_text(
            """---
model: claude-3-opus
description: A test agent
---
You are a test agent with instructions."""
        )

        monkeypatch.chdir(tmp_path)

        client = ClaudeClient()
        cmd = client._build_command("test prompt", subagent="test-agent", print_mode=True)

        assert "--append-system-prompt" in cmd
        idx = cmd.index("--append-system-prompt")
        assert cmd[idx + 1] == "You are a test agent with instructions."
        assert "---" not in cmd[idx + 1]

    def test_subagent_frontmatter_model_used(self, tmp_path, monkeypatch):
        """Model from subagent frontmatter used when no explicit model."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "test-agent.md"
        agent_file.write_text(
            """---
model: frontmatter-model
---
Agent body."""
        )

        monkeypatch.chdir(tmp_path)

        client = ClaudeClient()
        cmd = client._build_command("test prompt", subagent="test-agent", print_mode=True)

        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "frontmatter-model"

    def test_all_flags_combined(self, tmp_path, monkeypatch):
        """All flags work together correctly."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "spec-planner.md"
        agent_file.write_text("You are a planner.")

        monkeypatch.chdir(tmp_path)

        client = ClaudeClient()
        cmd = client._build_command(
            "do the work",
            subagent="spec-planner",
            model="claude-3-opus",
            print_mode=True,
            dont_save_session=True,
        )

        assert cmd[0] == CLAUDE_CLI_NAME
        assert "-p" in cmd
        assert "--model" in cmd
        assert "--no-session-persistence" in cmd
        assert "--append-system-prompt" in cmd
        assert cmd[-1] == "do the work"

    def test_no_print_mode(self):
        """Command without -p flag when print_mode=False."""
        client = ClaudeClient()
        cmd = client._build_command("test prompt", print_mode=False)

        assert "-p" not in cmd
        assert cmd[-1] == "test prompt"

    def test_prompt_is_last_argument(self):
        """Prompt is always the last positional argument."""
        client = ClaudeClient(model="claude-3-opus")
        cmd = client._build_command(
            "my prompt here",
            print_mode=True,
            dont_save_session=True,
        )

        assert cmd[-1] == "my prompt here"


class TestClaudeClientSubagentLoading:
    """Tests for _load_subagent_prompt() function."""

    def test_with_yaml_frontmatter(self, tmp_path, monkeypatch):
        """Strips YAML frontmatter, returns body only."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "test-agent.md"
        agent_file.write_text(
            """---
model: claude-3-opus
description: Testing
---
You are a test agent.
Follow these rules."""
        )

        monkeypatch.chdir(tmp_path)

        result = _load_subagent_prompt("test-agent")

        assert result == "You are a test agent.\nFollow these rules."
        assert "---" not in result
        assert "model:" not in result

    def test_without_frontmatter(self, tmp_path, monkeypatch):
        """Returns full content when no frontmatter."""
        agents_dir = tmp_path / ".augment" / "agents"
        agents_dir.mkdir(parents=True)
        agent_file = agents_dir / "simple-agent.md"
        agent_file.write_text("You are a simple agent with no frontmatter.")

        monkeypatch.chdir(tmp_path)

        result = _load_subagent_prompt("simple-agent")

        assert result == "You are a simple agent with no frontmatter."

    def test_file_not_found(self, tmp_path, monkeypatch):
        """Returns None when agent file doesn't exist."""
        monkeypatch.chdir(tmp_path)

        result = _load_subagent_prompt("nonexistent-agent")

        assert result is None


class TestClaudeClientExecution:
    """Tests for ClaudeClient execution methods with mocked subprocess."""

    def test_run_with_callback_streams_output(self):
        """run_with_callback streams output via Popen."""
        client = ClaudeClient()
        mock_callback = MagicMock()

        mock_process = MagicMock()
        mock_process.stdout = iter(["line 1\n", "line 2\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("spec.integrations.claude.subprocess.Popen", return_value=mock_process):
            success, output = client.run_with_callback(
                "test prompt",
                output_callback=mock_callback,
            )

        assert success is True
        assert "line 1" in output
        assert "line 2" in output
        assert mock_callback.call_count == 2
        mock_callback.assert_any_call("line 1")
        mock_callback.assert_any_call("line 2")

    def test_run_with_callback_failure(self):
        """run_with_callback returns False on non-zero exit code."""
        client = ClaudeClient()
        mock_callback = MagicMock()

        mock_process = MagicMock()
        mock_process.stdout = iter(["error output\n"])
        mock_process.returncode = 1
        mock_process.wait.return_value = None

        with patch("spec.integrations.claude.subprocess.Popen", return_value=mock_process):
            success, output = client.run_with_callback(
                "test prompt",
                output_callback=mock_callback,
            )

        assert success is False
        assert "error output" in output

    def test_run_print_with_output_returns_tuple(self):
        """run_print_with_output returns (success, output) tuple."""
        client = ClaudeClient()

        mock_process = MagicMock()
        mock_process.stdout = iter(["response line\n"])
        mock_process.returncode = 0
        mock_process.wait.return_value = None

        with patch("spec.integrations.claude.subprocess.Popen", return_value=mock_process):
            success, output = client.run_print_with_output("test prompt")

        assert success is True
        assert "response line" in output

    def test_run_print_quiet_returns_output_string(self):
        """run_print_quiet returns output string only."""
        client = ClaudeClient()

        mock_result = MagicMock()
        mock_result.stdout = "quiet output content"
        mock_result.returncode = 0

        with patch("spec.integrations.claude.subprocess.run", return_value=mock_result):
            output = client.run_print_quiet("test prompt")

        assert output == "quiet output content"

    def test_run_print_quiet_empty_output(self):
        """run_print_quiet returns empty string on None stdout."""
        client = ClaudeClient()

        mock_result = MagicMock()
        mock_result.stdout = None
        mock_result.returncode = 0

        with patch("spec.integrations.claude.subprocess.run", return_value=mock_result):
            output = client.run_print_quiet("test prompt")

        assert output == ""


class TestCheckClaudeInstalled:
    """Tests for check_claude_installed() function."""

    def test_installed_returns_true_and_version(self):
        """Returns (True, version) when CLI is installed."""
        with (
            patch("spec.integrations.claude.shutil.which", return_value="/usr/local/bin/claude"),
            patch(
                "spec.integrations.claude.subprocess.run",
                return_value=MagicMock(
                    returncode=0,
                    stdout="claude 1.0.0",
                    stderr="",
                ),
            ),
        ):
            is_installed, message = check_claude_installed()

        assert is_installed is True
        assert "1.0.0" in message

    def test_not_installed_returns_false(self):
        """Returns (False, message) when CLI is not in PATH."""
        with patch("spec.integrations.claude.shutil.which", return_value=None):
            is_installed, message = check_claude_installed()

        assert is_installed is False
        assert "not installed" in message.lower() or "not in PATH" in message


class TestLooksLikeRateLimit:
    """Tests for _looks_like_rate_limit() function."""

    def test_detects_429(self):
        """Detects HTTP 429 status code."""
        assert _looks_like_rate_limit("Error 429: Too Many Requests") is True

    def test_detects_rate_limit(self):
        """Detects 'rate limit' text."""
        assert _looks_like_rate_limit("rate limit exceeded") is True

    def test_detects_overloaded(self):
        """Detects 'overloaded' (Anthropic-specific)."""
        assert _looks_like_rate_limit("API is overloaded") is True

    def test_detects_529(self):
        """Detects HTTP 529 status code (Anthropic-specific)."""
        assert _looks_like_rate_limit("Error 529") is True

    def test_detects_quota_exceeded(self):
        """Detects 'quota exceeded'."""
        assert _looks_like_rate_limit("quota exceeded for this account") is True

    def test_detects_throttling(self):
        """Detects 'throttl' prefix (throttle, throttling, throttled)."""
        assert _looks_like_rate_limit("request throttled") is True

    def test_detects_capacity(self):
        """Detects 'capacity' keyword."""
        assert _looks_like_rate_limit("insufficient capacity") is True

    def test_detects_502(self):
        """Detects HTTP 502."""
        assert _looks_like_rate_limit("502 Bad Gateway") is True

    def test_detects_503(self):
        """Detects HTTP 503."""
        assert _looks_like_rate_limit("503 Service Unavailable") is True

    def test_detects_504(self):
        """Detects HTTP 504."""
        assert _looks_like_rate_limit("504 Gateway Timeout") is True

    def test_normal_output_returns_false(self):
        """Normal output returns False."""
        assert _looks_like_rate_limit("Successfully generated code") is False

    def test_empty_string_returns_false(self):
        """Empty string returns False."""
        assert _looks_like_rate_limit("") is False
