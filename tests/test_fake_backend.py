"""Self-tests for the FakeBackend test helper.

Validates that FakeBackend correctly implements the AIBackend protocol
and that all its test-support features (call recording, configurable
responses, convenience factories) work as documented.
"""

from __future__ import annotations

import pytest

from spec.config.fetch_config import AgentPlatform
from spec.integrations.backends.base import AIBackend
from tests.fakes.fake_backend import (
    FakeBackend,
    make_failing_backend,
    make_rate_limited_backend,
    make_successful_backend,
)


class TestFakeBackendProtocol:
    """Verify FakeBackend implements the AIBackend protocol."""

    def test_isinstance_aibackend(self):
        """FakeBackend instances satisfy isinstance(_, AIBackend)."""
        fb = FakeBackend([(True, "ok")])
        assert isinstance(fb, AIBackend)

    def test_has_all_protocol_methods(self):
        """FakeBackend exposes every method required by AIBackend."""
        fb = FakeBackend([(True, "ok")])
        for attr in (
            "name",
            "platform",
            "model",
            "supports_parallel",
            "run_with_callback",
            "run_print_with_output",
            "run_print_quiet",
            "run_streaming",
            "check_installed",
            "detect_rate_limit",
            "supports_parallel_execution",
            "close",
        ):
            assert hasattr(fb, attr), f"Missing protocol member: {attr}"


class TestFakeBackendResponses:
    """Test configurable response behaviour."""

    def test_returns_responses_in_order(self):
        """Responses are returned in the order they were configured."""
        fb = FakeBackend([(True, "first"), (False, "second")])
        assert fb.run_print_with_output("p1") == (True, "first")
        assert fb.run_print_with_output("p2") == (False, "second")

    def test_exhaustion_raises_index_error(self):
        """IndexError is raised when all responses have been consumed."""
        fb = FakeBackend([(True, "only")])
        fb.run_print_with_output("p1")
        with pytest.raises(IndexError, match="FakeBackend exhausted"):
            fb.run_print_with_output("p2")

    def test_call_count_increments(self):
        """call_count tracks total calls across all run_* methods."""
        fb = FakeBackend([(True, "a"), (True, "b"), (True, "c"), (True, "d")])
        fb.run_print_with_output("p")
        fb.run_print_quiet("p")
        fb.run_streaming("p")
        fb.run_with_callback("p", output_callback=lambda _: None)
        assert fb.call_count == 4


class TestFakeBackendCallRecording:
    """Test that each run method records calls correctly."""

    def test_run_with_callback_recorded(self):
        """run_with_callback appends to calls list."""
        fb = FakeBackend([(True, "out")])
        fb.run_with_callback("hello", output_callback=lambda _: None, model="gpt-4")
        assert len(fb.calls) == 1
        prompt, kwargs = fb.calls[0]
        assert prompt == "hello"
        assert kwargs["model"] == "gpt-4"

    def test_run_print_quiet_recorded(self):
        """run_print_quiet appends to quiet_calls list."""
        fb = FakeBackend([(True, "out")])
        fb.run_print_quiet("quiet prompt", subagent="planner")
        assert len(fb.quiet_calls) == 1
        prompt, kwargs = fb.quiet_calls[0]
        assert prompt == "quiet prompt"
        assert kwargs["subagent"] == "planner"

    def test_run_print_with_output_recorded(self):
        """run_print_with_output appends to print_with_output_calls list."""
        fb = FakeBackend([(True, "out")])
        fb.run_print_with_output("loud prompt")
        assert len(fb.print_with_output_calls) == 1
        assert fb.print_with_output_calls[0][0] == "loud prompt"

    def test_run_streaming_recorded(self):
        """run_streaming appends to streaming_calls list."""
        fb = FakeBackend([(True, "out")])
        fb.run_streaming("stream prompt")
        assert len(fb.streaming_calls) == 1
        assert fb.streaming_calls[0][0] == "stream prompt"


class TestFakeBackendStreamingCallback:
    """Test that run_with_callback streams output to the callback."""

    def test_callback_called_per_line(self):
        """output_callback receives each line of multi-line output."""
        lines_received: list[str] = []
        fb = FakeBackend([(True, "line1\nline2\nline3")])
        fb.run_with_callback("p", output_callback=lines_received.append)
        assert lines_received == ["line1", "line2", "line3"]

    def test_callback_single_line(self):
        """output_callback works with single-line output."""
        lines_received: list[str] = []
        fb = FakeBackend([(True, "single")])
        fb.run_with_callback("p", output_callback=lines_received.append)
        assert lines_received == ["single"]

    def test_callback_returns_full_output(self):
        """run_with_callback returns the full output string."""
        fb = FakeBackend([(True, "line1\nline2")])
        success, output = fb.run_with_callback("p", output_callback=lambda _: None)
        assert success is True
        assert output == "line1\nline2"


class TestFakeBackendProperties:
    """Test configurable properties."""

    def test_default_name(self):
        """Default name is 'FakeBackend'."""
        fb = FakeBackend([(True, "ok")])
        assert fb.name == "FakeBackend"

    def test_custom_name(self):
        """Name can be customized via constructor."""
        fb = FakeBackend([(True, "ok")], name="CustomBot")
        assert fb.name == "CustomBot"

    def test_default_platform(self):
        """Default platform is AUGGIE."""
        fb = FakeBackend([(True, "ok")])
        assert fb.platform == AgentPlatform.AUGGIE

    def test_custom_platform(self):
        """Platform can be customized via constructor."""
        fb = FakeBackend([(True, "ok")], platform=AgentPlatform.CLAUDE)
        assert fb.platform == AgentPlatform.CLAUDE

    def test_default_supports_parallel(self):
        """Default supports_parallel is True."""
        fb = FakeBackend([(True, "ok")])
        assert fb.supports_parallel is True

    def test_custom_supports_parallel(self):
        """supports_parallel can be set to False."""
        fb = FakeBackend([(True, "ok")], supports_parallel=False)
        assert fb.supports_parallel is False

    def test_supports_parallel_execution_delegates(self):
        """supports_parallel_execution() returns supports_parallel value."""
        fb = FakeBackend([(True, "ok")], supports_parallel=False)
        assert fb.supports_parallel_execution() is False

    def test_model_returns_empty_string(self):
        """Model property returns empty string."""
        fb = FakeBackend([(True, "ok")])
        assert fb.model == ""


class TestFakeBackendClose:
    """Test close() and closed attribute tracking."""

    def test_closed_initially_false(self):
        """closed is False before close() is called."""
        fb = FakeBackend([(True, "ok")])
        assert fb.closed is False

    def test_closed_after_close(self):
        """closed is True after close() is called."""
        fb = FakeBackend([(True, "ok")])
        fb.close()
        assert fb.closed is True

    def test_close_idempotent(self):
        """close() can be called multiple times safely."""
        fb = FakeBackend([(True, "ok")])
        fb.close()
        fb.close()
        assert fb.closed is True


class TestFakeBackendCheckInstalled:
    """Test the installed flag."""

    def test_installed_true(self):
        """check_installed returns (True, version) when installed=True."""
        fb = FakeBackend([(True, "ok")], installed=True)
        installed, msg = fb.check_installed()
        assert installed is True
        assert "1.0.0" in msg

    def test_installed_false(self):
        """check_installed returns (False, error) when installed=False."""
        fb = FakeBackend([(True, "ok")], installed=False)
        installed, msg = fb.check_installed()
        assert installed is False
        assert "not installed" in msg.lower()


class TestFakeBackendDetectRateLimit:
    """Test rate limit detection via matches_common_rate_limit."""

    def test_detects_429(self):
        """detect_rate_limit identifies HTTP 429 in output."""
        fb = FakeBackend([(True, "ok")])
        assert fb.detect_rate_limit("Error 429: rate limit hit") is True

    def test_detects_rate_limit_keyword(self):
        """detect_rate_limit identifies 'rate limit' keyword."""
        fb = FakeBackend([(True, "ok")])
        assert fb.detect_rate_limit("You hit the rate limit") is True

    def test_normal_output_not_rate_limited(self):
        """detect_rate_limit returns False for normal output."""
        fb = FakeBackend([(True, "ok")])
        assert fb.detect_rate_limit("Task completed successfully") is False

    def test_empty_output_not_rate_limited(self):
        """detect_rate_limit returns False for empty output."""
        fb = FakeBackend([(True, "ok")])
        assert fb.detect_rate_limit("") is False


class TestConvenienceFactories:
    """Test make_successful_backend, make_failing_backend, make_rate_limited_backend."""

    def test_make_successful_backend_default(self):
        """make_successful_backend returns (True, 'success') by default."""
        fb = make_successful_backend()
        result = fb.run_print_with_output("p")
        assert result == (True, "success")

    def test_make_successful_backend_custom_output(self):
        """make_successful_backend accepts custom output."""
        fb = make_successful_backend("custom result")
        result = fb.run_print_with_output("p")
        assert result == (True, "custom result")

    def test_make_failing_backend_default(self):
        """make_failing_backend returns (False, 'error') by default."""
        fb = make_failing_backend()
        result = fb.run_print_with_output("p")
        assert result == (False, "error")

    def test_make_failing_backend_custom_error(self):
        """make_failing_backend accepts custom error message."""
        fb = make_failing_backend("custom error")
        result = fb.run_print_with_output("p")
        assert result == (False, "custom error")

    def test_make_rate_limited_backend_default(self):
        """make_rate_limited_backend fails twice then succeeds."""
        fb = make_rate_limited_backend()
        r1 = fb.run_print_with_output("p1")
        r2 = fb.run_print_with_output("p2")
        r3 = fb.run_print_with_output("p3")
        assert r1 == (False, "Error 429: rate limit hit")
        assert r2 == (False, "Error 429: rate limit hit")
        assert r3 == (True, "Task completed successfully")

    def test_make_rate_limited_backend_custom_count(self):
        """make_rate_limited_backend respects custom fail_count."""
        fb = make_rate_limited_backend(fail_count=1)
        r1 = fb.run_print_with_output("p1")
        r2 = fb.run_print_with_output("p2")
        assert r1[0] is False
        assert r2[0] is True

    def test_factories_return_fakebackend_instances(self):
        """All factories return FakeBackend instances."""
        assert isinstance(make_successful_backend(), FakeBackend)
        assert isinstance(make_failing_backend(), FakeBackend)
        assert isinstance(make_rate_limited_backend(), FakeBackend)


class TestFakeBackendEdgeCases:
    """Edge cases and additional coverage."""

    def test_empty_responses_fails_immediately(self):
        """FakeBackend with empty responses raises IndexError on first call."""
        fb = FakeBackend([])
        with pytest.raises(IndexError, match="FakeBackend exhausted"):
            fb.run_print_with_output("p")

    def test_empty_responses_all_methods_fail(self):
        """All run methods fail with IndexError on empty responses."""
        fb1 = FakeBackend([])
        with pytest.raises(IndexError):
            fb1.run_print_quiet("p")

        fb2 = FakeBackend([])
        with pytest.raises(IndexError):
            fb2.run_streaming("p")

        fb3 = FakeBackend([])
        with pytest.raises(IndexError):
            fb3.run_with_callback("p", output_callback=lambda _: None)

    def test_model_recorded_in_run_with_callback(self):
        """model kwarg is recorded in run_with_callback calls."""
        fb = FakeBackend([(True, "ok")])
        fb.run_with_callback("p", output_callback=lambda _: None, model="claude-3")
        assert fb.calls[0][1]["model"] == "claude-3"

    def test_model_recorded_in_run_print_with_output(self):
        """model kwarg is recorded in run_print_with_output calls."""
        fb = FakeBackend([(True, "ok")])
        fb.run_print_with_output("p", model="gpt-4")
        assert fb.print_with_output_calls[0][1]["model"] == "gpt-4"

    def test_model_recorded_in_run_print_quiet(self):
        """model kwarg is recorded in run_print_quiet calls."""
        fb = FakeBackend([(True, "ok")])
        fb.run_print_quiet("p", model="sonnet")
        assert fb.quiet_calls[0][1]["model"] == "sonnet"

    def test_model_recorded_in_run_streaming(self):
        """model kwarg is recorded in run_streaming calls."""
        fb = FakeBackend([(True, "ok")])
        fb.run_streaming("p", model="opus")
        assert fb.streaming_calls[0][1]["model"] == "opus"

    def test_model_none_by_default(self):
        """model defaults to None when not specified."""
        fb = FakeBackend([(True, "ok")])
        fb.run_print_with_output("p")
        assert fb.print_with_output_calls[0][1]["model"] is None

    def test_subagent_recorded(self):
        """subagent kwarg is correctly recorded across methods."""
        fb = FakeBackend([(True, "a"), (True, "b")])
        fb.run_print_with_output("p", subagent="spec-planner")
        fb.run_with_callback("p", output_callback=lambda _: None, subagent="spec-implementer")
        assert fb.print_with_output_calls[0][1]["subagent"] == "spec-planner"
        assert fb.calls[0][1]["subagent"] == "spec-implementer"

    def test_timeout_seconds_recorded(self):
        """timeout_seconds kwarg is correctly recorded."""
        fb = FakeBackend([(True, "ok")])
        fb.run_with_callback("p", output_callback=lambda _: None, timeout_seconds=30.0)
        assert fb.calls[0][1]["timeout_seconds"] == 30.0

    def test_callback_with_empty_output(self):
        """run_with_callback handles empty string output (no callback calls)."""
        lines: list[str] = []
        fb = FakeBackend([(True, "")])
        success, output = fb.run_with_callback("p", output_callback=lines.append)
        assert success is True
        assert output == ""
        # splitlines() on empty string returns [], so callback is never called
        assert lines == []

    def test_mixed_method_calls_share_call_count(self):
        """call_count is shared across all methods, not per-method."""
        fb = FakeBackend([(True, "a"), (True, "b"), (True, "c")])
        fb.run_print_with_output("p1")
        fb.run_print_quiet("p2")
        fb.run_streaming("p3")
        assert fb.call_count == 3
        assert len(fb.print_with_output_calls) == 1
        assert len(fb.quiet_calls) == 1
        assert len(fb.streaming_calls) == 1
