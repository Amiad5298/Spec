# Implementation Plan: AMI-22 - Implement AuthenticationManager for Multi-Platform Credentials

**Ticket:** [AMI-22](https://linear.app/amiadingot/issue/AMI-22/implement-authenticationmanager-for-multi-platform-credentials)
**Status:** Draft
**Date:** 2026-01-25

---

## Summary

This ticket implements the `AuthenticationManager` class for managing **fallback credentials** used by `DirectAPIFetcher` when agent-mediated fetching is unavailable. Following the hybrid ticket fetching architecture:

1. **Primary authentication** is handled by the connected AI agent (Auggie, Claude Desktop, Cursor) via their MCP integrations
2. **Fallback credentials** (this component) provide direct API access when the agent doesn't support a platform

The `AuthenticationManager` integrates with the existing `ConfigManager` to load credentials from the configuration hierarchy (environment variables > local config > global config) and validates them against platform-specific requirements defined in `PLATFORM_REQUIRED_CREDENTIALS`.

---

## Technical Approach

### Architecture Fit

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PRIMARY: Agent-Mediated Fetch (AMI-27/AMI-30)                              │
│  • Auggie uses MCP servers with their own auth                              │
│  • User configures credentials IN THE AGENT, not in SPEC                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Agent doesn't support platform?
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FALLBACK: DirectAPIFetcher (AMI-28)                                        │
│  • Uses AuthenticationManager for credentials ← THIS TICKET                 │
│  • Makes direct REST/GraphQL API calls                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ get_credentials()
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  AuthenticationManager                                                       │
│  ├─ ConfigManager (loads credentials from config hierarchy)                 │
│  ├─ PLATFORM_REQUIRED_CREDENTIALS (from fetch_config.py)                    │
│  ├─ CREDENTIAL_ALIASES (from fetch_config.py)                               │
│  └─ Environment variable expansion (from env_utils.py)                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integration with Existing Components

| Component | Location | Integration |
|-----------|----------|-------------|
| `ConfigManager` | `ingot/config/manager.py` | Injected via constructor; provides `get_fallback_credentials()` |
| `PLATFORM_REQUIRED_CREDENTIALS` | `ingot/config/fetch_config.py` | Defines required fields per platform |
| `CREDENTIAL_ALIASES` | `ingot/config/fetch_config.py` | Credential key normalization |
| `Platform` enum | `ingot/integrations/providers/base.py` | Platform identification |
| `AuthenticationError` | `ingot/integrations/providers/exceptions.py` | For credential validation failures |
| `expand_env_vars` | `ingot/utils/env_utils.py` | Environment variable expansion |

### Key Design Decisions

1. **Delegate to ConfigManager** - Uses existing `get_fallback_credentials()` instead of duplicating config loading logic
2. **Dataclass for Results** - `PlatformCredentials` provides structured response with error context
3. **Lazy Validation** - Credentials are validated only when `get_credentials()` is called (not at startup)
4. **Secure Logging** - Never logs credential values; uses `is_sensitive_key()` for safe logging

---

## Components to Create

### New File: `ingot/integrations/auth.py`

| Component | Purpose |
|-----------|---------|
| `PlatformCredentials` dataclass | Structured credential response with platform, is_configured, credentials dict, error_message |
| `AuthenticationManager` class | Main class for fallback credential management |

### Modified Files

| File | Changes |
|------|---------|
| `ingot/integrations/__init__.py` | Export `AuthenticationManager`, `PlatformCredentials` |

---

## Implementation Steps

### Step 1: Create Auth Module with PlatformCredentials Dataclass
**File:** `ingot/integrations/auth.py`

```python
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
    from ingot.config.manager import ConfigManager

from ingot.integrations.providers.base import Platform

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
```

### Step 2: Implement AuthenticationManager Class
**File:** `ingot/integrations/auth.py` (continued)

```python
class AuthenticationManager:
    """Manage fallback credentials for direct API access.

    Primary auth is handled by the connected AI agent's MCP integrations.
    This class provides credentials only when DirectAPIFetcher is used
    as a fallback for platforms not supported by the agent.

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
        return [
            platform
            for platform in Platform
            if self.has_fallback_configured(platform)
        ]

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
```

### Step 3: Update Package Exports
**File:** `ingot/integrations/__init__.py`

Add exports for the new auth module:

```python
from ingot.integrations.auth import (
    AuthenticationManager,
    PlatformCredentials,
)

__all__ = [
    # ... existing exports ...
    # Authentication
    "AuthenticationManager",
    "PlatformCredentials",
]
```

### Step 4: Add Unit Tests
**File:** `tests/test_auth_manager.py`

Create comprehensive tests with mocked ConfigManager.

---

## File Changes Detail

### New: `ingot/integrations/auth.py`

Complete module with:
- Module docstring explaining FALLBACK-only purpose
- `PlatformCredentials` frozen dataclass
- `AuthenticationManager` class with:
  - `PLATFORM_NAMES` mapping for Platform enum to config keys
  - `__init__(config: ConfigManager)`
  - `get_credentials(platform: Platform) -> PlatformCredentials`
  - `has_fallback_configured(platform: Platform) -> bool`
  - `list_fallback_platforms() -> list[Platform]`
  - `validate_credentials(platform: Platform) -> tuple[bool, str]`

### Modified: `ingot/integrations/__init__.py`

Add imports and exports:

```python
from ingot.integrations.auth import (
    AuthenticationManager,
    PlatformCredentials,
)

# Add to __all__
"AuthenticationManager",
"PlatformCredentials",
```

---

## Testing Strategy

### Unit Tests (`tests/test_auth_manager.py`)

1. **Initialization Tests**
   - `test_init_with_config_manager` - Accepts ConfigManager
   - `test_platform_names_mapping` - All Platform values have mappings

2. **get_credentials() Tests**
   - `test_get_credentials_success` - Returns configured credentials
   - `test_get_credentials_not_configured` - Returns error when no credentials
   - `test_get_credentials_missing_env_var` - Returns error for unexpanded ${VAR}
   - `test_get_credentials_missing_required_fields` - Returns error for incomplete config
   - `test_get_credentials_unknown_platform` - Handles unknown platform gracefully
   - `test_get_credentials_with_aliases` - Credential aliases are normalized

3. **has_fallback_configured() Tests**
   - `test_has_fallback_configured_true` - Returns True when configured
   - `test_has_fallback_configured_false` - Returns False when not configured

4. **list_fallback_platforms() Tests**
   - `test_list_fallback_platforms_empty` - Returns empty list when no credentials
   - `test_list_fallback_platforms_multiple` - Returns all configured platforms
   - `test_list_fallback_platforms_partial` - Returns only configured platforms

5. **validate_credentials() Tests**
   - `test_validate_credentials_success` - Returns (True, message) for valid credentials
   - `test_validate_credentials_failure` - Returns (False, error) for invalid

### Mock Strategy

```python
import pytest
from unittest.mock import MagicMock

from ingot.config import ConfigManager, ConfigValidationError
from ingot.integrations.auth import AuthenticationManager, PlatformCredentials
from ingot.integrations.providers.base import Platform


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    config = MagicMock(spec=ConfigManager)
    # Default: no credentials configured
    config.get_fallback_credentials.return_value = None
    return config


@pytest.fixture
def config_with_jira_creds(mock_config_manager):
    """ConfigManager with Jira credentials configured."""
    mock_config_manager.get_fallback_credentials.side_effect = lambda p, **kw: (
        {"url": "https://company.atlassian.net", "email": "user@example.com", "token": "abc123"}
        if p == "jira" else None
    )
    return mock_config_manager
```

---

## Dependencies

### Upstream Dependencies (Must Exist Before Implementation)

| Component | Status | Location |
|-----------|--------|----------|
| `ConfigManager.get_fallback_credentials()` | ✅ Implemented (AMI-33) | `ingot/config/manager.py` |
| `PLATFORM_REQUIRED_CREDENTIALS` | ✅ Implemented (AMI-33) | `ingot/config/fetch_config.py` |
| `CREDENTIAL_ALIASES` | ✅ Implemented (AMI-33) | `ingot/config/fetch_config.py` |
| `validate_credentials()` | ✅ Implemented (AMI-33) | `ingot/config/fetch_config.py` |
| `Platform` enum | ✅ Implemented (AMI-16) | `ingot/integrations/providers/base.py` |

### Downstream Dependents (Will Use This After Implementation)

| Component | Ticket | Usage |
|-----------|--------|-------|
| `DirectAPIFetcher` | AMI-28 | Uses `get_credentials()` for API authentication |
| `TicketService` | AMI-32 | May check `has_fallback_configured()` for strategy selection |

---

## Acceptance Criteria Checklist

From the Linear ticket:

- [ ] `PlatformCredentials` dataclass properly structured
- [ ] `get_credentials()` returns fallback credentials for platform
- [ ] `has_fallback_configured()` checks if fallback is available
- [ ] `list_fallback_platforms()` returns platforms with fallback configured
- [ ] Supports environment variable expansion in config
- [ ] Secure handling (no logging of sensitive values)
- [ ] Integrates with existing `ConfigManager`
- [ ] Unit tests with mock config
- [ ] Clear documentation that this is FALLBACK only

---

## Security Considerations

1. **Never log credential values** - Use `logger.debug()` for error context only
2. **Secure comparison** - Future API validation should use constant-time comparison
3. **Environment variable expansion** - Delegates to `expand_env_vars()` with strict mode
4. **Frozen dataclass** - `PlatformCredentials` is immutable to prevent accidental modification

---

## Documentation Requirements

During implementation, ensure the following documentation is included in docstrings:

### 1. Canonical Credential Key Names

The `PlatformCredentials.credentials` dictionary returns **canonical key names**, not the config file key names. Document this in the `AuthenticationManager` class docstring:

| Platform | Config Keys | Canonical Keys Returned |
|----------|-------------|------------------------|
| Jira | `FALLBACK_JIRA_URL`, `FALLBACK_JIRA_EMAIL`, `FALLBACK_JIRA_TOKEN` | `url`, `email`, `token` |
| GitHub | `FALLBACK_GITHUB_TOKEN` | `token` |
| Linear | `FALLBACK_LINEAR_API_KEY` | `api_key` |
| Azure DevOps | `FALLBACK_AZURE_DEVOPS_ORGANIZATION`, `FALLBACK_AZURE_DEVOPS_PAT` | `organization`, `pat` |
| Monday | `FALLBACK_MONDAY_API_KEY` | `api_key` |
| Trello | `FALLBACK_TRELLO_API_KEY`, `FALLBACK_TRELLO_TOKEN` | `api_key`, `token` |

### 2. Credential Alias Resolution

Document in the `AuthenticationManager` class docstring that credential aliases are automatically resolved by `ConfigManager.get_fallback_credentials()`:

```python
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

        See CREDENTIAL_ALIASES in ingot/config/fetch_config.py for full mapping.
    """
```

### 3. validate_credentials() Docstring Clarity

The `validate_credentials()` method must have a clear docstring explaining it performs FORMAT validation only (already updated in Step 2 implementation code above).

---

## Usage Examples

### Basic Usage

```python
from ingot.config import ConfigManager
from ingot.integrations.auth import AuthenticationManager, PlatformCredentials
from ingot.integrations.providers.base import Platform

# Initialize
config = ConfigManager()
config.load()
auth_manager = AuthenticationManager(config)

# Get credentials for a platform
creds = auth_manager.get_credentials(Platform.AZURE_DEVOPS)
if creds.is_configured:
    # Use credentials for direct API access
    organization = creds.credentials["organization"]
    pat = creds.credentials["pat"]
else:
    print(f"Fallback not available: {creds.error_message}")
```

### With DirectAPIFetcher (AMI-28)

```python
class DirectAPIFetcher(TicketFetcher):
    """Fetches tickets via direct REST/GraphQL API calls."""

    def __init__(
        self,
        auth_manager: AuthenticationManager,
        config_manager: ConfigManager | None = None,
    ) -> None:
        self._auth = auth_manager
        self._config = config_manager

    async def fetch_raw(self, ticket_id: str, platform: Platform) -> dict[str, Any]:
        creds = self._auth.get_credentials(platform)
        if not creds.is_configured:
            raise AuthenticationError(
                message=creds.error_message or "Credentials not configured",
                platform=platform.name,
            )

        # Make direct API call with credentials
        if platform == Platform.JIRA:
            return await self._fetch_jira(ticket_id, creds.credentials)
        elif platform == Platform.AZURE_DEVOPS:
            return await self._fetch_azure_devops(ticket_id, creds.credentials)
        # ... etc
```

### Checking Available Fallbacks

```python
# List all platforms with fallback credentials
available = auth_manager.list_fallback_platforms()
print(f"Fallback available for: {[p.name for p in available]}")

# Check specific platform
if auth_manager.has_fallback_configured(Platform.TRELLO):
    print("Trello fallback is configured")
```

### Credential Validation

```python
# Validate before use
success, message = auth_manager.validate_credentials(Platform.LINEAR)
if success:
    print(f"✓ {message}")
else:
    print(f"✗ {message}")
```

---

## Configuration Reference

### Config Keys per Platform (from AMI-22 ticket)

These are the config file keys and the **canonical keys** returned in `PlatformCredentials.credentials`:

| Platform | Config File Keys | Canonical Keys Returned |
|----------|------------------|------------------------|
| Jira | `FALLBACK_JIRA_URL`, `FALLBACK_JIRA_EMAIL`, `FALLBACK_JIRA_TOKEN` | `url`, `email`, `token` |
| GitHub | `FALLBACK_GITHUB_TOKEN` | `token` |
| Linear | `FALLBACK_LINEAR_API_KEY` | `api_key` |
| Azure DevOps | `FALLBACK_AZURE_DEVOPS_ORGANIZATION`, `FALLBACK_AZURE_DEVOPS_PAT` | `organization`, `pat` |
| Monday | `FALLBACK_MONDAY_API_KEY` | `api_key` |
| Trello | `FALLBACK_TRELLO_API_KEY`, `FALLBACK_TRELLO_TOKEN` | `api_key`, `token` |

> **Note:** Azure DevOps `project` is NOT a credential - it is derived from the ticket ID format (e.g., `MyProject/_workitems/edit/123`). Only `organization` and `pat` are needed for API authentication.

### Credential Key Transformation

Config file keys are automatically transformed to canonical keys:
- `FALLBACK_JIRA_URL` → `url`
- `FALLBACK_AZURE_DEVOPS_ORGANIZATION` → `organization`

Additionally, common aliases are resolved via `CREDENTIAL_ALIASES`:
- `org` → `organization` (Azure DevOps)
- `base_url` → `url` (Jira)
- `api_token` → `token` (Trello)

### Example Configuration

```bash
# ~/.ingot-config or .ingot

# Fallback credentials (only used when agent doesn't support platform)
FALLBACK_AZURE_DEVOPS_ORGANIZATION=myorg
FALLBACK_AZURE_DEVOPS_PAT=${AZURE_DEVOPS_PAT}

FALLBACK_TRELLO_API_KEY=${TRELLO_API_KEY}
FALLBACK_TRELLO_TOKEN=${TRELLO_API_TOKEN}

# NOTE: Jira, GitHub, Linear credentials typically NOT needed
# because Auggie/Claude Desktop handle these via MCP
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Configuration Sources                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  Environment Variables   ────────────────────────────────────> Highest      │
│  Local Config (.ingot)    ──────────────────────────────────>                │
│  Global Config (~/.ingot-config) ───────────────────────────>                │
│  Built-in Defaults       ────────────────────────────────────> Lowest       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ConfigManager                                     │
│  ├─ get_fallback_credentials(platform, strict, validate)                    │
│  └─ _expand_env_vars() ─────────────────────────────> expand_env_vars()     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AuthenticationManager                                │
│  ├─ get_credentials(platform) ──────────────────────> PlatformCredentials   │
│  ├─ has_fallback_configured(platform) ──────────────> bool                  │
│  ├─ list_fallback_platforms() ──────────────────────> list[Platform]        │
│  └─ validate_credentials(platform) ─────────────────> tuple[bool, str]      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DirectAPIFetcher (AMI-28)                            │
│  Uses AuthenticationManager to get credentials for direct API calls         │
└─────────────────────────────────────────────────────────────────────────────┘
```
