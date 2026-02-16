"""Tests for BackendModel dataclass and backend list_models() methods."""

from __future__ import annotations

from unittest.mock import patch

from ingot.integrations.backends.base import BackendModel, BaseBackend


class TestBackendModel:
    def test_create_with_defaults(self):
        model = BackendModel(id="claude-3", name="Claude 3")
        assert model.id == "claude-3"
        assert model.name == "Claude 3"
        assert model.description == ""

    def test_create_with_description(self):
        model = BackendModel(id="gpt-4", name="GPT-4", description="Latest GPT model")
        assert model.description == "Latest GPT model"

    def test_equality(self):
        m1 = BackendModel(id="x", name="X")
        m2 = BackendModel(id="x", name="X")
        assert m1 == m2


class TestBaseBackendListModels:
    def test_returns_empty_list(self):
        """BaseBackend.list_models() returns [] by default."""

        class ConcreteBackend(BaseBackend):
            @property
            def name(self):
                return "Test"

            @property
            def platform(self):
                from ingot.config.fetch_config import AgentPlatform

                return AgentPlatform.AUGGIE

            def run_with_callback(self, *a, **kw):
                pass

            def run_print_with_output(self, *a, **kw):
                pass

            def run_print_quiet(self, *a, **kw):
                pass

            def run_streaming(self, *a, **kw):
                pass

            def check_installed(self):
                return True, "ok"

            def detect_rate_limit(self, output):
                return False

        backend = ConcreteBackend()
        assert backend.list_models() == []


class TestListModelsCaching:
    """Tests for list_models() caching logic on BaseBackend."""

    def _make_backend(self, fetch_side_effects: list):
        """Create a ConcreteBackend whose _fetch_models returns values in sequence."""
        call_index = {"i": 0}
        side_effects = fetch_side_effects

        class ConcreteBackend(BaseBackend):
            @property
            def name(self):
                return "Test"

            @property
            def platform(self):
                from ingot.config.fetch_config import AgentPlatform

                return AgentPlatform.AUGGIE

            def run_with_callback(self, *a, **kw):
                pass

            def run_print_with_output(self, *a, **kw):
                pass

            def run_print_quiet(self, *a, **kw):
                pass

            def run_streaming(self, *a, **kw):
                pass

            def check_installed(self):
                return True, "ok"

            def detect_rate_limit(self, output):
                return False

            def _fetch_models(self):
                idx = call_index["i"]
                call_index["i"] += 1
                return side_effects[idx]

        return ConcreteBackend(), call_index

    def test_empty_result_not_cached_and_retries(self):
        """First call returns [] (transient failure) → second call retries."""
        models = [BackendModel(id="m1", name="Model 1")]
        backend, calls = self._make_backend([[], models])

        first = backend.list_models()
        assert first == []

        second = backend.list_models()
        assert second == models
        assert calls["i"] == 2  # _fetch_models called twice

    def test_non_empty_result_is_cached(self):
        """Non-empty result is cached; subsequent calls do not re-fetch."""
        models = [BackendModel(id="m1", name="Model 1")]
        backend, calls = self._make_backend([models, []])

        first = backend.list_models()
        second = backend.list_models()

        assert first == second == models
        assert calls["i"] == 1  # _fetch_models called only once

    def test_defensive_copy_prevents_cache_mutation(self):
        """Mutating the returned list does not affect cached value."""
        models = [BackendModel(id="m1", name="Model 1")]
        backend, _ = self._make_backend([models])

        first = backend.list_models()
        first.clear()

        second = backend.list_models()
        assert second == models


class TestClaudeBackendListModels:
    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key_returns_fallback(self):
        from ingot.integrations.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert all(isinstance(m, BackendModel) for m in models)
        assert any("claude" in m.id for m in models)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ingot.integrations.backends.model_discovery.fetch_anthropic_models")
    def test_api_success_returns_dynamic(self, mock_fetch):
        from ingot.integrations.backends.claude import ClaudeBackend

        mock_fetch.return_value = [BackendModel(id="claude-new", name="Claude New")]
        backend = ClaudeBackend()
        models = backend.list_models()
        assert len(models) == 1
        assert models[0].id == "claude-new"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ingot.integrations.backends.model_discovery.fetch_anthropic_models")
    def test_api_failure_returns_fallback(self, mock_fetch):
        from ingot.integrations.backends.claude import ClaudeBackend

        mock_fetch.return_value = []
        backend = ClaudeBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert any("claude" in m.id for m in models)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    @patch("ingot.integrations.backends.model_discovery.fetch_anthropic_models")
    def test_caching_calls_fetch_only_once(self, mock_fetch):
        """list_models() should cache: _fetch_models (via API) called only once."""
        from ingot.integrations.backends.claude import ClaudeBackend

        mock_fetch.return_value = [BackendModel(id="claude-cached", name="Cached")]
        backend = ClaudeBackend()

        first = backend.list_models()
        second = backend.list_models()

        assert first == second
        mock_fetch.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    def test_cache_returns_defensive_copy(self):
        """Mutating returned list should not affect the cache."""
        from ingot.integrations.backends.claude import ClaudeBackend

        backend = ClaudeBackend()
        first = backend.list_models()
        first.clear()
        second = backend.list_models()
        assert len(second) >= 1


class TestCursorBackendListModels:
    def test_returns_hardcoded_models(self):
        from ingot.integrations.backends.cursor import CursorBackend

        backend = CursorBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert all(isinstance(m, BackendModel) for m in models)


class TestAiderBackendListModels:
    def test_returns_hardcoded_models(self):
        from ingot.integrations.backends.aider import AiderBackend

        backend = AiderBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert all(isinstance(m, BackendModel) for m in models)


class TestGeminiBackendListModels:
    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key_returns_fallback(self):
        from ingot.integrations.backends.gemini import GeminiBackend

        backend = GeminiBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert any("gemini" in m.id for m in models)

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    @patch("ingot.integrations.backends.model_discovery.fetch_gemini_models")
    def test_api_success_returns_dynamic(self, mock_fetch):
        from ingot.integrations.backends.gemini import GeminiBackend

        mock_fetch.return_value = [BackendModel(id="gemini-new", name="Gemini New")]
        backend = GeminiBackend()
        models = backend.list_models()
        assert len(models) == 1
        assert models[0].id == "gemini-new"


class TestCodexBackendListModels:
    @patch.dict("os.environ", {}, clear=True)
    def test_no_api_key_returns_fallback(self):
        from ingot.integrations.backends.codex import CodexBackend

        backend = CodexBackend()
        models = backend.list_models()
        assert len(models) >= 1
        assert any(m.id in ("o3", "o4-mini", "gpt-4.1") for m in models)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("ingot.integrations.backends.model_discovery.fetch_openai_models")
    def test_api_success_returns_dynamic(self, mock_fetch):
        from ingot.integrations.backends.codex import CodexBackend

        mock_fetch.return_value = [BackendModel(id="o3", name="o3")]
        backend = CodexBackend()
        models = backend.list_models()
        assert len(models) == 1
        assert models[0].id == "o3"


class TestAuggieBackendListModels:
    @patch("ingot.integrations.backends.auggie.auggie_list_models")
    def test_wraps_auggie_models(self, mock_list):
        from ingot.integrations.auggie import AuggieModel
        from ingot.integrations.backends.auggie import AuggieBackend

        mock_list.return_value = [
            AuggieModel(name="Model A", id="model-a", description="Desc A"),
        ]
        backend = AuggieBackend()
        models = backend.list_models()
        assert len(models) == 1
        assert models[0].id == "model-a"
        assert models[0].name == "Model A"
        assert isinstance(models[0], BackendModel)

    @patch("ingot.integrations.backends.auggie.auggie_list_models")
    def test_empty_when_cli_returns_nothing(self, mock_list):
        from ingot.integrations.backends.auggie import AuggieBackend

        mock_list.return_value = []
        backend = AuggieBackend()
        assert backend.list_models() == []
