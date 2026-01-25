"""Authentication management for fallback credentials.

This module provides AuthenticationManager for managing fallback credentials
used by DirectAPIFetcher when agent-mediated fetching is unavailable.

IMPORTANT: This is for FALLBACK credentials only. Primary authentication
is handled by the connected AI agent's MCP integrations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec.config.manager import ConfigManager

from spec.integrations.providers.base import Platform

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlatformCredentials:
    """Credentials for a specific platform.

    Attributes:
        platform: The platform these credentials are for
        is_configured: Whether valid credentials are available
        credentials: Dictionary of credential key-value pairs (empty if not configured)
        error_message: Description of why credentials are unavailable (if not configured)
    """

    platform: Platform
    is_configured: bool
    credentials: dict[str, str]
    error_message: str | None = None


class AuthenticationManager:
    """Manage fallback credentials for direct API access.

    Primary auth is handled by the connected AI agent's MCP integrations.
    This class provides credentials only when DirectAPIFetcher is used
    as a fallback for platforms not supported by the agent.

    Credential Key Transformation:
        Config file keys (e.g., FALLBACK_JIRA_URL) are automatically
        transformed to canonical keys (e.g., 'url') by ConfigManager.

        Common aliases are also resolved:
        - 'org' → 'organization' (Azure DevOps)
        - 'base_url' → 'url' (Jira)
        - 'api_token' → 'token' (Trello)

        See CREDENTIAL_ALIASES in spec/config/fetch_config.py for full mapping.

    Canonical Keys Returned per Platform:
        - Jira: url, email, token
        - GitHub: token
        - Linear: api_key
        - Azure DevOps: organization, pat
        - Monday: api_key
        - Trello: api_key, token

    Attributes:
        _config: ConfigManager instance for loading credentials
    """

    # Map Platform enum to credential requirement keys
    # Uses lowercase platform names to match PLATFORM_REQUIRED_CREDENTIALS
    PLATFORM_NAMES: dict[Platform, str] = {
        Platform.JIRA: "jira",
        Platform.GITHUB: "github",
        Platform.LINEAR: "linear",
        Platform.AZURE_DEVOPS: "azure_devops",
        Platform.MONDAY: "monday",
        Platform.TRELLO: "trello",
    }

    def __init__(self, config: ConfigManager) -> None:
        """Initialize with ConfigManager.

        Args:
            config: ConfigManager instance (should have load() called)
        """
        self._config = config

    def get_credentials(self, platform: Platform) -> PlatformCredentials:
        """Get fallback credentials for direct API access.

        Retrieves and validates credentials for the specified platform
        from the configuration hierarchy.

        Args:
            platform: Platform enum value to get credentials for

        Returns:
            PlatformCredentials with credentials if available, or error_message if not
        """
        platform_name = self.PLATFORM_NAMES.get(platform)
        if platform_name is None:
            return PlatformCredentials(
                platform=platform,
                is_configured=False,
                credentials={},
                error_message=f"Unknown platform: {platform}",
            )

        try:
            credentials = self._config.get_fallback_credentials(
                platform_name,
                strict=True,  # Fail on missing env vars
                validate=True,  # Validate required fields
            )
        except Exception as e:
            logger.debug(f"Failed to get credentials for {platform_name}: {e}")
            return PlatformCredentials(
                platform=platform,
                is_configured=False,
                credentials={},
                error_message=str(e),
            )

        if credentials is None:
            return PlatformCredentials(
                platform=platform,
                is_configured=False,
                credentials={},
                error_message=f"No fallback credentials configured for {platform_name}",
            )

        return PlatformCredentials(
            platform=platform,
            is_configured=True,
            credentials=credentials,
            error_message=None,
        )

    def has_fallback_configured(self, platform: Platform) -> bool:
        """Check if fallback credentials are available for a platform.

        Convenience method for quick availability check without full validation.

        Args:
            platform: Platform to check

        Returns:
            True if credentials are configured and valid
        """
        return self.get_credentials(platform).is_configured

    def list_fallback_platforms(self) -> list[Platform]:
        """List platforms with fallback credentials configured.

        Returns:
            List of Platform enum values that have valid fallback credentials
        """
        return [platform for platform in Platform if self.has_fallback_configured(platform)]

    def validate_credentials(self, platform: Platform) -> tuple[bool, str]:
        """Validate that required credential fields are present and non-empty.

        NOTE: This performs FORMAT validation only. It checks that:
        - All required fields for the platform are present
        - No required fields are empty strings

        This method does NOT:
        - Make API calls to verify credentials are valid
        - Test network connectivity to the platform
        - Validate token expiration or permissions

        For API connectivity testing, use DirectAPIFetcher which makes
        actual API calls and will surface authentication errors.

        Args:
            platform: Platform to validate credentials for

        Returns:
            Tuple of (success: bool, message: str)
            - (True, "Credentials configured for {platform}") if valid
            - (False, error_message) if validation fails
        """
        creds = self.get_credentials(platform)

        if not creds.is_configured:
            return False, creds.error_message or "Credentials not configured"

        # Basic validation passed (required fields present)
        return True, f"Credentials configured for {platform.name}"
