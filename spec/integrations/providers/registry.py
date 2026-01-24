"""Provider Registry for issue tracker provider management.

This module provides:
- ProviderRegistry class for centralized provider registration and lookup
- Factory pattern for provider instantiation
- Singleton pattern for memory efficiency and connection reuse
- Decorator-based registration for providers

Example usage:
    from spec.integrations.providers import ProviderRegistry, Platform

    # Register a provider (typically done via decorator)
    @ProviderRegistry.register
    class JiraProvider(IssueTrackerProvider):
        PLATFORM = Platform.JIRA
        ...

    # Get provider instance
    provider = ProviderRegistry.get_provider(Platform.JIRA)

    # Or auto-detect from input
    provider = ProviderRegistry.get_provider_for_input("PROJ-123")
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from spec.integrations.providers.base import IssueTrackerProvider, Platform
from spec.integrations.providers.detector import PlatformDetector
from spec.integrations.providers.exceptions import PlatformNotSupportedError
from spec.integrations.providers.user_interaction import (
    CLIUserInteraction,
    UserInteractionInterface,
)

if TYPE_CHECKING:
    pass


class ProviderRegistry:
    """Registry for issue tracker providers.

    Provides centralized factory for provider instantiation using:
    - Factory Pattern: Provider classes register themselves
    - Singleton Pattern: One provider instance per platform
    - Decorator-based Registration: Providers use @ProviderRegistry.register

    All methods are class methods - no instance needed.
    Thread-safe singleton instantiation using threading.Lock.
    """

    _providers: dict[Platform, type[IssueTrackerProvider]] = {}
    _instances: dict[Platform, IssueTrackerProvider] = {}
    _user_interaction: UserInteractionInterface = CLIUserInteraction()
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, provider_class: type[IssueTrackerProvider]) -> type[IssueTrackerProvider]:
        """Decorator to register a provider class.

        The provider class must have a PLATFORM class attribute that specifies
        which platform it handles.

        Args:
            provider_class: The provider class to register

        Returns:
            The provider class unchanged (for decorator chaining)

        Raises:
            TypeError: If provider_class doesn't have a PLATFORM attribute
        """
        if not hasattr(provider_class, "PLATFORM"):
            raise TypeError(
                f"Provider class {provider_class.__name__} must have a PLATFORM " "class attribute"
            )

        platform = provider_class.PLATFORM
        if not isinstance(platform, Platform):
            raise TypeError(
                f"PLATFORM attribute of {provider_class.__name__} must be a "
                f"Platform enum value, got {type(platform).__name__}"
            )

        cls._providers[platform] = provider_class
        return provider_class

    @classmethod
    def get_provider(cls, platform: Platform) -> IssueTrackerProvider:
        """Get singleton provider instance for a platform.

        Uses lazy instantiation - provider is only created when first requested.
        Thread-safe using threading.Lock.

        Args:
            platform: The platform to get provider for

        Returns:
            The singleton provider instance

        Raises:
            PlatformNotSupportedError: If no provider is registered for platform
        """
        if platform not in cls._providers:
            registered = [p.name for p in cls._providers.keys()]
            raise PlatformNotSupportedError(
                message=f"No provider registered for platform: {platform.name}",
                supported_platforms=registered,
            )

        # Thread-safe singleton instantiation
        if platform not in cls._instances:
            with cls._lock:
                # Double-check locking pattern
                if platform not in cls._instances:
                    provider_class = cls._providers[platform]
                    cls._instances[platform] = provider_class()

        return cls._instances[platform]

    @classmethod
    def get_provider_for_input(cls, input_str: str) -> IssueTrackerProvider:
        """Get provider instance based on input URL or ticket ID.

        Convenience method that combines platform detection with provider lookup.
        Uses PlatformDetector to determine the platform from the input.

        Args:
            input_str: URL or ticket ID to detect platform from

        Returns:
            The singleton provider instance for the detected platform

        Raises:
            PlatformNotSupportedError: If platform cannot be detected or
                no provider is registered for the detected platform
        """
        platform, _ = PlatformDetector.detect(input_str)
        return cls.get_provider(platform)

    @classmethod
    def list_platforms(cls) -> list[Platform]:
        """List all registered platforms.

        Returns:
            List of Platform enum values that have registered providers
        """
        return list(cls._providers.keys())

    @classmethod
    def set_user_interaction(cls, ui: UserInteractionInterface) -> None:
        """Set the user interaction implementation.

        Enables dependency injection for testing or different UI implementations.

        Args:
            ui: The UserInteractionInterface implementation to use
        """
        cls._user_interaction = ui

    @classmethod
    def get_user_interaction(cls) -> UserInteractionInterface:
        """Get the current user interaction implementation.

        Returns:
            The current UserInteractionInterface implementation
        """
        return cls._user_interaction

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations and instances.

        Used for test isolation to reset registry state between tests.
        """
        cls._providers.clear()
        cls._instances.clear()
        cls._user_interaction = CLIUserInteraction()
