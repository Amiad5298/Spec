# Implementation Plan: AMI-18 - Implement JiraProvider Concrete Class

**Ticket:** [AMI-18](https://linear.app/amiadspec/issue/AMI-18/implement-jiraprovider-concrete-class)
**Status:** Draft
**Date:** 2026-01-25

---

## Summary

This ticket implements the `JiraProvider` concrete class that extends `IssueTrackerProvider` for Jira integration. Following the hybrid ticket fetching architecture, this provider focuses on **input parsing and data normalization**, not direct API calls. The actual data fetching is delegated to `TicketFetcher` implementations (`AuggieMediatedFetcher` as primary, `DirectAPIFetcher` as fallback).

The provider is responsible for:
1. **Input parsing** - Recognizing Jira URLs and `PROJECT-123` format IDs
2. **Data normalization** - Converting raw Jira API/agent responses to `GenericTicket`
3. **Status/type mapping** - Mapping Jira-specific values to normalized enums
4. **Structured prompt templates** - Providing Jira-specific prompts for agent-mediated fetching

---

## Technical Approach

### Architecture Fit

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TicketFetcher (AMI-29/30/31)      │  Handles HOW to get data               │
│  • AuggieMediatedFetcher (primary) │  • Structured prompt → raw JSON        │
│  • DirectAPIFetcher (fallback)     │  • REST API → raw JSON                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ raw JSON data
┌─────────────────────────────────────────────────────────────────────────────┐
│  JiraProvider (THIS TICKET)        │  Handles WHAT the data means           │
│  • can_handle()                    │  • URL/ID pattern matching             │
│  • parse_input()                   │  • URL/ID → normalized ticket ID       │
│  • normalize()                     │  • raw JSON → GenericTicket            │
│  • get_prompt_template()           │  • Jira-specific prompt for agent      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ProviderRegistry (AMI-17)                            │
│  @ProviderRegistry.register                                                  │
│  → Singleton provider instance per platform                                  │
│  → Auto-detection via get_provider_for_input()                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **PLATFORM Class Attribute** - Required for `@ProviderRegistry.register` decorator validation
2. **No Direct API Calls** - All fetching delegated to `TicketFetcher` via `TicketService` (AMI-32)
3. **Comprehensive Status Mapping** - Maps all common Jira statuses with `UNKNOWN` fallback
4. **Comprehensive Type Mapping** - Maps Jira issue types to `TicketType` enum
5. **Optional DI** - Constructor accepts optional `user_interaction` for testing
6. **Pattern Reuse** - Leverages `PlatformDetector` patterns for consistency

---

## Components to Create

### New File: `spec/integrations/providers/jira.py`

| Component | Purpose |
|-----------|---------|
| `JiraProvider` class | Concrete provider for Jira platform |
| `STATUS_MAPPING` dict | Maps Jira status names to `TicketStatus` |
| `TYPE_MAPPING` dict | Maps Jira issue types to `TicketType` |
| `STRUCTURED_PROMPT_TEMPLATE` str | Jira-specific prompt for agent-mediated fetching |
| `DEFAULT_PROJECT` constant | Default project key for numeric-only ticket IDs |

### Modified Files

| File | Changes |
|------|---------|
| `spec/integrations/providers/__init__.py` | Export `JiraProvider` |

### ABC Extension Note

> **Important:** The `normalize()` and `get_prompt_template()` methods are **not** currently part of the `IssueTrackerProvider` ABC. They are provider-specific extensions required by the hybrid architecture's `TicketFetcher` integration pattern:
> - `normalize()` - Called by `DirectAPIFetcher` and `AuggieMediatedFetcher` to convert raw JSON to `GenericTicket`
> - `get_prompt_template()` - Called by `AuggieMediatedFetcher` to get platform-specific structured prompts
>
> These methods may be added to the ABC in a future refactor, but for now they are implemented as concrete methods on each provider.

---

## Implementation Steps

### Step 1: Create JiraProvider Module

**File:** `spec/integrations/providers/jira.py`

```python
"""Jira issue tracker provider.

This module provides the JiraProvider class for integrating with Jira.
Following the hybrid architecture, this provider handles:
- Input parsing (URLs, PROJECT-123 format)
- Data normalization (raw JSON → GenericTicket)
- Status/type mapping to normalized enums

Data fetching is delegated to TicketFetcher implementations.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from spec.integrations.providers.base import (
    GenericTicket,
    IssueTrackerProvider,
    Platform,
    PlatformMetadata,
    TicketStatus,
    TicketType,
    sanitize_title_for_branch,
)
from spec.integrations.providers.registry import ProviderRegistry
from spec.integrations.providers.user_interaction import (
    CLIUserInteraction,
    UserInteractionInterface,
)


# Status mapping: Jira status name → TicketStatus
STATUS_MAPPING: dict[str, TicketStatus] = {
    # Open states
    "to do": TicketStatus.OPEN,
    "open": TicketStatus.OPEN,
    "backlog": TicketStatus.OPEN,
    "new": TicketStatus.OPEN,
    "reopened": TicketStatus.OPEN,
    # In Progress states
    "in progress": TicketStatus.IN_PROGRESS,
    "in development": TicketStatus.IN_PROGRESS,
    "in review": TicketStatus.REVIEW,
    "code review": TicketStatus.REVIEW,
    "review": TicketStatus.REVIEW,
    "testing": TicketStatus.REVIEW,
    "qa": TicketStatus.REVIEW,
    # Done states
    "done": TicketStatus.DONE,
    "resolved": TicketStatus.DONE,
    "completed": TicketStatus.DONE,
    # Closed states
    "closed": TicketStatus.CLOSED,
    # Blocked states
    "blocked": TicketStatus.BLOCKED,
    "on hold": TicketStatus.BLOCKED,
    "waiting": TicketStatus.BLOCKED,
}

# Type mapping: Jira issue type → TicketType
TYPE_MAPPING: dict[str, TicketType] = {
    # Feature types
    "story": TicketType.FEATURE,
    "feature": TicketType.FEATURE,
    "epic": TicketType.FEATURE,
    "user story": TicketType.FEATURE,
    "enhancement": TicketType.FEATURE,
    "new feature": TicketType.FEATURE,
    # Bug types
    "bug": TicketType.BUG,
    "defect": TicketType.BUG,
    "incident": TicketType.BUG,
    "problem": TicketType.BUG,
    # Task types
    "task": TicketType.TASK,
    "sub-task": TicketType.TASK,
    "subtask": TicketType.TASK,
    "spike": TicketType.TASK,
    # Maintenance types
    "technical debt": TicketType.MAINTENANCE,
    "improvement": TicketType.MAINTENANCE,
    "refactor": TicketType.MAINTENANCE,
    "maintenance": TicketType.MAINTENANCE,
    "chore": TicketType.MAINTENANCE,
}

# Default project key for numeric-only ticket IDs
# Can be overridden via environment variable JIRA_DEFAULT_PROJECT
DEFAULT_PROJECT: str = "PROJ"
```

### Step 2: Continue JiraProvider Implementation

Add the class definition and remaining implementation (continuing from Step 1):

```python
import os

# Structured prompt template for agent-mediated fetching
STRUCTURED_PROMPT_TEMPLATE = """Use your Jira tool to fetch issue {ticket_id}.

Return ONLY a JSON object with these fields (no markdown, no explanation):
{{
  "key": "<ticket key>",
  "fields": {{
    "summary": "<title>",
    "description": "<description text>",
    "status": {{"name": "<status name>"}},
    "issuetype": {{"name": "<issue type>"}},
    "priority": {{"name": "<priority>"}},
    "assignee": {{"displayName": "<name>", "emailAddress": "<email>"}} or null,
    "labels": ["<label1>", "<label2>"],
    "created": "<ISO timestamp>",
    "updated": "<ISO timestamp>",
    "project": {{"key": "<PROJECT>", "name": "<Project Name>"}},
    "components": [{{"name": "<component>"}}],
    "fixVersions": [{{"name": "<version>"}}],
    "customfield_10014": "<epic link>" or null,
    "customfield_10016": <story points number> or null
  }}
}}"""


@ProviderRegistry.register
class JiraProvider(IssueTrackerProvider):
    """Jira issue tracker provider.

    Handles Jira-specific input parsing and data normalization.
    Data fetching is delegated to TicketFetcher implementations.

    Class Attributes:
        PLATFORM: Platform.JIRA for registry registration
    """

    PLATFORM = Platform.JIRA

    # URL patterns for Jira
    _URL_PATTERNS = [
        # Atlassian Cloud: https://company.atlassian.net/browse/PROJECT-123
        re.compile(
            r"https?://[^/]+\.atlassian\.net/browse/(?P<ticket_id>[A-Z]+-\d+)",
            re.IGNORECASE,
        ),
        # Self-hosted Jira: https://jira.company.com/browse/PROJECT-123
        re.compile(
            r"https?://jira\.[^/]+/browse/(?P<ticket_id>[A-Z]+-\d+)",
            re.IGNORECASE,
        ),
        # Generic /browse/ URL
        re.compile(
            r"https?://[^/]+/browse/(?P<ticket_id>[A-Z]+-\d+)",
            re.IGNORECASE,
        ),
    ]

    # ID pattern: PROJECT-123 format
    _ID_PATTERN = re.compile(r"^(?P<ticket_id>[A-Z][A-Z0-9]*-\d+)$", re.IGNORECASE)

    # Numeric-only pattern: 123 → DEFAULT_PROJECT-123
    _NUMERIC_ID_PATTERN = re.compile(r"^(?P<number>\d+)$")

    def __init__(
        self,
        user_interaction: UserInteractionInterface | None = None,
        default_project: str | None = None,
    ) -> None:
        """Initialize JiraProvider.

        Args:
            user_interaction: Optional user interaction interface for DI.
                If not provided, uses CLIUserInteraction.
            default_project: Default project key for numeric-only ticket IDs.
                If not provided, uses JIRA_DEFAULT_PROJECT env var or DEFAULT_PROJECT constant.
        """
        self._user_interaction = user_interaction or CLIUserInteraction()
        self._default_project = (
            default_project
            or os.environ.get("JIRA_DEFAULT_PROJECT")
            or DEFAULT_PROJECT
        )

    @property
    def platform(self) -> Platform:
        """Return the platform this provider handles."""
        return Platform.JIRA

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Jira"

    def can_handle(self, input_str: str) -> bool:
        """Check if this provider can handle the given input.

        Recognizes:
        - Atlassian Cloud URLs: https://company.atlassian.net/browse/PROJ-123
        - Self-hosted Jira URLs: https://jira.company.com/browse/PROJ-123
        - Ticket IDs: PROJ-123, ABC-1, XYZ-99999 (case-insensitive)
        - Numeric IDs: 123 (uses default project)

        Args:
            input_str: URL or ticket ID to check

        Returns:
            True if this provider recognizes the input format
        """
        input_str = input_str.strip()

        # Check URL patterns
        for pattern in self._URL_PATTERNS:
            if pattern.match(input_str):
                return True

        # Check ID pattern (PROJECT-123)
        if self._ID_PATTERN.match(input_str):
            return True

        # Check numeric-only pattern (123)
        if self._NUMERIC_ID_PATTERN.match(input_str):
            return True

        return False

    def parse_input(self, input_str: str) -> str:
        """Parse input and extract normalized ticket ID.

        Args:
            input_str: URL or ticket ID

        Returns:
            Normalized ticket ID in uppercase (e.g., "PROJECT-123")
            For numeric-only input, prepends default project: 123 → "PROJ-123"

        Raises:
            ValueError: If input cannot be parsed
        """
        input_str = input_str.strip()

        # Try URL patterns first
        for pattern in self._URL_PATTERNS:
            match = pattern.match(input_str)
            if match:
                return match.group("ticket_id").upper()

        # Try ID pattern (PROJECT-123)
        match = self._ID_PATTERN.match(input_str)
        if match:
            return match.group("ticket_id").upper()

        # Try numeric-only pattern (123 → DEFAULT_PROJECT-123)
        match = self._NUMERIC_ID_PATTERN.match(input_str)
        if match:
            number = match.group("number")
            return f"{self._default_project.upper()}-{number}"

        raise ValueError(f"Cannot parse Jira ticket from input: {input_str}")
```

### Step 3: Add normalize() and remaining methods

```python
    def normalize(self, raw_data: dict[str, Any]) -> GenericTicket:
        """Convert raw Jira data to GenericTicket.

        Args:
            raw_data: Raw Jira API response (issue object)

        Returns:
            Populated GenericTicket with normalized fields
        """
        fields = raw_data.get("fields", {})
        ticket_id = raw_data.get("key", "")

        # Extract status and type
        status_name = fields.get("status", {}).get("name", "")
        type_name = fields.get("issuetype", {}).get("name", "")

        # Extract timestamps
        created_at = self._parse_timestamp(fields.get("created"))
        updated_at = self._parse_timestamp(fields.get("updated"))

        # Extract assignee
        assignee = None
        if fields.get("assignee"):
            assignee = fields["assignee"].get("displayName") or fields["assignee"].get("name")

        # Extract labels
        labels = fields.get("labels", [])

        # Build project key for URL
        project_key = fields.get("project", {}).get("key", "")

        # Build URL (fallback if not in raw data)
        url = raw_data.get("self", "")
        if not url and project_key:
            # Construct URL from project key
            url = f"https://jira.atlassian.net/browse/{ticket_id}"

        # Extract platform-specific metadata
        platform_metadata: PlatformMetadata = {
            "raw_response": raw_data,
            "project_key": project_key,
            "priority": fields.get("priority", {}).get("name", ""),
            "epic_link": fields.get("customfield_10014", ""),
            "story_points": fields.get("customfield_10016"),
            "components": [c.get("name", "") for c in fields.get("components", [])],
            "issue_type_id": fields.get("issuetype", {}).get("id", ""),
            "resolution": fields.get("resolution", {}).get("name", "") if fields.get("resolution") else "",
            "fix_versions": [v.get("name", "") for v in fields.get("fixVersions", [])],
        }

        return GenericTicket(
            id=ticket_id,
            platform=Platform.JIRA,
            url=url,
            title=fields.get("summary", ""),
            description=fields.get("description", "") or "",
            status=self._map_status(status_name),
            type=self._map_type(type_name),
            assignee=assignee,
            labels=labels,
            created_at=created_at,
            updated_at=updated_at,
            branch_summary=sanitize_title_for_branch(fields.get("summary", "")),
            platform_metadata=platform_metadata,
        )

    def _map_status(self, status_name: str) -> TicketStatus:
        """Map Jira status to TicketStatus enum.

        Args:
            status_name: Jira status name (e.g., "In Progress")

        Returns:
            Normalized TicketStatus, UNKNOWN if not recognized
        """
        return STATUS_MAPPING.get(status_name.lower(), TicketStatus.UNKNOWN)

    def _map_type(self, type_name: str) -> TicketType:
        """Map Jira issue type to TicketType enum.

        Args:
            type_name: Jira issue type name (e.g., "Story")

        Returns:
            Normalized TicketType, UNKNOWN if not recognized
        """
        return TYPE_MAPPING.get(type_name.lower(), TicketType.UNKNOWN)

    def _parse_timestamp(self, timestamp_str: str | None) -> datetime | None:
        """Parse ISO timestamp from Jira API.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            datetime object or None if parsing fails
        """
        if not timestamp_str:
            return None
        try:
            # Jira uses ISO format: 2024-01-15T10:30:00.000+0000
            # Handle with or without milliseconds and timezone
            return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def get_prompt_template(self) -> str:
        """Return structured prompt template for agent-mediated fetch.

        Returns:
            Prompt template string with {ticket_id} placeholder
        """
        return STRUCTURED_PROMPT_TEMPLATE

    def fetch_ticket(self, ticket_id: str) -> GenericTicket:
        """Fetch ticket details from Jira.

        NOTE: This method is required by IssueTrackerProvider ABC but
        in the hybrid architecture, fetching is delegated to TicketService
        which uses TicketFetcher implementations. This method is kept for
        backward compatibility and direct provider usage.

        Args:
            ticket_id: Normalized ticket ID from parse_input()

        Returns:
            Populated GenericTicket

        Raises:
            NotImplementedError: Fetching should use TicketService
        """
        raise NotImplementedError(
            "JiraProvider.fetch_ticket() is deprecated in hybrid architecture. "
            "Use TicketService.get_ticket() with AuggieMediatedFetcher or "
            "DirectAPIFetcher instead."
        )

    def check_connection(self) -> tuple[bool, str]:
        """Verify Jira integration is properly configured.

        NOTE: Connection checking is delegated to TicketFetcher implementations
        in the hybrid architecture.

        Returns:
            Tuple of (success: bool, message: str)
        """
        # In hybrid architecture, connection check is done by TicketService
        # This method returns True as the provider itself doesn't manage connections
        return (True, "JiraProvider ready - use TicketService for connection verification")
```

### Step 4: Update Package Exports

**File:** `spec/integrations/providers/__init__.py`

```python
# Add to existing exports
from spec.integrations.providers.jira import JiraProvider

__all__ = [
    # ... existing exports
    "JiraProvider",
]
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_jira.py`

```python
"""Tests for JiraProvider."""

import pytest
from datetime import datetime

from spec.integrations.providers.base import (
    GenericTicket,
    Platform,
    TicketStatus,
    TicketType,
)
from spec.integrations.providers.jira import (
    JiraProvider,
    STATUS_MAPPING,
    TYPE_MAPPING,
    DEFAULT_PROJECT,
)
from spec.integrations.providers.registry import ProviderRegistry


class TestJiraProviderRegistration:
    """Test provider registration with ProviderRegistry."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test."""
        ProviderRegistry.clear()
        yield
        ProviderRegistry.clear()

    def test_provider_has_platform_attribute(self):
        """JiraProvider has required PLATFORM class attribute."""
        assert hasattr(JiraProvider, "PLATFORM")
        assert JiraProvider.PLATFORM == Platform.JIRA

    def test_provider_registers_successfully(self):
        """JiraProvider can be registered with ProviderRegistry."""
        # Import triggers registration due to decorator
        from spec.integrations.providers.jira import JiraProvider

        provider = ProviderRegistry.get_provider(Platform.JIRA)
        assert provider is not None
        assert isinstance(provider, JiraProvider)

    def test_singleton_pattern(self):
        """Same instance returned for multiple get_provider calls."""
        provider1 = ProviderRegistry.get_provider(Platform.JIRA)
        provider2 = ProviderRegistry.get_provider(Platform.JIRA)
        assert provider1 is provider2


class TestJiraProviderCanHandle:
    """Test can_handle() method."""

    @pytest.fixture
    def provider(self):
        return JiraProvider()

    # Valid URLs
    @pytest.mark.parametrize("url", [
        "https://company.atlassian.net/browse/PROJ-123",
        "https://myorg.atlassian.net/browse/ABC-1",
        "https://TEAM.atlassian.net/browse/XYZ-99999",
        "https://jira.company.com/browse/PROJ-123",
        "https://jira.example.org/browse/TEST-1",
        "http://jira.internal.net/browse/DEV-42",
    ])
    def test_can_handle_valid_urls(self, provider, url):
        assert provider.can_handle(url) is True

    # Valid IDs
    @pytest.mark.parametrize("ticket_id", [
        "PROJ-123",
        "ABC-1",
        "XYZ-99999",
        "proj-123",  # lowercase
        "A1-1",      # alphanumeric project
        "123",       # numeric-only (uses default project)
        "99999",     # large numeric-only
    ])
    def test_can_handle_valid_ids(self, provider, ticket_id):
        assert provider.can_handle(ticket_id) is True

    # Invalid inputs
    @pytest.mark.parametrize("input_str", [
        "https://github.com/owner/repo/issues/123",
        "owner/repo#123",
        "AMI-18-implement-feature",  # Not just ticket ID
        "PROJECT",                   # No number
        "",                          # Empty
        "abc",                       # Letters only, no dash
    ])
    def test_can_handle_invalid_inputs(self, provider, input_str):
        assert provider.can_handle(input_str) is False


class TestJiraProviderParseInput:
    """Test parse_input() method."""

    @pytest.fixture
    def provider(self):
        return JiraProvider()

    def test_parse_atlassian_url(self, provider):
        url = "https://company.atlassian.net/browse/PROJ-123"
        assert provider.parse_input(url) == "PROJ-123"

    def test_parse_self_hosted_url(self, provider):
        url = "https://jira.company.com/browse/TEST-42"
        assert provider.parse_input(url) == "TEST-42"

    def test_parse_lowercase_id(self, provider):
        assert provider.parse_input("proj-123") == "PROJ-123"

    def test_parse_with_whitespace(self, provider):
        assert provider.parse_input("  PROJ-123  ") == "PROJ-123"

    def test_parse_numeric_id_uses_default_project(self, provider):
        """Numeric-only input uses default project."""
        assert provider.parse_input("123") == f"{DEFAULT_PROJECT}-123"

    def test_parse_numeric_id_with_custom_default(self):
        """Numeric-only input uses custom default project."""
        provider = JiraProvider(default_project="MYPROJ")
        assert provider.parse_input("456") == "MYPROJ-456"

    def test_parse_invalid_raises_valueerror(self, provider):
        with pytest.raises(ValueError, match="Cannot parse Jira ticket"):
            provider.parse_input("not-a-ticket")


class TestJiraProviderNormalize:
    """Test normalize() method."""

    @pytest.fixture
    def provider(self):
        return JiraProvider()

    @pytest.fixture
    def sample_jira_response(self):
        return {
            "key": "PROJ-123",
            "self": "https://company.atlassian.net/rest/api/2/issue/12345",
            "fields": {
                "summary": "Implement new feature",
                "description": "This is the description",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Story", "id": "10001"},
                "priority": {"name": "High"},
                "assignee": {
                    "displayName": "John Doe",
                    "emailAddress": "john@example.com",
                },
                "labels": ["backend", "priority"],
                "created": "2024-01-15T10:30:00.000+0000",
                "updated": "2024-01-20T15:45:00.000+0000",
                "project": {"key": "PROJ", "name": "My Project"},
                "components": [{"name": "API"}],
                "fixVersions": [{"name": "v1.0"}],
                "customfield_10014": "PROJ-100",  # Epic link
                "customfield_10016": 5,            # Story points
            },
        }

    def test_normalize_full_response(self, provider, sample_jira_response):
        ticket = provider.normalize(sample_jira_response)

        assert ticket.id == "PROJ-123"
        assert ticket.platform == Platform.JIRA
        assert ticket.title == "Implement new feature"
        assert ticket.description == "This is the description"
        assert ticket.status == TicketStatus.IN_PROGRESS
        assert ticket.type == TicketType.FEATURE
        assert ticket.assignee == "John Doe"
        assert ticket.labels == ["backend", "priority"]
        assert ticket.created_at is not None
        assert ticket.updated_at is not None

    def test_normalize_minimal_response(self, provider):
        minimal = {"key": "TEST-1", "fields": {"summary": "Minimal"}}
        ticket = provider.normalize(minimal)

        assert ticket.id == "TEST-1"
        assert ticket.title == "Minimal"
        assert ticket.status == TicketStatus.UNKNOWN
        assert ticket.type == TicketType.UNKNOWN


class TestStatusMapping:
    """Test status mapping coverage."""

    @pytest.fixture
    def provider(self):
        return JiraProvider()

    @pytest.mark.parametrize("status,expected", [
        ("To Do", TicketStatus.OPEN),
        ("In Progress", TicketStatus.IN_PROGRESS),
        ("In Review", TicketStatus.REVIEW),
        ("Done", TicketStatus.DONE),
        ("Closed", TicketStatus.CLOSED),
        ("Blocked", TicketStatus.BLOCKED),
        ("Unknown Status", TicketStatus.UNKNOWN),
    ])
    def test_status_mapping(self, provider, status, expected):
        assert provider._map_status(status) == expected


class TestTypeMapping:
    """Test type mapping coverage."""

    @pytest.fixture
    def provider(self):
        return JiraProvider()

    @pytest.mark.parametrize("type_name,expected", [
        ("Story", TicketType.FEATURE),
        ("Bug", TicketType.BUG),
        ("Task", TicketType.TASK),
        ("Technical Debt", TicketType.MAINTENANCE),
        ("Unknown Type", TicketType.UNKNOWN),
    ])
    def test_type_mapping(self, provider, type_name, expected):
        assert provider._map_type(type_name) == expected
```

---

## Dependencies

### Required (Must Be Complete)

| Dependency | Ticket | Status |
|------------|--------|--------|
| `PlatformDetector` | AMI-16 | ✅ Complete |
| `ProviderRegistry` | AMI-17 | ✅ Complete |
| `IssueTrackerProvider` ABC | AMI-17 | ✅ Complete |
| `Platform` enum | AMI-17 | ✅ Complete |
| `GenericTicket` dataclass | AMI-17 | ✅ Complete |
| `UserInteractionInterface` | AMI-17 | ✅ Complete |

### Future Integration

| Integration Point | Ticket | Relationship |
|-------------------|--------|--------------|
| `TicketService` | AMI-32 | Orchestrates provider + fetcher |
| `AuggieMediatedFetcher` | AMI-30 | Uses `get_prompt_template()` |
| `DirectAPIFetcher` | AMI-31 | Uses `normalize()` for response handling |
| `TicketFetcher` abstraction | AMI-29 | Base class for fetcher implementations |

---

## Migration Considerations

### Backward Compatibility

- `fetch_ticket()` raises `NotImplementedError` with clear migration message
- Existing code using direct Jira integration unchanged
- Provider is opt-in via explicit import

### Gradual Migration Path

1. **Phase 1 (This Ticket):** Implement JiraProvider with parse/normalize capabilities
2. **Phase 2 (AMI-32):** Integrate with TicketService for unified access
3. **Phase 3 (Future):** Deprecate legacy `specflow/integrations/jira.py`

---

## Acceptance Criteria Checklist

From Linear ticket AMI-18:

- [ ] JiraProvider class extends IssueTrackerProvider ABC
- [ ] Registers with ProviderRegistry using @register decorator
- [ ] PLATFORM class attribute set to Platform.JIRA
- [ ] Implements all required abstract methods:
  - [ ] `platform` property
  - [ ] `name` property
  - [ ] `can_handle(input_str)` - recognizes Jira URLs and IDs
  - [ ] `parse_input(input_str)` - extracts normalized ticket ID
  - [ ] `fetch_ticket(ticket_id)` - placeholder for hybrid architecture
  - [ ] `check_connection()` - returns ready status
- [ ] Implements additional methods for hybrid architecture:
  - [ ] `normalize(raw_data)` - converts Jira JSON to GenericTicket
  - [ ] `get_prompt_template()` - returns structured prompt for agent
- [ ] STATUS_MAPPING covers common Jira statuses
- [ ] TYPE_MAPPING covers common Jira issue types
- [ ] Unit tests with >90% coverage
- [ ] Documentation in docstrings

---

## Example Usage

### Basic Provider Usage

```python
from spec.integrations.providers.jira import JiraProvider
from spec.integrations.providers.registry import ProviderRegistry
from spec.integrations.providers.base import Platform

# Get provider via registry (singleton)
provider = ProviderRegistry.get_provider(Platform.JIRA)

# Check if input is handled by this provider
if provider.can_handle("https://company.atlassian.net/browse/PROJ-123"):
    ticket_id = provider.parse_input("https://company.atlassian.net/browse/PROJ-123")
    print(f"Parsed ticket ID: {ticket_id}")  # PROJ-123
```

### Integration with TicketService (AMI-32)

```python
from spec.integrations.ticket_service import TicketService

# TicketService handles provider lookup and fetching
service = TicketService()
ticket = await service.get_ticket("https://company.atlassian.net/browse/PROJ-123")

# Ticket is already normalized as GenericTicket
print(f"Title: {ticket.title}")
print(f"Status: {ticket.status}")
print(f"Type: {ticket.type}")
```

### Test Isolation Pattern

```python
import pytest
from spec.integrations.providers.registry import ProviderRegistry

@pytest.fixture(autouse=True)
def reset_registry():
    """Ensure clean registry state for each test."""
    ProviderRegistry.clear()
    yield
    ProviderRegistry.clear()


def test_isolated_provider():
    """Test runs with clean registry state."""
    # Re-import to trigger registration
    from spec.integrations.providers.jira import JiraProvider

    provider = ProviderRegistry.get_provider(Platform.JIRA)
    assert provider is not None
```

---

## References

- [Architecture Spec - Section 6: Provider Registry](specs/00_Architecture_Refactor_Spec.md#6-provider-registry--factory-pattern)
- [AMI-17 Implementation Plan](specs/AMI-17-implementation-plan.md) - ProviderRegistry pattern
- [AMI-30 Implementation Plan](specs/AMI-30-implementation-plan.md) - Structured prompt templates
- [AMI-31 Implementation Plan](specs/AMI-31-implementation-plan.md) - Direct API handler pattern

---

## Implementation Notes

> **Alignment with Linear Ticket:** This implementation plan has been verified against the AMI-18 Linear ticket to ensure all requirements are addressed. Key alignment points:
>
> 1. **AMI-17 Alignment Verification** - The constructor contract, `PLATFORM` class attribute, and `@ProviderRegistry.register` decorator pattern all follow the AMI-17 provider infrastructure specifications.
>
> 2. **Constructor Contract** - The `JiraProvider.__init__()` accepts optional `user_interaction` parameter for dependency injection during testing, following the same pattern as other providers. The `default_project` parameter enables numeric ID support configuration.
>
> 3. **Test Isolation Pattern** - Tests should use the `reset_registry` fixture (shown in Testing Strategy) to ensure clean registry state. This prevents cross-test pollution when using the `@ProviderRegistry.register` decorator.
>
> 4. **Numeric ID Support** - Plain numeric IDs (e.g., `123`) are supported and mapped to `DEFAULT_PROJECT-123` using the `_NUMERIC_ID_PATTERN` regex. The default project can be configured via:
>    - Constructor parameter: `JiraProvider(default_project="MYPROJ")`
>    - Environment variable: `JIRA_DEFAULT_PROJECT`
>    - Constant fallback: `DEFAULT_PROJECT = "PROJ"`
