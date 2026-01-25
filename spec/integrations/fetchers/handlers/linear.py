"""Linear GraphQL API handler."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler

# Use issueByIdentifier for team-scoped identifiers (e.g., "AMI-31")
# NOT issue(id:) which requires a UUID
ISSUE_QUERY = """
query GetIssue($identifier: String!) {
  issueByIdentifier(identifier: $identifier) {
    id
    identifier
    title
    description
    state { name }
    assignee { name email }
    labels { nodes { name } }
    createdAt
    updatedAt
    priority
    team { key name }
    url
  }
}
"""


class LinearHandler(PlatformHandler):
    """Handler for Linear GraphQL API.

    Credential keys (from AuthenticationManager):
        - api_key: Linear API key

    Ticket ID format: Team-scoped identifier (e.g., "AMI-31", "PROJ-123")
    """

    API_URL = "https://api.linear.app/graphql"

    @property
    def platform_name(self) -> str:
        return "Linear"

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
        """Fetch issue from Linear GraphQL API.

        Uses issueByIdentifier query for team-scoped identifiers.
        """
        # Validate required credentials are present
        self._validate_credentials(credentials)

        api_key = credentials["api_key"]
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "query": ISSUE_QUERY,
            "variables": {"identifier": ticket_id},
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

        # Extract issue from GraphQL response
        if "errors" in data:
            raise ValueError(f"GraphQL errors: {data['errors']}")

        issue = data.get("data", {}).get("issueByIdentifier")
        if issue is None:
            raise ValueError(f"Issue not found: {ticket_id}")
        result: dict[str, Any] = issue
        return result
