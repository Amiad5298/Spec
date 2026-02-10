"""Ticket fetchers package.

This package provides the fetcher abstraction layer for retrieving
raw ticket data from various issue tracking platforms.

The fetcher layer separates HOW to fetch data (fetching strategy) from
HOW to normalize data (provider responsibility).

Classes:
    TicketFetcher: Abstract base class for all fetchers
    AgentMediatedFetcher: Base class for AI agent-mediated fetching
    AuggieMediatedFetcher: Fetcher using Auggie's MCP integrations
    DirectAPIFetcher: Fallback fetcher using direct REST/GraphQL API calls

Exceptions:
    TicketFetchError: Base exception for fetch failures
    PlatformNotSupportedError: Fetcher doesn't support requested platform
    AgentIntegrationError: Agent integration/configuration failure
    AgentFetchError: Tool execution failed during fetch
    AgentResponseParseError: JSON output was malformed
"""

from ingot.integrations.fetchers.auggie_fetcher import AuggieMediatedFetcher
from ingot.integrations.fetchers.base import (
    DEFAULT_TIMEOUT_SECONDS,
    AgentMediatedFetcher,
    TicketFetcher,
)
from ingot.integrations.fetchers.claude_fetcher import ClaudeMediatedFetcher
from ingot.integrations.fetchers.cursor_fetcher import CursorMediatedFetcher
from ingot.integrations.fetchers.direct_api_fetcher import DirectAPIFetcher
from ingot.integrations.fetchers.exceptions import (
    AgentFetchError,
    AgentIntegrationError,
    AgentResponseParseError,
    PlatformNotSupportedError,
    TicketFetchError,
)

__all__ = [
    # Base classes
    "TicketFetcher",
    "AgentMediatedFetcher",
    "DEFAULT_TIMEOUT_SECONDS",
    # Concrete fetchers
    "AuggieMediatedFetcher",
    "ClaudeMediatedFetcher",
    "CursorMediatedFetcher",
    "DirectAPIFetcher",
    # Exceptions
    "TicketFetchError",
    "PlatformNotSupportedError",
    "AgentIntegrationError",
    "AgentFetchError",
    "AgentResponseParseError",
]
