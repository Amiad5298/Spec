"""Claude Code CLI-mediated ticket fetcher using MCP integrations.

This module provides the ClaudeMediatedFetcher class that fetches
ticket data through the Claude Code CLI's MCP tool integrations for
Jira, Linear, and GitHub.

ClaudeMediatedFetcher inherits all behaviour from AgentMediatedFetcher.
Only the `name` property is overridden; everything else (platform support,
prompt building, timeout handling, response parsing) lives in the base class.
"""

from __future__ import annotations

from ingot.integrations.fetchers.base import DEFAULT_TIMEOUT_SECONDS, AgentMediatedFetcher


class ClaudeMediatedFetcher(AgentMediatedFetcher):
    """Fetches tickets through Claude Code CLI's MCP integrations.

    Inherits all behaviour from AgentMediatedFetcher. This subclass
    exists only to provide the fetcher name.
    """

    @property
    def name(self) -> str:
        """Human-readable fetcher name."""
        return "Claude MCP Fetcher"


__all__ = [
    "ClaudeMediatedFetcher",
    "DEFAULT_TIMEOUT_SECONDS",
]
