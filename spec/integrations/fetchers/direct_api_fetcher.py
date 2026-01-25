"""Direct API ticket fetcher using REST/GraphQL clients.

This module provides DirectAPIFetcher for fetching ticket data directly
from platform APIs. This is the FALLBACK path when agent-mediated
fetching is unavailable.

The fetcher uses:
- AuthenticationManager (AMI-22) for credential retrieval
- FetchPerformanceConfig (AMI-33) for timeout/retry settings
- Platform-specific handlers for API implementation
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

import httpx

from spec.config.fetch_config import FetchPerformanceConfig
from spec.integrations.fetchers.base import TicketFetcher
from spec.integrations.fetchers.exceptions import (
    AgentFetchError,
    AgentIntegrationError,
    AgentResponseParseError,
)
from spec.integrations.fetchers.handlers import (
    AzureDevOpsHandler,
    GitHubHandler,
    JiraHandler,
    LinearHandler,
    MondayHandler,
    PlatformHandler,
    TrelloHandler,
)
from spec.integrations.providers.base import Platform

if TYPE_CHECKING:
    from spec.config import ConfigManager
    from spec.integrations.auth import AuthenticationManager

logger = logging.getLogger(__name__)


class DirectAPIFetcher(TicketFetcher):
    """Fetches tickets directly from platform APIs.

    Uses AuthenticationManager for fallback credentials when agent-mediated
    fetching fails or is unavailable. Supports all 6 platforms with
    platform-specific handlers.

    Attributes:
        _auth: AuthenticationManager for credential retrieval
        _config: Optional ConfigManager for performance settings
        _timeout_seconds: Default request timeout
        _performance: FetchPerformanceConfig for retry settings
        _handlers: Lazily-created platform handlers (instance-level)
    """

    def __init__(
        self,
        auth_manager: AuthenticationManager,
        config_manager: ConfigManager | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize with AuthenticationManager.

        Args:
            auth_manager: AuthenticationManager instance (from AMI-22)
            config_manager: Optional ConfigManager for performance settings
            timeout_seconds: Optional timeout override (uses config default otherwise)
        """
        self._auth = auth_manager
        self._config = config_manager

        # Handler instances (created lazily, instance-level to avoid shared state)
        self._handlers: dict[Platform, PlatformHandler] | None = None

        # Get performance config for defaults
        if config_manager:
            self._performance = config_manager.get_fetch_performance_config()
        else:
            self._performance = FetchPerformanceConfig()

        self._timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else self._performance.timeout_seconds
        )

    @property
    def name(self) -> str:
        """Human-readable fetcher name."""
        return "Direct API Fetcher"

    def supports_platform(self, platform: Platform) -> bool:
        """Check if fallback credentials exist for this platform.

        Uses AuthenticationManager.has_fallback_configured() from AMI-22.

        Args:
            platform: Platform enum value

        Returns:
            True if fallback credentials are configured
        """
        return self._auth.has_fallback_configured(platform)

    async def fetch(
        self,
        ticket_id: str,
        platform: str,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Fetch ticket data from platform API (string-based interface).

        This is the primary public interface for TicketService integration.
        Accepts platform as a string and handles internal enum conversion.

        Args:
            ticket_id: Normalized ticket ID
            platform: Platform name string (e.g., 'jira', 'linear')
            timeout_seconds: Optional timeout override

        Returns:
            Raw API response data

        Raises:
            AgentIntegrationError: If platform string is invalid or not supported
            AgentFetchError: If API request fails
            AgentResponseParseError: If response parsing fails
        """
        platform_enum = self._resolve_platform(platform)
        return await self.fetch_raw(ticket_id, platform_enum, timeout_seconds)

    async def fetch_raw(
        self,
        ticket_id: str,
        platform: Platform,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Fetch ticket data from platform API.

        Args:
            ticket_id: Normalized ticket ID
            platform: Platform enum value
            timeout_seconds: Optional timeout override

        Returns:
            Raw API response data

        Raises:
            AgentIntegrationError: If no credentials configured for platform
            AgentFetchError: If API request fails (with retry exhaustion)
            AgentResponseParseError: If response parsing fails
        """
        # Get credentials from AuthenticationManager
        creds = self._auth.get_credentials(platform)
        if not creds.is_configured:
            raise AgentIntegrationError(
                message=creds.error_message or f"No credentials configured for {platform.name}",
                agent_name=self.name,
            )

        # Get platform-specific handler
        handler = self._get_platform_handler(platform)

        # Determine effective timeout
        effective_timeout = (
            timeout_seconds if timeout_seconds is not None else self._timeout_seconds
        )

        # Execute with retry logic
        return await self._fetch_with_retry(
            handler=handler,
            ticket_id=ticket_id,
            credentials=dict(creds.credentials),
            timeout_seconds=effective_timeout,
        )

    async def _fetch_with_retry(
        self,
        handler: PlatformHandler,
        ticket_id: str,
        credentials: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        """Execute fetch with exponential backoff retry.

        Uses FetchPerformanceConfig settings for max_retries and retry_delay.
        """
        last_error: Exception | None = None

        for attempt in range(self._performance.max_retries + 1):
            try:
                return await handler.fetch(ticket_id, credentials, timeout_seconds)
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    "Timeout fetching %s (attempt %d/%d): %s",
                    ticket_id,
                    attempt + 1,
                    self._performance.max_retries + 1,
                    e,
                )
            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise AgentFetchError(
                        message=f"API request failed: {e.response.status_code} {e.response.text}",
                        agent_name=self.name,
                        original_error=e,
                    ) from e
                last_error = e
                logger.warning(
                    "HTTP error fetching %s (attempt %d/%d): %s",
                    ticket_id,
                    attempt + 1,
                    self._performance.max_retries + 1,
                    e,
                )
            except httpx.HTTPError as e:
                last_error = e
                logger.warning(
                    "Network error fetching %s (attempt %d/%d): %s",
                    ticket_id,
                    attempt + 1,
                    self._performance.max_retries + 1,
                    e,
                )
            except ValueError as e:
                # GraphQL errors or parse errors
                raise AgentResponseParseError(
                    message=str(e),
                    agent_name=self.name,
                    original_error=e,
                ) from e

            # Calculate delay with jitter for next retry
            if attempt < self._performance.max_retries:
                delay = self._performance.retry_delay_seconds * (2**attempt)
                jitter = random.uniform(0, delay * 0.1)
                await asyncio.sleep(delay + jitter)

        # All retries exhausted
        raise AgentFetchError(
            message=f"API request failed after {self._performance.max_retries + 1} attempts",
            agent_name=self.name,
            original_error=last_error,
        )

    def _get_platform_handler(self, platform: Platform) -> PlatformHandler:
        """Get the handler for a specific platform.

        Lazily creates handlers on first access.
        """
        if self._handlers is None:
            self._handlers = {
                Platform.JIRA: JiraHandler(),
                Platform.LINEAR: LinearHandler(),
                Platform.GITHUB: GitHubHandler(),
                Platform.AZURE_DEVOPS: AzureDevOpsHandler(),
                Platform.TRELLO: TrelloHandler(),
                Platform.MONDAY: MondayHandler(),
            }

        handler = self._handlers.get(platform)
        if not handler:
            raise AgentIntegrationError(
                message=f"No handler for platform: {platform.name}",
                agent_name=self.name,
            )
        return handler

    def _resolve_platform(self, platform: str) -> Platform:
        """Resolve a platform string to Platform enum.

        Args:
            platform: Platform name as string (case-insensitive)

        Returns:
            Platform enum value

        Raises:
            AgentIntegrationError: If platform string is invalid
        """
        try:
            return Platform[platform.upper()]
        except KeyError as err:
            raise AgentIntegrationError(
                message=f"Unknown platform: {platform}",
                agent_name=self.name,
            ) from err
