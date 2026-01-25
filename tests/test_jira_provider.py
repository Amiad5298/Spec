"""Tests for JiraProvider in spec.integrations.providers.jira module.

Tests cover:
- Provider registration with ProviderRegistry
- can_handle() for URLs and ticket IDs
- parse_input() for URL and ID parsing
- normalize() for raw Jira data conversion
- Status and type mapping
- get_prompt_template() and other methods
"""

import pytest

from spec.integrations.providers.base import (
    Platform,
    TicketStatus,
    TicketType,
)
from spec.integrations.providers.jira import (
    DEFAULT_PROJECT,
    JiraProvider,
)
from spec.integrations.providers.registry import ProviderRegistry


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry before and after each test."""
    ProviderRegistry.clear()
    yield
    ProviderRegistry.clear()


@pytest.fixture
def provider():
    """Create a fresh JiraProvider instance."""
    return JiraProvider()


class TestJiraProviderRegistration:
    """Test provider registration with ProviderRegistry."""

    def test_provider_has_platform_attribute(self):
        """JiraProvider has required PLATFORM class attribute."""
        assert hasattr(JiraProvider, "PLATFORM")
        assert JiraProvider.PLATFORM == Platform.JIRA

    def test_provider_registers_successfully(self):
        """JiraProvider can be registered with ProviderRegistry."""
        # Manually register since the decorator ran at import time before clear()
        ProviderRegistry.register(JiraProvider)

        provider = ProviderRegistry.get_provider(Platform.JIRA)
        assert provider is not None
        assert isinstance(provider, JiraProvider)

    def test_singleton_pattern(self):
        """Same instance returned for multiple get_provider calls."""
        # Manually register since the decorator ran at import time before clear()
        ProviderRegistry.register(JiraProvider)

        provider1 = ProviderRegistry.get_provider(Platform.JIRA)
        provider2 = ProviderRegistry.get_provider(Platform.JIRA)
        assert provider1 is provider2


class TestJiraProviderProperties:
    """Test provider properties."""

    def test_platform_property(self, provider):
        """platform property returns Platform.JIRA."""
        assert provider.platform == Platform.JIRA

    def test_name_property(self, provider):
        """name property returns 'Jira'."""
        assert provider.name == "Jira"


class TestJiraProviderCanHandle:
    """Test can_handle() method."""

    # Valid URLs
    @pytest.mark.parametrize(
        "url",
        [
            "https://company.atlassian.net/browse/PROJ-123",
            "https://myorg.atlassian.net/browse/ABC-1",
            "https://TEAM.atlassian.net/browse/XYZ-99999",
            "https://jira.company.com/browse/PROJ-123",
            "https://jira.example.org/browse/TEST-1",
            "http://jira.internal.net/browse/DEV-42",
        ],
    )
    def test_can_handle_valid_urls(self, provider, url):
        """can_handle returns True for valid Jira URLs."""
        assert provider.can_handle(url) is True

    # Valid IDs
    @pytest.mark.parametrize(
        "ticket_id",
        [
            "PROJ-123",
            "ABC-1",
            "XYZ-99999",
            "proj-123",  # lowercase
            "A1-1",  # alphanumeric project
            "123",  # numeric-only (uses default project)
            "99999",  # large numeric-only
        ],
    )
    def test_can_handle_valid_ids(self, provider, ticket_id):
        """can_handle returns True for valid ticket IDs."""
        assert provider.can_handle(ticket_id) is True

    # Invalid inputs
    @pytest.mark.parametrize(
        "input_str",
        [
            "https://github.com/owner/repo/issues/123",
            "owner/repo#123",
            "AMI-18-implement-feature",  # Not just ticket ID
            "PROJECT",  # No number
            "",  # Empty
            "abc",  # Letters only, no dash
        ],
    )
    def test_can_handle_invalid_inputs(self, provider, input_str):
        """can_handle returns False for invalid inputs."""
        assert provider.can_handle(input_str) is False


class TestJiraProviderParseInput:
    """Test parse_input() method."""

    def test_parse_atlassian_url(self, provider):
        """Parses Atlassian Cloud URL."""
        url = "https://company.atlassian.net/browse/PROJ-123"
        assert provider.parse_input(url) == "PROJ-123"

    def test_parse_self_hosted_url(self, provider):
        """Parses self-hosted Jira URL."""
        url = "https://jira.company.com/browse/TEST-42"
        assert provider.parse_input(url) == "TEST-42"

    def test_parse_lowercase_id(self, provider):
        """Normalizes lowercase ID to uppercase."""
        assert provider.parse_input("proj-123") == "PROJ-123"

    def test_parse_with_whitespace(self, provider):
        """Strips whitespace from input."""
        assert provider.parse_input("  PROJ-123  ") == "PROJ-123"

    def test_parse_numeric_id_uses_default_project(self, provider):
        """Numeric-only input uses default project."""
        assert provider.parse_input("123") == f"{DEFAULT_PROJECT}-123"

    def test_parse_numeric_id_with_custom_default(self):
        """Numeric-only input uses custom default project."""
        provider = JiraProvider(default_project="MYPROJ")
        assert provider.parse_input("456") == "MYPROJ-456"

    def test_parse_invalid_raises_valueerror(self, provider):
        """Invalid input raises ValueError."""
        with pytest.raises(ValueError, match="Cannot parse Jira ticket"):
            provider.parse_input("not-a-ticket")


class TestJiraProviderNormalize:
    """Test normalize() method."""

    @pytest.fixture
    def sample_jira_response(self):
        """Sample Jira API response."""
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
                "customfield_10016": 5,  # Story points
            },
        }

    def test_normalize_full_response(self, provider, sample_jira_response):
        """Normalizes full Jira response to GenericTicket."""
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
        """Normalizes minimal Jira response."""
        minimal = {"key": "TEST-1", "fields": {"summary": "Minimal"}}
        ticket = provider.normalize(minimal)

        assert ticket.id == "TEST-1"
        assert ticket.title == "Minimal"
        assert ticket.status == TicketStatus.UNKNOWN
        assert ticket.type == TicketType.UNKNOWN
        assert ticket.assignee is None
        assert ticket.labels == []

    def test_normalize_extracts_platform_metadata(self, provider, sample_jira_response):
        """Normalizes and extracts platform metadata."""
        ticket = provider.normalize(sample_jira_response)

        assert ticket.platform_metadata["project_key"] == "PROJ"
        assert ticket.platform_metadata["priority"] == "High"
        assert ticket.platform_metadata["epic_link"] == "PROJ-100"
        assert ticket.platform_metadata["story_points"] == 5
        assert ticket.platform_metadata["components"] == ["API"]
        assert ticket.platform_metadata["fix_versions"] == ["v1.0"]

    def test_normalize_generates_branch_summary(self, provider, sample_jira_response):
        """Normalizes and generates branch summary."""
        ticket = provider.normalize(sample_jira_response)

        assert ticket.branch_summary == "implement-new-feature"

    def test_normalize_empty_response(self, provider):
        """Normalizes empty dict without raising exceptions."""
        ticket = provider.normalize({})

        assert ticket.id == ""
        assert ticket.platform == Platform.JIRA
        assert ticket.title == ""
        assert ticket.description == ""
        assert ticket.status == TicketStatus.UNKNOWN
        assert ticket.type == TicketType.UNKNOWN
        assert ticket.assignee is None
        assert ticket.labels == []
        assert ticket.created_at is None
        assert ticket.updated_at is None

    def test_normalize_handles_non_dict_nested_fields(self, provider):
        """Normalizes response where nested fields are None instead of dicts."""
        # This simulates API responses where status, issuetype, etc. are null
        response = {
            "key": "TEST-1",
            "fields": {
                "summary": "Test ticket",
                "status": None,
                "issuetype": None,
                "assignee": None,
                "project": None,
                "priority": None,
                "resolution": None,
                "components": None,
                "fixVersions": None,
                "labels": None,
            },
        }
        ticket = provider.normalize(response)

        assert ticket.id == "TEST-1"
        assert ticket.title == "Test ticket"
        assert ticket.status == TicketStatus.UNKNOWN
        assert ticket.type == TicketType.UNKNOWN
        assert ticket.assignee is None
        assert ticket.labels == []
        assert ticket.platform_metadata["components"] == []
        assert ticket.platform_metadata["fix_versions"] == []


class TestStatusMapping:
    """Test status mapping coverage."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("To Do", TicketStatus.OPEN),
            ("Open", TicketStatus.OPEN),
            ("Backlog", TicketStatus.OPEN),
            ("In Progress", TicketStatus.IN_PROGRESS),
            ("In Development", TicketStatus.IN_PROGRESS),
            ("In Review", TicketStatus.REVIEW),
            ("Code Review", TicketStatus.REVIEW),
            ("Testing", TicketStatus.REVIEW),
            ("Done", TicketStatus.DONE),
            ("Resolved", TicketStatus.DONE),
            ("Closed", TicketStatus.CLOSED),
            ("Blocked", TicketStatus.BLOCKED),
            ("On Hold", TicketStatus.BLOCKED),
            ("Unknown Status", TicketStatus.UNKNOWN),
        ],
    )
    def test_status_mapping(self, provider, status, expected):
        """Maps Jira status to TicketStatus."""
        assert provider._map_status(status) == expected


class TestTypeMapping:
    """Test type mapping coverage."""

    @pytest.mark.parametrize(
        "type_name,expected",
        [
            ("Story", TicketType.FEATURE),
            ("Feature", TicketType.FEATURE),
            ("Epic", TicketType.FEATURE),
            ("Bug", TicketType.BUG),
            ("Defect", TicketType.BUG),
            ("Task", TicketType.TASK),
            ("Sub-task", TicketType.TASK),
            ("Spike", TicketType.TASK),
            ("Technical Debt", TicketType.MAINTENANCE),
            ("Improvement", TicketType.MAINTENANCE),
            ("Unknown Type", TicketType.UNKNOWN),
        ],
    )
    def test_type_mapping(self, provider, type_name, expected):
        """Maps Jira issue type to TicketType."""
        assert provider._map_type(type_name) == expected


class TestJiraProviderMethods:
    """Test remaining provider methods."""

    def test_get_prompt_template(self, provider):
        """get_prompt_template returns structured prompt."""
        template = provider.get_prompt_template()
        assert "{ticket_id}" in template
        assert "Jira" in template

    def test_fetch_ticket_raises_not_implemented(self, provider):
        """fetch_ticket raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="deprecated"):
            provider.fetch_ticket("PROJ-123")

    def test_check_connection_returns_ready(self, provider):
        """check_connection returns ready status."""
        success, message = provider.check_connection()
        assert success is True
        assert "ready" in message.lower()


class TestJiraProviderTimestampParsing:
    """Test timestamp parsing."""

    def test_parse_valid_timestamp(self, provider):
        """Parses valid ISO timestamp."""
        ts = provider._parse_timestamp("2024-01-15T10:30:00.000+0000")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15

    def test_parse_timestamp_with_z(self, provider):
        """Parses timestamp with Z suffix."""
        ts = provider._parse_timestamp("2024-01-15T10:30:00Z")
        assert ts is not None

    def test_parse_none_timestamp(self, provider):
        """Returns None for None input."""
        assert provider._parse_timestamp(None) is None

    def test_parse_invalid_timestamp(self, provider):
        """Returns None for invalid timestamp."""
        assert provider._parse_timestamp("not-a-timestamp") is None

    def test_parse_timestamp_without_colon_in_timezone(self, provider):
        """Parses timestamp with +0000 format (without colon in timezone)."""
        ts = provider._parse_timestamp("2024-01-15T10:30:00.000+0000")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.day == 15
        assert ts.hour == 10
        assert ts.minute == 30

    def test_parse_timestamp_with_negative_timezone_offset(self, provider):
        """Parses timestamp with negative timezone offset (without colon)."""
        ts = provider._parse_timestamp("2024-01-15T10:30:00.000-0500")
        assert ts is not None
        assert ts.year == 2024
        # Timezone info should be preserved
        assert ts.tzinfo is not None

    def test_parse_timestamp_with_colon_in_timezone(self, provider):
        """Parses timestamp with +00:00 format (with colon in timezone)."""
        ts = provider._parse_timestamp("2024-01-15T10:30:00.000+00:00")
        assert ts is not None
        assert ts.year == 2024
