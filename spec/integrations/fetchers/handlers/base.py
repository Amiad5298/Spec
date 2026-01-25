"""Base class for platform-specific API handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import httpx


class PlatformHandler(ABC):
    """Base class for platform-specific API handlers.

    Each handler encapsulates the API-specific logic for fetching
    ticket data from a particular platform.

    HTTP Client Injection:
        Handlers accept an optional `http_client` parameter for testability.
        When provided, the handler uses the injected client instead of
        creating a new one. This enables easy mocking in unit tests.
    """

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Human-readable platform name."""
        pass

    @property
    @abstractmethod
    def required_credential_keys(self) -> frozenset[str]:
        """Set of required credential keys for this platform.

        Returns:
            Frozenset of credential key names that must be present
        """
        pass

    @abstractmethod
    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch ticket data from platform API.

        Args:
            ticket_id: The ticket identifier
            credentials: Immutable credential mapping from AuthenticationManager
            timeout_seconds: Optional request timeout
            http_client: Optional injected HTTP client for testing

        Returns:
            Raw API response as dictionary

        Raises:
            ValueError: If required credential keys are missing
            httpx.HTTPError: For HTTP-level failures
            httpx.TimeoutException: For timeout failures
        """
        pass

    def _validate_credentials(self, credentials: Mapping[str, str]) -> None:
        """Validate that all required credential keys are present.

        Args:
            credentials: Credential mapping to validate

        Raises:
            ValueError: If any required keys are missing
        """
        missing = self.required_credential_keys - set(credentials.keys())
        if missing:
            raise ValueError(
                f"{self.platform_name} handler missing required credentials: {sorted(missing)}"
            )

    def _get_http_client(self, timeout_seconds: float | None = None) -> httpx.AsyncClient:
        """Create configured HTTP client with timeout."""
        timeout = httpx.Timeout(timeout_seconds or 30.0)
        return httpx.AsyncClient(timeout=timeout)
