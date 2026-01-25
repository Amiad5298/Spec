"""Monday.com GraphQL API handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler

ITEM_QUERY = """
query GetItem($itemId: ID!) {
  items(ids: [$itemId]) {
    id
    name
    state
    column_values {
      id
      title
      text
    }
    created_at
    updated_at
    board { id name }
    group { id title }
  }
}
"""


class MondayHandler(PlatformHandler):
    """Handler for Monday.com GraphQL API.

    Credential keys (from AuthenticationManager):
        - api_key: Monday API key

    Ticket ID: Monday item ID (numeric)
    """

    API_URL = "https://api.monday.com/v2"

    @property
    def platform_name(self) -> str:
        return "Monday"

    @property
    def required_credential_keys(self) -> frozenset[str]:
        return frozenset({"api_key"})

    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch item from Monday GraphQL API."""
        # Validate required credentials are present
        self._validate_credentials(credentials)

        api_key = credentials["api_key"]
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "query": ITEM_QUERY,
            "variables": {"itemId": ticket_id},
        }

        # Use injected client or create new one
        if http_client is not None:
            response = await http_client.post(
                self.API_URL,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        else:
            async with self._get_http_client(timeout_seconds) as client:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")

        items = data.get("data", {}).get("items", [])
        if not items:
            raise ValueError(f"Item not found: {ticket_id}")
        result: dict[str, Any] = items[0]
        return result
