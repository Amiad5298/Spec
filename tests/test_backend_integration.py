"""Integration tests for multi-backend system.

All tests are gated behind SPEC_INTEGRATION_TESTS=1 and require the
actual backend CLIs to be installed. These tests verify real backend
instances against the AIBackend protocol contract.

Usage:
    # Skipped by default:
    pytest tests/test_backend_integration.py -v

    # Run when enabled (requires CLIs installed):
    SPEC_INTEGRATION_TESTS=1 pytest tests/test_backend_integration.py -v
"""

from __future__ import annotations

import os

import pytest

from spec.config.fetch_config import AgentPlatform
from spec.integrations.backends.base import AIBackend
from spec.integrations.backends.factory import BackendFactory

pytestmark = pytest.mark.skipif(
    os.environ.get("SPEC_INTEGRATION_TESTS") != "1",
    reason="Integration tests disabled. Set SPEC_INTEGRATION_TESTS=1 to enable.",
)

_PLATFORMS = [
    AgentPlatform.AUGGIE,
    AgentPlatform.CLAUDE,
    AgentPlatform.CURSOR,
]


@pytest.mark.parametrize("platform", _PLATFORMS, ids=lambda p: p.value)
class TestBackendProtocolCompliance:
    """Verify real backends satisfy the AIBackend protocol."""

    def test_isinstance_aibackend(self, platform: AgentPlatform):
        """Backend instance satisfies isinstance(_, AIBackend)."""
        backend = BackendFactory.create(platform)
        assert isinstance(backend, AIBackend)

    def test_name_is_string(self, platform: AgentPlatform):
        """Backend name property returns a non-empty string."""
        backend = BackendFactory.create(platform)
        assert isinstance(backend.name, str)
        assert len(backend.name) > 0

    def test_platform_is_ai_backend_platform(self, platform: AgentPlatform):
        """Backend platform property returns an AgentPlatform enum."""
        backend = BackendFactory.create(platform)
        assert isinstance(backend.platform, AgentPlatform)
        assert backend.platform == platform

    def test_model_is_string(self, platform: AgentPlatform):
        """Backend model property returns a string."""
        backend = BackendFactory.create(platform)
        assert isinstance(backend.model, str)

    def test_supports_parallel_is_bool(self, platform: AgentPlatform):
        """Backend supports_parallel property returns a bool."""
        backend = BackendFactory.create(platform)
        assert isinstance(backend.supports_parallel, bool)

    def test_run_methods_are_callable(self, platform: AgentPlatform):
        """All required run_* methods are callable."""
        backend = BackendFactory.create(platform)
        for method_name in (
            "run_with_callback",
            "run_print_with_output",
            "run_print_quiet",
            "run_streaming",
        ):
            assert callable(getattr(backend, method_name))

    def test_check_installed_is_callable(self, platform: AgentPlatform):
        """check_installed method is callable."""
        backend = BackendFactory.create(platform)
        assert callable(backend.check_installed)

    def test_detect_rate_limit_is_callable(self, platform: AgentPlatform):
        """detect_rate_limit method is callable."""
        backend = BackendFactory.create(platform)
        assert callable(backend.detect_rate_limit)

    def test_close_is_callable(self, platform: AgentPlatform):
        """close method is callable."""
        backend = BackendFactory.create(platform)
        assert callable(backend.close)

    def test_supports_parallel_execution_is_callable(self, platform: AgentPlatform):
        """supports_parallel_execution method is callable."""
        backend = BackendFactory.create(platform)
        assert callable(backend.supports_parallel_execution)


@pytest.mark.parametrize("platform", _PLATFORMS, ids=lambda p: p.value)
class TestBackendCheckInstalled:
    """Verify check_installed() returns correct types."""

    def test_check_installed_returns_tuple(self, platform: AgentPlatform):
        """check_installed() returns a (bool, str) tuple."""
        backend = BackendFactory.create(platform)
        result = backend.check_installed()
        assert isinstance(result, tuple)
        assert len(result) == 2
        installed, message = result
        assert isinstance(installed, bool)
        assert isinstance(message, str)

    def test_detect_rate_limit_returns_bool(self, platform: AgentPlatform):
        """detect_rate_limit() returns a bool for normal output."""
        backend = BackendFactory.create(platform)
        result = backend.detect_rate_limit("normal output")
        assert isinstance(result, bool)
        assert result is False

    def test_detect_rate_limit_detects_429(self, platform: AgentPlatform):
        """detect_rate_limit() detects HTTP 429 across all backends."""
        backend = BackendFactory.create(platform)
        assert backend.detect_rate_limit("Error 429: rate limit") is True

    def test_close_does_not_raise(self, platform: AgentPlatform):
        """close() completes without raising."""
        backend = BackendFactory.create(platform)
        backend.close()  # Should not raise
