"""Base classes for ticket fetching strategies.

This module defines:
- TicketFetcher: Abstract base class for all ticket fetchers
- AgentMediatedFetcher: Base class for fetchers that use AI agent integrations

The fetcher abstraction separates HOW to fetch data (fetching strategy) from
HOW to normalize data (provider responsibility), enabling flexible ticket
retrieval from multiple sources.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from spec.integrations.providers.base import Platform

from .exceptions import AgentIntegrationError, PlatformNotSupportedError

logger = logging.getLogger(__name__)

# Regex pattern to extract JSON from markdown code blocks
# Matches ```json ... ``` or ``` ... ``` with optional language hint
_CODE_BLOCK_PATTERN = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?```",
    re.DOTALL | re.IGNORECASE,
)


class TicketFetcher(ABC):
    """Abstract base class for ticket fetching strategies.

    Defines the contract for all ticket fetchers. Implementations can use
    different strategies such as agent-mediated fetching (via MCP) or
    direct API calls.

    All fetchers return raw dict data - normalization to GenericTicket
    is handled by IssueTrackerProvider implementations.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable fetcher name.

        Returns:
            Display name like 'Auggie MCP Fetcher', 'Direct API Fetcher', etc.
        """
        pass

    @abstractmethod
    def supports_platform(self, platform: Platform) -> bool:
        """Check if this fetcher supports the given platform.

        Args:
            platform: The platform to check support for

        Returns:
            True if this fetcher can fetch tickets from the platform
        """
        pass

    @abstractmethod
    async def fetch_raw(self, ticket_id: str, platform: Platform) -> dict[str, Any]:
        """Fetch raw ticket data from the platform.

        This is the primary method for retrieving ticket information.
        Returns raw platform API response data as a dictionary.

        Args:
            ticket_id: The ticket identifier (e.g., 'PROJ-123', 'owner/repo#42')
            platform: The platform to fetch from

        Returns:
            Raw ticket data as returned by the platform API

        Raises:
            PlatformNotSupportedError: If this fetcher doesn't support the platform
            TicketFetchError: If fetching fails for any reason
        """
        pass


class AgentMediatedFetcher(TicketFetcher):
    """Base class for fetchers that use AI agent integrations.

    This class provides common functionality for fetching tickets through
    AI agents that have MCP (Model Context Protocol) integrations with
    issue tracking platforms.

    Subclasses must implement:
    - _execute_fetch_prompt(): Send prompt to agent and get response
    - _get_prompt_template(): Return platform-specific prompt template
    - supports_platform(): Check if platform is supported
    - name: Human-readable fetcher name
    """

    @abstractmethod
    async def _execute_fetch_prompt(self, prompt: str, platform: Platform) -> str:
        """Execute the fetch prompt through the agent.

        Subclasses implement this to send the prompt to their specific
        agent integration and return the raw response.

        Args:
            prompt: The structured prompt to send to the agent
            platform: The target platform (for context/tool selection)

        Returns:
            Raw string response from the agent

        Raises:
            AgentIntegrationError: If agent communication fails
        """
        pass

    @abstractmethod
    def _get_prompt_template(self, platform: Platform) -> str:
        """Get the prompt template for the given platform.

        Returns a format string with {ticket_id} placeholder.

        Args:
            platform: The platform to get template for

        Returns:
            Prompt template string with {ticket_id} placeholder
        """
        pass

    async def fetch_raw(self, ticket_id: str, platform: Platform) -> dict[str, Any]:
        """Fetch raw ticket data using agent-mediated approach.

        Builds a structured prompt, sends it to the agent, and parses
        the JSON response.

        Args:
            ticket_id: The ticket identifier
            platform: The platform to fetch from

        Returns:
            Raw ticket data as a dictionary

        Raises:
            PlatformNotSupportedError: If platform is not supported
            AgentIntegrationError: If agent communication or parsing fails
        """
        if not self.supports_platform(platform):
            raise PlatformNotSupportedError(
                platform=platform.name,
                fetcher_name=self.name,
            )

        prompt = self._build_prompt(ticket_id, platform)
        response = await self._execute_fetch_prompt(prompt, platform)
        return self._parse_response(response)

    def _build_prompt(self, ticket_id: str, platform: Platform) -> str:
        """Build the fetch prompt for the given ticket.

        Uses the platform-specific template and formats it with
        the ticket ID.

        Args:
            ticket_id: The ticket identifier
            platform: The target platform

        Returns:
            Formatted prompt string ready to send to agent
        """
        template = self._get_prompt_template(platform)
        return template.format(ticket_id=ticket_id)

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse agent response and extract JSON data.

        Handles multiple response formats:
        - Bare JSON object: {"key": "value"}
        - Markdown code block: ```json\n{...}\n```
        - Markdown without language hint: ```\n{...}\n```

        Args:
            response: Raw string response from agent

        Returns:
            Parsed JSON as a dictionary

        Raises:
            AgentIntegrationError: If response cannot be parsed as JSON
        """
        if not response or not response.strip():
            raise AgentIntegrationError(
                message="Empty response received from agent",
                agent_name=self.name,
            )

        # Try to extract JSON from markdown code blocks first
        code_block_match = _CODE_BLOCK_PATTERN.search(response)
        if code_block_match:
            json_str = code_block_match.group(1).strip()
            logger.debug("Extracted JSON from markdown code block")
        else:
            # Try bare JSON - find first { and last }
            json_str = response.strip()

        try:
            result = json.loads(json_str)
            if not isinstance(result, dict):
                raise AgentIntegrationError(
                    message=f"Expected JSON object, got {type(result).__name__}",
                    agent_name=self.name,
                )
            return result
        except json.JSONDecodeError as e:
            logger.debug(
                "Initial JSON parse failed: %s. Attempting fallback extraction.",
                e,
            )
            # Try to find JSON object in the response
            # Look for first { and last } to handle text before/after JSON
            start_idx = response.find("{")
            end_idx = response.rfind("}")
            if start_idx != -1 and end_idx > start_idx:
                try:
                    json_str = response[start_idx : end_idx + 1]
                    result = json.loads(json_str)
                    if isinstance(result, dict):
                        logger.debug(
                            "Fallback extraction succeeded: found JSON at positions %d-%d",
                            start_idx,
                            end_idx,
                        )
                        return result
                except json.JSONDecodeError:
                    logger.debug(
                        "Fallback extraction also failed for substring at %d-%d",
                        start_idx,
                        end_idx,
                    )
                    pass

            raise AgentIntegrationError(
                message=f"Failed to parse JSON from agent response: {e}",
                agent_name=self.name,
                original_error=e,
            ) from e
