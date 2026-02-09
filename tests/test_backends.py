"""Backend unit tests: factory, rate-limit detection, and compatibility matrix.

Tests:
- BackendFactory.create() for all platforms
- Per-backend rate limit detection (Auggie, Claude, Cursor)
- Compatibility matrix: get_platform_support()
"""

from __future__ import annotations

import pytest

from spec.config.compatibility import get_platform_support
from spec.config.fetch_config import AgentPlatform
from spec.integrations.backends.base import AIBackend
from spec.integrations.backends.factory import BackendFactory
from spec.integrations.providers.base import Platform


class TestBackendFactory:
    """Tests for BackendFactory.create()."""

    def test_create_auggie_backend(self):
        """Factory creates AuggieBackend for AUGGIE platform."""
        backend = BackendFactory.create(AgentPlatform.AUGGIE)
        assert backend.platform == AgentPlatform.AUGGIE
        assert backend.name == "Auggie"
        assert isinstance(backend, AIBackend)

    def test_create_claude_backend(self):
        """Factory creates ClaudeBackend for CLAUDE platform."""
        backend = BackendFactory.create(AgentPlatform.CLAUDE)
        assert backend.platform == AgentPlatform.CLAUDE
        assert backend.name == "Claude Code"
        assert isinstance(backend, AIBackend)

    def test_create_cursor_backend(self):
        """Factory creates CursorBackend for CURSOR platform."""
        backend = BackendFactory.create(AgentPlatform.CURSOR)
        assert backend.platform == AgentPlatform.CURSOR
        assert backend.name == "Cursor"
        assert isinstance(backend, AIBackend)

    def test_create_from_string(self):
        """Factory accepts string platform names."""
        backend = BackendFactory.create("auggie")
        assert backend.platform == AgentPlatform.AUGGIE

    def test_create_from_string_claude(self):
        """Factory accepts 'claude' string."""
        backend = BackendFactory.create("claude")
        assert backend.platform == AgentPlatform.CLAUDE

    def test_create_from_string_cursor(self):
        """Factory accepts 'cursor' string."""
        backend = BackendFactory.create("cursor")
        assert backend.platform == AgentPlatform.CURSOR

    def test_create_unknown_backend_raises(self):
        """Factory raises for unknown string platforms."""
        with pytest.raises((ValueError, Exception)):
            BackendFactory.create("unknown")

    def test_manual_backend_raises(self):
        """Factory raises ValueError for MANUAL platform."""
        with pytest.raises(ValueError, match="Manual mode"):
            BackendFactory.create(AgentPlatform.MANUAL)

    def test_aider_backend_raises(self):
        """Factory raises ValueError for AIDER platform (not yet implemented)."""
        with pytest.raises(ValueError, match="[Aa]ider"):
            BackendFactory.create(AgentPlatform.AIDER)

    def test_create_with_model(self):
        """Factory passes model parameter to backend."""
        backend = BackendFactory.create(AgentPlatform.AUGGIE, model="gpt-4")
        assert isinstance(backend, AIBackend)

    def test_create_returns_independent_instances(self):
        """Each create() call returns a new independent instance."""
        b1 = BackendFactory.create(AgentPlatform.AUGGIE)
        b2 = BackendFactory.create(AgentPlatform.AUGGIE)
        assert b1 is not b2


class TestRateLimitDetection:
    """Tests for per-backend rate limit detection."""

    def test_auggie_detects_429(self):
        """AuggieBackend detects HTTP 429."""
        from spec.integrations.backends.auggie import AuggieBackend

        backend = AuggieBackend()
        assert backend.detect_rate_limit("Error 429: Too many requests") is True

    def test_auggie_detects_rate_limit_keyword(self):
        """AuggieBackend detects 'rate limit' text."""
        from spec.integrations.backends.auggie import AuggieBackend

        backend = AuggieBackend()
        assert backend.detect_rate_limit("rate limit exceeded") is True

    def test_auggie_normal_output_not_rate_limited(self):
        """AuggieBackend returns False for normal output."""
        from spec.integrations.backends.auggie import AuggieBackend

        backend = AuggieBackend()
        assert backend.detect_rate_limit("Task completed successfully") is False

    def test_claude_detects_429(self):
        """ClaudeBackend detects HTTP 429."""
        from spec.integrations.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        assert backend.detect_rate_limit("Error 429: Too many requests") is True

    def test_claude_detects_rate_limit_keyword(self):
        """ClaudeBackend detects 'rate limit' text."""
        from spec.integrations.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        assert backend.detect_rate_limit("rate limit exceeded") is True

    def test_claude_normal_output_not_rate_limited(self):
        """ClaudeBackend returns False for normal output."""
        from spec.integrations.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        assert backend.detect_rate_limit("Task completed successfully") is False

    def test_cursor_detects_429(self):
        """CursorBackend detects HTTP 429."""
        from spec.integrations.backends.cursor import CursorBackend

        backend = CursorBackend()
        assert backend.detect_rate_limit("Error 429: Too many requests") is True

    def test_cursor_detects_quota_exceeded(self):
        """CursorBackend detects 'quota exceeded' text."""
        from spec.integrations.backends.cursor import CursorBackend

        backend = CursorBackend()
        assert backend.detect_rate_limit("quota exceeded") is True

    def test_cursor_normal_output_not_rate_limited(self):
        """CursorBackend returns False for normal output."""
        from spec.integrations.backends.cursor import CursorBackend

        backend = CursorBackend()
        assert backend.detect_rate_limit("Task completed successfully") is False

    def test_all_backends_detect_429(self):
        """All backends detect HTTP 429 consistently."""
        for platform in (AgentPlatform.AUGGIE, AgentPlatform.CLAUDE, AgentPlatform.CURSOR):
            backend = BackendFactory.create(platform)
            assert (
                backend.detect_rate_limit("Error 429: rate limit") is True
            ), f"{backend.name} failed to detect 429"

    def test_all_backends_reject_normal_output(self):
        """All backends return False for normal output."""
        for platform in (AgentPlatform.AUGGIE, AgentPlatform.CLAUDE, AgentPlatform.CURSOR):
            backend = BackendFactory.create(platform)
            assert (
                backend.detect_rate_limit("Task completed successfully") is False
            ), f"{backend.name} false positive on normal output"


class TestCompatibilityMatrix:
    """Tests for the backend-platform MCP support compatibility matrix."""

    def test_auggie_supports_jira_mcp(self):
        """Auggie supports Jira via MCP."""
        supported, mechanism = get_platform_support(AgentPlatform.AUGGIE, Platform.JIRA)
        assert supported is True
        assert mechanism == "mcp"

    def test_auggie_supports_linear_mcp(self):
        """Auggie supports Linear via MCP."""
        supported, mechanism = get_platform_support(AgentPlatform.AUGGIE, Platform.LINEAR)
        assert supported is True
        assert mechanism == "mcp"

    def test_auggie_supports_github_mcp(self):
        """Auggie supports GitHub via MCP."""
        supported, mechanism = get_platform_support(AgentPlatform.AUGGIE, Platform.GITHUB)
        assert supported is True
        assert mechanism == "mcp"

    def test_auggie_supports_trello_api(self):
        """Auggie supports Trello via API fallback (not MCP)."""
        supported, mechanism = get_platform_support(AgentPlatform.AUGGIE, Platform.TRELLO)
        assert supported is True
        assert mechanism == "api"

    def test_claude_supports_jira_mcp(self):
        """Claude supports Jira via MCP."""
        supported, mechanism = get_platform_support(AgentPlatform.CLAUDE, Platform.JIRA)
        assert supported is True
        assert mechanism == "mcp"

    def test_cursor_supports_linear_mcp(self):
        """Cursor supports Linear via MCP."""
        supported, mechanism = get_platform_support(AgentPlatform.CURSOR, Platform.LINEAR)
        assert supported is True
        assert mechanism == "mcp"

    def test_manual_no_mcp_support(self):
        """Manual mode has no MCP support but falls back to API."""
        supported, mechanism = get_platform_support(AgentPlatform.MANUAL, Platform.JIRA)
        assert supported is True
        assert mechanism == "api"

    def test_aider_no_mcp_support(self):
        """Aider has no MCP support but falls back to API."""
        supported, mechanism = get_platform_support(AgentPlatform.AIDER, Platform.LINEAR)
        assert supported is True
        assert mechanism == "api"

    def test_aider_trello_api_fallback(self):
        """Aider supports Trello via API fallback."""
        supported, mechanism = get_platform_support(AgentPlatform.AIDER, Platform.TRELLO)
        assert supported is True
        assert mechanism == "api"

    def test_azure_devops_api_for_all_backends(self):
        """Azure DevOps is supported via API for all backends (no MCP)."""
        for backend in AgentPlatform:
            supported, mechanism = get_platform_support(backend, Platform.AZURE_DEVOPS)
            assert supported is True
            assert mechanism == "api"

    def test_monday_api_for_all_backends(self):
        """Monday is supported via API for all backends."""
        for backend in AgentPlatform:
            supported, mechanism = get_platform_support(backend, Platform.MONDAY)
            assert supported is True
            assert mechanism == "api"
