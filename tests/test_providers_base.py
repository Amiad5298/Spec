"""Tests for specflow.integrations.providers.base module.

Tests cover:
- Platform, TicketStatus, TicketType enums
- GenericTicket dataclass properties and methods
- semantic_branch_prefix property
- safe_branch_name property
- IssueTrackerProvider abstract methods
- Default generate_branch_summary implementation
"""

import pytest
from abc import ABC
from enum import Enum

from specflow.integrations.providers.base import (
    GenericTicket,
    IssueTrackerProvider,
    Platform,
    TicketStatus,
    TicketType,
)


class TestPlatformEnum:
    """Tests for Platform enum."""

    def test_is_enum(self):
        """Platform is an Enum."""
        assert issubclass(Platform, Enum)

    def test_has_jira(self):
        """Has JIRA platform."""
        assert Platform.JIRA is not None

    def test_has_github(self):
        """Has GITHUB platform."""
        assert Platform.GITHUB is not None

    def test_has_linear(self):
        """Has LINEAR platform."""
        assert Platform.LINEAR is not None

    def test_has_azure_devops(self):
        """Has AZURE_DEVOPS platform."""
        assert Platform.AZURE_DEVOPS is not None

    def test_has_monday(self):
        """Has MONDAY platform."""
        assert Platform.MONDAY is not None

    def test_has_trello(self):
        """Has TRELLO platform."""
        assert Platform.TRELLO is not None

    def test_all_platforms(self):
        """All expected platforms are present."""
        platforms = list(Platform)
        assert len(platforms) == 6

    def test_platform_values_are_auto(self):
        """Platform values are auto-generated integers."""
        for platform in Platform:
            assert isinstance(platform.value, int)


class TestTicketStatusEnum:
    """Tests for TicketStatus enum."""

    def test_is_enum(self):
        """TicketStatus is an Enum."""
        assert issubclass(TicketStatus, Enum)

    def test_has_open(self):
        """Has OPEN status."""
        assert TicketStatus.OPEN is not None

    def test_has_in_progress(self):
        """Has IN_PROGRESS status."""
        assert TicketStatus.IN_PROGRESS is not None

    def test_has_review(self):
        """Has REVIEW status."""
        assert TicketStatus.REVIEW is not None

    def test_has_done(self):
        """Has DONE status."""
        assert TicketStatus.DONE is not None

    def test_has_closed(self):
        """Has CLOSED status."""
        assert TicketStatus.CLOSED is not None

    def test_has_blocked(self):
        """Has BLOCKED status."""
        assert TicketStatus.BLOCKED is not None

    def test_has_unknown(self):
        """Has UNKNOWN status for unmapped statuses."""
        assert TicketStatus.UNKNOWN is not None


class TestTicketTypeEnum:
    """Tests for TicketType enum."""

    def test_is_enum(self):
        """TicketType is an Enum."""
        assert issubclass(TicketType, Enum)

    def test_has_feature(self):
        """Has FEATURE type."""
        assert TicketType.FEATURE is not None

    def test_has_bug(self):
        """Has BUG type."""
        assert TicketType.BUG is not None

    def test_has_task(self):
        """Has TASK type."""
        assert TicketType.TASK is not None

    def test_has_maintenance(self):
        """Has MAINTENANCE type."""
        assert TicketType.MAINTENANCE is not None

    def test_has_unknown(self):
        """Has UNKNOWN type for unmapped types."""
        assert TicketType.UNKNOWN is not None


class TestGenericTicketBasic:
    """Basic tests for GenericTicket dataclass."""

    def test_creation_with_required_fields(self):
        """Can create ticket with required fields only."""
        ticket = GenericTicket(
            id="TEST-123",
            platform=Platform.JIRA,
            url="https://jira.example.com/TEST-123",
        )
        assert ticket.id == "TEST-123"
        assert ticket.platform == Platform.JIRA
        assert ticket.url == "https://jira.example.com/TEST-123"

    def test_default_values(self):
        """Has sensible default values."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.GITHUB,
            url="https://github.com/owner/repo/issues/1",
        )
        assert ticket.title == ""
        assert ticket.description == ""
        assert ticket.status == TicketStatus.UNKNOWN
        assert ticket.type == TicketType.UNKNOWN
        assert ticket.assignee is None
        assert ticket.labels == []
        assert ticket.platform_metadata == {}

    def test_full_ticket(self):
        """Can create ticket with all fields."""
        ticket = GenericTicket(
            id="PROJ-456",
            platform=Platform.LINEAR,
            url="https://linear.app/issue/PROJ-456",
            title="Add feature",
            description="Long description",
            status=TicketStatus.IN_PROGRESS,
            type=TicketType.FEATURE,
            assignee="john.doe",
            labels=["frontend", "priority-high"],
            platform_metadata={"key": "value"},
        )
        assert ticket.description == "Long description"
        assert ticket.assignee == "john.doe"
        assert "frontend" in ticket.labels


class TestGenericTicketSemanticBranchPrefix:
    """Tests for GenericTicket.semantic_branch_prefix property."""

    def test_feature_returns_feat(self):
        """FEATURE type returns 'feat'."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.FEATURE,
        )
        assert ticket.semantic_branch_prefix == "feat"

    def test_bug_returns_fix(self):
        """BUG type returns 'fix'."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.BUG,
        )
        assert ticket.semantic_branch_prefix == "fix"

    def test_task_returns_chore(self):
        """TASK type returns 'chore'."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.TASK,
        )
        assert ticket.semantic_branch_prefix == "chore"

    def test_maintenance_returns_refactor(self):
        """MAINTENANCE type returns 'refactor'."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.MAINTENANCE,
        )
        assert ticket.semantic_branch_prefix == "refactor"

    def test_unknown_returns_feature(self):
        """UNKNOWN type defaults to 'feature'."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.UNKNOWN,
        )
        assert ticket.semantic_branch_prefix == "feature"


class TestGenericTicketSafeBranchName:
    """Tests for GenericTicket.safe_branch_name property."""

    def test_basic_branch_name_with_summary(self):
        """Generates branch name with branch_summary."""
        ticket = GenericTicket(
            id="PROJ-123",
            platform=Platform.JIRA,
            url="https://jira.example.com/PROJ-123",
            type=TicketType.FEATURE,
            branch_summary="add-user-login",
        )
        branch = ticket.safe_branch_name
        assert branch.startswith("feat/")
        assert "proj-123" in branch.lower()
        assert "add-user-login" in branch.lower()

    def test_branch_name_lowercase(self):
        """Branch name contains lowercase ticket ID."""
        ticket = GenericTicket(
            id="TEST-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/TEST-1",
            type=TicketType.BUG,
            branch_summary="uppercase-fix",
        )
        branch = ticket.safe_branch_name
        assert "test-1" in branch  # ID is lowercased

    def test_branch_name_without_summary(self):
        """Branch name works without branch_summary."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            type=TicketType.TASK,
        )
        branch = ticket.safe_branch_name
        # Should be prefix/id only
        assert branch == "chore/t-1"

    def test_branch_name_includes_ticket_id(self):
        """Includes ticket ID in branch name."""
        ticket = GenericTicket(
            id="ABC-999",
            platform=Platform.JIRA,
            url="https://jira.example.com/ABC-999",
            type=TicketType.FEATURE,
            branch_summary="feature-work",
        )
        branch = ticket.safe_branch_name
        assert "abc-999" in branch.lower()

    def test_bug_branch_starts_with_fix(self):
        """Bug ticket branch starts with fix/."""
        ticket = GenericTicket(
            id="BUG-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/BUG-1",
            type=TicketType.BUG,
            branch_summary="critical-issue",
        )
        branch = ticket.safe_branch_name
        assert branch.startswith("fix/")

    def test_task_branch_starts_with_chore(self):
        """Task ticket branch starts with chore/."""
        ticket = GenericTicket(
            id="TASK-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/TASK-1",
            type=TicketType.TASK,
            branch_summary="cleanup-code",
        )
        branch = ticket.safe_branch_name
        assert branch.startswith("chore/")

    def test_maintenance_branch_starts_with_refactor(self):
        """Maintenance ticket branch starts with refactor/."""
        ticket = GenericTicket(
            id="MAINT-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/MAINT-1",
            type=TicketType.MAINTENANCE,
            branch_summary="tech-debt",
        )
        branch = ticket.safe_branch_name
        assert branch.startswith("refactor/")

    def test_unknown_type_branch_starts_with_feature(self):
        """Unknown type ticket branch starts with feature/."""
        ticket = GenericTicket(
            id="U-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/U-1",
            type=TicketType.UNKNOWN,
            branch_summary="something",
        )
        branch = ticket.safe_branch_name
        assert branch.startswith("feature/")


class TestIssueTrackerProviderABC:
    """Tests for IssueTrackerProvider abstract base class."""

    def test_is_abstract_class(self):
        """IssueTrackerProvider is an ABC."""
        assert issubclass(IssueTrackerProvider, ABC)

    def test_cannot_instantiate_directly(self):
        """Cannot instantiate abstract class directly."""
        with pytest.raises(TypeError):
            IssueTrackerProvider()

    def test_requires_platform_property(self):
        """Subclass must implement platform property."""
        class IncompleteProv(IssueTrackerProvider):
            @property
            def name(self):
                return "Test"
            def can_handle(self, input_str):
                return False
            def parse_input(self, input_str):
                return None
            def fetch_ticket(self, ticket_id):
                return None
            def check_connection(self):
                return True

        with pytest.raises(TypeError):
            IncompleteProv()

    def test_requires_name_property(self):
        """Subclass must implement name property."""
        class IncompleteProv(IssueTrackerProvider):
            @property
            def platform(self):
                return Platform.JIRA
            def can_handle(self, input_str):
                return False
            def parse_input(self, input_str):
                return None
            def fetch_ticket(self, ticket_id):
                return None
            def check_connection(self):
                return True

        with pytest.raises(TypeError):
            IncompleteProv()

    def test_complete_implementation_works(self):
        """Complete implementation can be instantiated."""
        class CompleteProv(IssueTrackerProvider):
            @property
            def platform(self):
                return Platform.JIRA

            @property
            def name(self):
                return "Test Provider"

            def can_handle(self, input_str):
                return input_str.startswith("TEST-")

            def parse_input(self, input_str):
                return input_str.upper()

            def fetch_ticket(self, ticket_id):
                return GenericTicket(
                    id=ticket_id,
                    platform=Platform.JIRA,
                    url=f"https://jira.example.com/{ticket_id}",
                    title="Test ticket",
                )

            def check_connection(self):
                return (True, "Connected")

        provider = CompleteProv()
        assert provider.platform == Platform.JIRA
        assert provider.name == "Test Provider"
        assert provider.can_handle("TEST-123") is True
        assert provider.parse_input("test-1") == "TEST-1"


class TestIssueTrackerProviderGenerateBranchSummary:
    """Tests for default generate_branch_summary implementation."""

    @pytest.fixture
    def provider(self):
        """Create a test provider with default implementation."""
        class TestProvider(IssueTrackerProvider):
            @property
            def platform(self):
                return Platform.JIRA

            @property
            def name(self):
                return "Test"

            def can_handle(self, input_str):
                return True

            def parse_input(self, input_str):
                return input_str

            def fetch_ticket(self, ticket_id):
                return GenericTicket(
                    id=ticket_id,
                    platform=Platform.JIRA,
                    url=f"https://jira.example.com/{ticket_id}",
                    title="Test",
                )

            def check_connection(self):
                return (True, "Connected")

        return TestProvider()

    def test_basic_summary(self, provider):
        """Generates basic summary from title."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            title="Add user authentication",
        )
        summary = provider.generate_branch_summary(ticket)
        assert summary is not None
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_summary_lowercase(self, provider):
        """Summary is lowercase."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            title="UPPERCASE Title Here",
        )
        summary = provider.generate_branch_summary(ticket)
        assert summary == summary.lower()

    def test_summary_replaces_spaces(self, provider):
        """Spaces become hyphens in summary."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            title="Multiple Words Here",
        )
        summary = provider.generate_branch_summary(ticket)
        assert " " not in summary
        assert "-" in summary

    def test_summary_removes_special_chars(self, provider):
        """Removes special characters."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            title="Fix: issue [critical]!",
        )
        summary = provider.generate_branch_summary(ticket)
        assert ":" not in summary
        assert "[" not in summary
        assert "]" not in summary
        assert "!" not in summary

    def test_summary_truncates_long_titles(self, provider):
        """Truncates long titles."""
        ticket = GenericTicket(
            id="T-1",
            platform=Platform.JIRA,
            url="https://jira.example.com/T-1",
            title="This is a very long title " * 10,
        )
        summary = provider.generate_branch_summary(ticket)
        assert len(summary) < 60


class TestIssueTrackerProviderMethodSignatures:
    """Tests for method signatures and type hints."""

    @pytest.fixture
    def provider_class(self):
        """Return the abstract provider class."""
        return IssueTrackerProvider

    def test_can_handle_takes_string(self, provider_class):
        """can_handle method takes a string parameter."""
        import inspect
        sig = inspect.signature(provider_class.can_handle)
        params = list(sig.parameters.keys())
        assert "input_str" in params

    def test_parse_input_takes_string(self, provider_class):
        """parse_input method takes a string parameter."""
        import inspect
        sig = inspect.signature(provider_class.parse_input)
        params = list(sig.parameters.keys())
        assert "input_str" in params

    def test_fetch_ticket_takes_ticket_id(self, provider_class):
        """fetch_ticket method takes a ticket_id parameter."""
        import inspect
        sig = inspect.signature(provider_class.fetch_ticket)
        params = list(sig.parameters.keys())
        assert "ticket_id" in params

