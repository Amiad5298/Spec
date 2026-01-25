"""Trello REST API handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler


class TrelloHandler(PlatformHandler):
    """Handler for Trello REST API.

    Credential keys (from AuthenticationManager):
        - api_key: Trello API key
        - token: Trello token

    Ticket ID: Trello card ID or shortLink
    """

    API_URL = "https://api.trello.com/1"

    @property
    def platform_name(self) -> str:
        return "Trello"

    @property
    def required_credential_keys(self) -> frozenset[str]:
        return frozenset({"api_key", "token"})

    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch card from Trello REST API.

        API endpoint: GET /1/cards/{id}
        """
        # Validate required credentials are present
        self._validate_credentials(credentials)

        api_key = credentials["api_key"]
        token = credentials["token"]

        endpoint = f"{self.API_URL}/cards/{ticket_id}"
        params = {"key": api_key, "token": token}

        # Use injected client or create new one
        if http_client is not None:
            response = await http_client.get(endpoint, params=params)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        else:
            async with self._get_http_client(timeout_seconds) as client:
                response = await client.get(endpoint, params=params)
                response.raise_for_status()
                result = response.json()
                return result
