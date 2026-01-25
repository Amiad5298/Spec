"""Jira REST API handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler


class JiraHandler(PlatformHandler):
    """Handler for Jira REST API v3.

    Credential keys (from AuthenticationManager):
        - url: Jira instance URL (e.g., https://company.atlassian.net)
        - email: User email for authentication
        - token: API token
    """

    @property
    def platform_name(self) -> str:
        return "Jira"

    @property
    def required_credential_keys(self) -> frozenset[str]:
        return frozenset({"url", "email", "token"})

    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch issue from Jira REST API.

        API endpoint: GET /rest/api/3/issue/{issueIdOrKey}
        """
        # Validate required credentials are present
        self._validate_credentials(credentials)

        url = credentials["url"].rstrip("/")
        email = credentials["email"]
        token = credentials["token"]

        endpoint = f"{url}/rest/api/3/issue/{ticket_id}"

        # Use injected client or create new one
        if http_client is not None:
            response = await http_client.get(
                endpoint,
                auth=(email, token),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        else:
            async with self._get_http_client(timeout_seconds) as client:
                response = await client.get(
                    endpoint,
                    auth=(email, token),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
                return result
