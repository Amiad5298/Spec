"""Azure DevOps REST API handler."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any

import httpx

from .base import PlatformHandler


class AzureDevOpsHandler(PlatformHandler):
    """Handler for Azure DevOps REST API.

    Credential keys (from AuthenticationManager):
        - organization: Azure DevOps organization name
        - pat: Personal Access Token

    Ticket ID format: "ProjectName/WorkItemID" (e.g., "MyProject/12345")
    """

    @property
    def platform_name(self) -> str:
        return "Azure DevOps"

    @property
    def required_credential_keys(self) -> frozenset[str]:
        return frozenset({"organization", "pat"})

    def _parse_ticket_id(self, ticket_id: str) -> tuple[str, int]:
        """Parse 'Project/ID' format.

        Returns:
            Tuple of (project, work_item_id)
        """
        parts = ticket_id.split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            raise ValueError(f"Invalid Azure DevOps ticket format: {ticket_id}")
        return parts[0], int(parts[1])

    async def fetch(
        self,
        ticket_id: str,
        credentials: Mapping[str, str],
        timeout_seconds: float | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """Fetch work item from Azure DevOps REST API.

        API endpoint: GET /{organization}/{project}/_apis/wit/workitems/{id}
        """
        # Validate required credentials are present
        self._validate_credentials(credentials)

        project, work_item_id = self._parse_ticket_id(ticket_id)
        organization = credentials["organization"]
        pat = credentials["pat"]

        # Azure DevOps uses Basic auth with PAT as password
        auth_bytes = base64.b64encode(f":{pat}".encode()).decode()

        endpoint = (
            f"https://dev.azure.com/{organization}/{project}/"
            f"_apis/wit/workitems/{work_item_id}?api-version=7.0"
        )
        headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Accept": "application/json",
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
