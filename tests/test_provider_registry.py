"""Tests for spec.integrations.providers.registry module.

Tests cover:
- Decorator registration
- Singleton instance creation
- Platform lookup and error handling
- get_provider_for_input() with PlatformDetector
- Thread safety
- clear() for test isolation
- Dependency injection for UserInteractionInterface
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

import pytest

from spec.integrations.providers.base import (
    GenericTicket,
    IssueTrackerProvider,
    Platform,
)
from spec.integrations.providers.exceptions import PlatformNotSupportedError
from spec.integrations.providers.registry import ProviderRegistry
from spec.integrations.providers.user_interaction import (
    CLIUserInteraction,
    NonInteractiveUserInteraction,
    UserInteractionInterface,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry before and after each test."""
    ProviderRegistry.clear()
    yield
    ProviderRegistry.clear()


class MockJiraProvider(IssueTrackerProvider):
    """Mock Jira provider for testing."""

    PLATFORM = Platform.JIRA

    @property
    def platform(self) -> Platform:
        return Platform.JIRA

    @property
    def name(self) -> str:
        return "Mock Jira"

    def can_handle(self, input_str: str) -> bool:
        return "jira" in input_str.lower() or input_str.upper().startswith("PROJ-")

    def parse_input(self, input_str: str) -> str:
        return input_str.upper()

    def fetch_ticket(self, ticket_id: str) -> GenericTicket:
        return GenericTicket(
            id=ticket_id,
            platform=Platform.JIRA,
            url=f"https://example.atlassian.net/browse/{ticket_id}",
            title="Mock Ticket",
        )

    def check_connection(self) -> tuple[bool, str]:
        return True, "Connected"


class MockGitHubProvider(IssueTrackerProvider):
    """Mock GitHub provider for testing."""

    PLATFORM = Platform.GITHUB

    @property
    def platform(self) -> Platform:
        return Platform.GITHUB

    @property
    def name(self) -> str:
        return "Mock GitHub"

    def can_handle(self, input_str: str) -> bool:
        return "github" in input_str.lower()

    def parse_input(self, input_str: str) -> str:
        return input_str

    def fetch_ticket(self, ticket_id: str) -> GenericTicket:
        return GenericTicket(
            id=ticket_id,
            platform=Platform.GITHUB,
            url=f"https://github.com/{ticket_id}",
            title="Mock Issue",
        )

    def check_connection(self) -> tuple[bool, str]:
        return True, "Connected"


class TestProviderRegistryRegister:
    """Tests for @ProviderRegistry.register decorator."""

    def test_register_decorator_adds_to_registry(self):
        """Decorator adds provider class to registry."""

        @ProviderRegistry.register
        class TestProvider(MockJiraProvider):
            PLATFORM = Platform.JIRA

        assert Platform.JIRA in ProviderRegistry._providers
        assert ProviderRegistry._providers[Platform.JIRA] is TestProvider

    def test_register_without_platform_raises_typeerror(self):
        """Missing PLATFORM attribute raises TypeError."""
        with pytest.raises(TypeError) as exc_info:

            @ProviderRegistry.register
            class BadProvider(IssueTrackerProvider):
                pass

        assert "PLATFORM" in str(exc_info.value)
        assert "BadProvider" in str(exc_info.value)

    def test_register_with_invalid_platform_raises_typeerror(self):
        """Non-Platform PLATFORM attribute raises TypeError."""
        with pytest.raises(TypeError) as exc_info:

            @ProviderRegistry.register
            class BadProvider(IssueTrackerProvider):
                PLATFORM = "jira"  # String instead of Platform enum

        assert "Platform enum value" in str(exc_info.value)

    def test_register_returns_class_unchanged(self):
        """Decorator returns the original class."""

        @ProviderRegistry.register
        class TestProvider(MockJiraProvider):
            PLATFORM = Platform.JIRA

        # Class should be usable normally
        instance = TestProvider()
        assert instance.platform == Platform.JIRA

    def test_register_multiple_providers(self):
        """Can register multiple providers for different platforms."""

        @ProviderRegistry.register
        class JiraProvider(MockJiraProvider):
            PLATFORM = Platform.JIRA

        @ProviderRegistry.register
        class GitHubProvider(MockGitHubProvider):
            PLATFORM = Platform.GITHUB

        assert len(ProviderRegistry._providers) == 2
        assert Platform.JIRA in ProviderRegistry._providers
        assert Platform.GITHUB in ProviderRegistry._providers


class TestProviderRegistryGetProvider:
    """Tests for ProviderRegistry.get_provider()."""

    def test_get_provider_returns_singleton(self):
        """Same instance returned for repeated calls."""
        ProviderRegistry.register(MockJiraProvider)

        provider1 = ProviderRegistry.get_provider(Platform.JIRA)
        provider2 = ProviderRegistry.get_provider(Platform.JIRA)

        assert provider1 is provider2

    def test_get_provider_creates_instance_lazily(self):
        """Provider instance not created until first get."""
        ProviderRegistry.register(MockJiraProvider)

        # No instance yet
        assert Platform.JIRA not in ProviderRegistry._instances

        # Now get it
        provider = ProviderRegistry.get_provider(Platform.JIRA)

        # Instance exists
        assert Platform.JIRA in ProviderRegistry._instances
        assert isinstance(provider, MockJiraProvider)

    def test_get_provider_unregistered_raises_error(self):
        """Unregistered platform raises PlatformNotSupportedError."""
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            ProviderRegistry.get_provider(Platform.JIRA)

        assert "JIRA" in str(exc_info.value)

    def test_get_provider_error_includes_registered_platforms(self):
        """Error message includes list of registered platforms."""
        ProviderRegistry.register(MockGitHubProvider)

        with pytest.raises(PlatformNotSupportedError) as exc_info:
            ProviderRegistry.get_provider(Platform.JIRA)

        error = exc_info.value
        assert "GITHUB" in error.supported_platforms


class TestProviderRegistryGetProviderForInput:
    """Tests for ProviderRegistry.get_provider_for_input()."""

    def test_get_provider_for_input_jira_url(self):
        """Detects Jira from URL and returns provider."""
        ProviderRegistry.register(MockJiraProvider)

        provider = ProviderRegistry.get_provider_for_input(
            "https://company.atlassian.net/browse/PROJ-123"
        )

        assert isinstance(provider, MockJiraProvider)

    def test_get_provider_for_input_jira_id(self):
        """Detects Jira from ticket ID and returns provider."""
        ProviderRegistry.register(MockJiraProvider)

        provider = ProviderRegistry.get_provider_for_input("PROJ-123")

        assert isinstance(provider, MockJiraProvider)

    def test_get_provider_for_input_github_url(self):
        """Detects GitHub from URL and returns provider."""
        ProviderRegistry.register(MockGitHubProvider)

        provider = ProviderRegistry.get_provider_for_input(
            "https://github.com/owner/repo/issues/42"
        )

        assert isinstance(provider, MockGitHubProvider)

    def test_get_provider_for_input_unknown_raises_error(self):
        """Unknown input raises PlatformNotSupportedError."""
        with pytest.raises(PlatformNotSupportedError):
            ProviderRegistry.get_provider_for_input("unknown-input-format")

    def test_get_provider_for_input_detected_but_not_registered(self):
        """Detected platform without registered provider raises error."""
        # Don't register any provider
        # Jira ID format will be detected but no provider registered
        with pytest.raises(PlatformNotSupportedError) as exc_info:
            ProviderRegistry.get_provider_for_input("PROJ-123")

        assert "JIRA" in str(exc_info.value)


class TestProviderRegistryUtilityMethods:
    """Tests for utility methods."""

    def test_list_platforms_returns_registered(self):
        """list_platforms() returns all registered platforms."""
        ProviderRegistry.register(MockJiraProvider)
        ProviderRegistry.register(MockGitHubProvider)

        platforms = ProviderRegistry.list_platforms()

        assert Platform.JIRA in platforms
        assert Platform.GITHUB in platforms
        assert len(platforms) == 2

    def test_list_platforms_empty_initially(self):
        """list_platforms() returns empty list after clear()."""
        platforms = ProviderRegistry.list_platforms()
        assert platforms == []

    def test_clear_resets_providers_and_instances(self):
        """clear() removes all providers and instances."""
        ProviderRegistry.register(MockJiraProvider)
        _ = ProviderRegistry.get_provider(Platform.JIRA)

        # Verify they exist
        assert len(ProviderRegistry._providers) == 1
        assert len(ProviderRegistry._instances) == 1

        # Clear
        ProviderRegistry.clear()

        # Verify they're gone
        assert len(ProviderRegistry._providers) == 0
        assert len(ProviderRegistry._instances) == 0

    def test_set_user_interaction(self):
        """set_user_interaction() sets the UI implementation."""
        mock_ui = MagicMock(spec=UserInteractionInterface)

        ProviderRegistry.set_user_interaction(mock_ui)

        assert ProviderRegistry._user_interaction is mock_ui

    def test_get_user_interaction_returns_current(self):
        """get_user_interaction() returns current implementation."""
        mock_ui = MagicMock(spec=UserInteractionInterface)
        ProviderRegistry.set_user_interaction(mock_ui)

        result = ProviderRegistry.get_user_interaction()

        assert result is mock_ui

    def test_default_user_interaction_is_cli(self):
        """Default user interaction is CLIUserInteraction."""
        # After clear(), should reset to CLI
        ui = ProviderRegistry.get_user_interaction()
        assert isinstance(ui, CLIUserInteraction)

    def test_set_non_interactive_user_interaction(self):
        """Can set NonInteractiveUserInteraction for testing."""
        non_interactive = NonInteractiveUserInteraction(fail_on_interaction=True)

        ProviderRegistry.set_user_interaction(non_interactive)

        result = ProviderRegistry.get_user_interaction()
        assert isinstance(result, NonInteractiveUserInteraction)


class TestProviderRegistryThreadSafety:
    """Tests for thread-safe singleton instantiation."""

    def test_concurrent_get_provider_returns_same_instance(self):
        """Concurrent calls to get_provider() return same instance."""
        ProviderRegistry.register(MockJiraProvider)

        instances = []
        errors = []

        def get_provider():
            try:
                provider = ProviderRegistry.get_provider(Platform.JIRA)
                instances.append(provider)
            except Exception as e:
                errors.append(e)

        # Run many concurrent calls
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_provider) for _ in range(100)]
            for future in futures:
                future.result()

        # No errors
        assert len(errors) == 0

        # All instances are the same object
        assert len(instances) == 100
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance

    def test_concurrent_registration_and_lookup(self):
        """Concurrent registration and lookup works correctly."""
        results = {"registered": False, "found": []}
        errors = []

        def register_provider():
            try:
                ProviderRegistry.register(MockJiraProvider)
                results["registered"] = True
            except Exception as e:
                errors.append(e)

        def lookup_provider():
            try:
                # May fail if not registered yet, that's OK
                provider = ProviderRegistry.get_provider(Platform.JIRA)
                results["found"].append(provider)
            except PlatformNotSupportedError:
                pass  # Expected if registration hasn't happened yet
            except Exception as e:
                errors.append(e)

        threads = []
        # Start registration thread
        t1 = threading.Thread(target=register_provider)
        threads.append(t1)

        # Start multiple lookup threads
        for _ in range(5):
            t = threading.Thread(target=lookup_provider)
            threads.append(t)

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all to complete
        for t in threads:
            t.join()

        # No unexpected errors
        assert len(errors) == 0

        # Registration succeeded
        assert results["registered"] is True


class TestProviderRegistryImport:
    """Tests for module imports."""

    def test_import_from_providers_package(self):
        """Can import ProviderRegistry from providers package."""
        from spec.integrations.providers import ProviderRegistry as PR

        assert PR is ProviderRegistry

    def test_in_all_exports(self):
        """ProviderRegistry is in __all__ exports."""
        from spec.integrations.providers import __all__

        assert "ProviderRegistry" in __all__
