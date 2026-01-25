"""GitHub REST API handler."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler


class GitHubHandler(PlatformHandler):
    """Handler for GitHub REST API v3.

    Credential keys (from AuthenticationManager):
        - token: GitHub personal access token

    Ticket ID format: "owner/repo#number" (e.g., "microsoft/vscode#12345")
    """

    API_URL = "https://api.github.com"

    @property
    def platform_name(self) -> str:
        return "GitHub"

    @property
    def required_credential_keys(self) -> frozenset[str]:
        return frozenset({"token"})

    def _parse_ticket_id(self, ticket_id: str) -> tuple[str, str, int]:
        """Parse 'owner/repo#number' format.

        Returns:
            Tuple of (owner, repo, issue_number)
        """
        match = re.match(r"^([^/]+)/([^#]+)#(\d+)$", ticket_id)
        if not match:
            raise ValueError(f"Invalid GitHub ticket format: {ticket_id}")
        return match.group(1), match.group(2), int(match.group(3))

    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch issue/PR from GitHub REST API.

        API endpoint: GET /repos/{owner}/{repo}/issues/{issue_number}
        """
        # Validate required credentials are present
        self._validate_credentials(credentials)

        owner, repo, number = self._parse_ticket_id(ticket_id)
        token = credentials["token"]

        endpoint = f"{self.API_URL}/repos/{owner}/{repo}/issues/{number}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # Use injected client or create new one
        if http_client is not None:
            response = await http_client.get(endpoint, headers=headers)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        else:
            async with self._get_http_client(timeout_seconds) as client:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                result = response.json()
                return result
