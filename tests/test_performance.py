"""Tests for Phase 3 performance features: caching, timeouts, scoping, signals."""

from pathlib import PurePosixPath
from unittest.mock import MagicMock

from ingot.discovery.context_builder import ContextBuilder
from ingot.discovery.grep_engine import GrepEngine
from ingot.validation.base import ValidationContext, ValidationSeverity
from ingot.validation.plan_validators import OperationalCompletenessValidator
from ingot.workflow.step1_plan import _extract_ticket_signals

# =============================================================================
# Ticket Signal Extraction
# =============================================================================


class TestTicketSignalExtraction:
    """Tests for _extract_ticket_signals()."""

    def test_metric_signal(self):
        signals = _extract_ticket_signals("Add Prometheus metrics for queue depth")
        assert "metric" in signals

    def test_alert_signal(self):
        signals = _extract_ticket_signals("Configure PagerDuty alerting for high latency")
        assert "alert" in signals

    def test_monitor_signal(self):
        signals = _extract_ticket_signals("Add health check monitoring dashboard")
        assert "monitor" in signals

    def test_endpoint_signal(self):
        signals = _extract_ticket_signals("Create REST API endpoint for user profiles")
        assert "endpoint" in signals

    def test_migration_signal(self):
        signals = _extract_ticket_signals("Database schema migration for user table")
        assert "migration" in signals

    def test_config_signal(self):
        signals = _extract_ticket_signals("Update feature flag configuration for dark mode")
        assert "config" in signals

    def test_refactor_signal(self):
        signals = _extract_ticket_signals("Refactor authentication module")
        assert "refactor" in signals

    def test_security_signal(self):
        signals = _extract_ticket_signals("Add OAuth2 authentication flow")
        assert "security" in signals

    def test_test_signal(self):
        signals = _extract_ticket_signals("Add integration test coverage for payments")
        assert "test" in signals

    def test_multiple_signals(self):
        signals = _extract_ticket_signals(
            "Add Prometheus metric and PagerDuty alert for SQS queue monitoring"
        )
        assert "metric" in signals
        assert "alert" in signals
        assert "monitor" in signals

    def test_empty_text(self):
        signals = _extract_ticket_signals("")
        assert signals == []

    def test_no_matching_signals(self):
        signals = _extract_ticket_signals("Fix typo in README")
        assert signals == []

    def test_case_insensitive(self):
        signals = _extract_ticket_signals("PROMETHEUS METRICS for monitoring")
        assert "metric" in signals


# =============================================================================
# GrepEngine Caching
# =============================================================================


class TestGrepEngineCaching:
    """Tests for GrepEngine result caching."""

    def test_search_caches_results(self, tmp_path):
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        engine = GrepEngine(
            tmp_path,
            [PurePosixPath("test.py")],
        )

        # First search
        results1 = engine.search("hello")
        assert len(results1) == 1

        # Delete the file — cached result should still be returned
        test_file.unlink()
        results2 = engine.search("hello")
        assert len(results2) == 1
        assert results1[0].line_content == results2[0].line_content

    def test_different_patterns_not_cached(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'\n")

        engine = GrepEngine(
            tmp_path,
            [PurePosixPath("test.py")],
        )

        results_hello = engine.search("hello")
        results_world = engine.search("world")
        assert len(results_hello) == 1
        assert len(results_world) == 1
        assert results_hello[0].line_content != results_world[0].line_content

    def test_case_sensitivity_creates_separate_cache_entry(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("def Hello():\n    pass\n")

        engine = GrepEngine(
            tmp_path,
            [PurePosixPath("test.py")],
        )

        results_sensitive = engine.search("hello", ignore_case=False)
        results_insensitive = engine.search("hello", ignore_case=True)
        assert len(results_sensitive) == 0
        assert len(results_insensitive) == 1


# =============================================================================
# GrepEngine Timeout
# =============================================================================


class TestGrepEngineTimeout:
    """Tests for GrepEngine search timeout."""

    def test_timeout_stops_search(self, tmp_path):
        # Create many files to ensure timeout is hit
        for i in range(100):
            (tmp_path / f"file_{i}.py").write_text(f"line {i}\n" * 100)

        file_paths = [PurePosixPath(f"file_{i}.py") for i in range(100)]

        # Set an extremely short timeout
        engine = GrepEngine(
            tmp_path,
            file_paths,
            search_timeout=0.0,  # Immediate timeout
        )

        results = engine.search("line")
        # Should get some results but not all (timeout stops the search)
        # May get 0 if timeout is checked before first file is processed
        assert len(results) < 100 * 100  # Less than total possible matches

    def test_normal_timeout_completes(self, tmp_path):
        test_file = tmp_path / "test.py"
        test_file.write_text("hello world\n")

        engine = GrepEngine(
            tmp_path,
            [PurePosixPath("test.py")],
            search_timeout=30.0,
        )

        results = engine.search("hello")
        assert len(results) == 1


# =============================================================================
# ContextBuilder Large Repo Scoping
# =============================================================================


class TestContextBuilderLargeRepoScoping:
    """Tests for ContextBuilder._scope_paths_for_large_repo()."""

    def test_scoping_reduces_paths(self):
        # Mock FileIndex with many paths
        mock_index = MagicMock()
        all_paths = [
            PurePosixPath(f"src/module{i}/file{j}.py") for i in range(100) for j in range(10)
        ]
        mock_index.all_paths.return_value = all_paths
        mock_index.file_count = len(all_paths)

        # Keyword matches only in module5
        mock_index.find_by_stem.side_effect = lambda stem: (
            [PurePosixPath("src/module5/service.py")] if stem == "service" else []
        )

        scoped = ContextBuilder._scope_paths_for_large_repo(mock_index, ["service"])

        # Should include files from module5 and its parent (src)
        assert len(scoped) < len(all_paths)
        # Files from module5 should be included
        assert any("module5" in str(p) for p in scoped)

    def test_scoping_falls_back_when_no_stems_match(self):
        mock_index = MagicMock()
        all_paths = [PurePosixPath(f"file{i}.py") for i in range(10)]
        mock_index.all_paths.return_value = all_paths
        mock_index.find_by_stem.return_value = []

        scoped = ContextBuilder._scope_paths_for_large_repo(mock_index, ["nonexistent"])

        assert scoped == all_paths  # Falls back to all paths


# =============================================================================
# Signal-Based Validator Severity Elevation
# =============================================================================


class TestSignalBasedSeverity:
    """Tests for OperationalCompletenessValidator severity elevation via signals."""

    def test_info_severity_without_signals(self):
        v = OperationalCompletenessValidator()
        plan = "## Summary\nAdd Prometheus gauge metric for queue monitoring.\n"
        ctx = ValidationContext(ticket_signals=[])
        findings = v.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.INFO

    def test_warning_severity_with_metric_signal(self):
        v = OperationalCompletenessValidator()
        plan = "## Summary\nAdd Prometheus gauge metric for queue monitoring.\n"
        ctx = ValidationContext(ticket_signals=["metric"])
        findings = v.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING

    def test_warning_severity_with_alert_signal(self):
        v = OperationalCompletenessValidator()
        plan = "## Summary\nAdd alert rules for queue depth monitoring.\n"
        ctx = ValidationContext(ticket_signals=["alert"])
        findings = v.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING

    def test_warning_severity_with_monitor_signal(self):
        v = OperationalCompletenessValidator()
        plan = "## Summary\nAdd dashboard for monitoring queue depth.\n"
        ctx = ValidationContext(ticket_signals=["monitor"])
        findings = v.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING

    def test_unrelated_signal_stays_info(self):
        v = OperationalCompletenessValidator()
        plan = "## Summary\nAdd Prometheus gauge metric for queue monitoring.\n"
        ctx = ValidationContext(ticket_signals=["refactor", "config"])
        findings = v.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.INFO
