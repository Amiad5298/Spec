"""Base classes for platform-agnostic issue tracker integration.

This module defines:
- Platform enum for supported issue tracking platforms
- TicketStatus and TicketType enums for normalized ticket states
- GenericTicket dataclass for platform-agnostic ticket representation
- IssueTrackerProvider abstract base class that all providers must implement

All platform-specific providers must implement the IssueTrackerProvider
interface, ensuring consistent behavior and enabling the Open/Closed principle.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class Platform(Enum):
    """Supported issue tracking platforms.

    Each platform has a dedicated provider that implements
    the IssueTrackerProvider interface.
    """

    JIRA = auto()
    GITHUB = auto()
    LINEAR = auto()
    AZURE_DEVOPS = auto()
    MONDAY = auto()
    TRELLO = auto()


class TicketStatus(Enum):
    """Normalized ticket statuses across platforms.

    Providers map their platform-specific statuses to these
    normalized values for consistent workflow handling.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CLOSED = "closed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class TicketType(Enum):
    """Normalized ticket types across platforms.

    Used for downstream automation such as generating semantic branch names
    (e.g., feat/, fix/, chore/) and categorizing work items.
    """

    FEATURE = "feature"  # New functionality, user stories, enhancements
    BUG = "bug"  # Defects, issues, fixes
    TASK = "task"  # General tasks, chores, housekeeping
    MAINTENANCE = "maintenance"  # Tech debt, refactoring, infrastructure
    UNKNOWN = "unknown"  # Unable to determine type


@dataclass
class GenericTicket:
    """Platform-agnostic ticket representation.

    This is the normalized data model that all platform providers
    must populate. The workflow engine only interacts with this model.

    Attributes:
        id: Unique ticket identifier (platform-specific format preserved)
        platform: Source platform
        url: Original full URL to the ticket
        title: Ticket title/summary
        description: Full description/body text
        status: Normalized status
        type: Normalized ticket type (feature, bug, task, etc.)
        assignee: Assigned user (display name or username)
        labels: List of labels/tags
        created_at: Creation timestamp
        updated_at: Last update timestamp
        branch_summary: Short summary suitable for git branch name
        full_info: Complete raw ticket information for context
        platform_metadata: Platform-specific fields for edge cases
    """

    # Core identifiers
    id: str
    platform: Platform
    url: str

    # Primary fields
    title: str = ""
    description: str = ""
    status: TicketStatus = TicketStatus.UNKNOWN
    type: TicketType = TicketType.UNKNOWN

    # Assignment
    assignee: Optional[str] = None

    # Categorization
    labels: list[str] = field(default_factory=list)

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Workflow fields
    branch_summary: str = ""
    full_info: str = ""

    # Platform-specific raw data
    platform_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_id(self) -> str:
        """Human-readable ticket ID for display."""
        return self.id

    @property
    def semantic_branch_prefix(self) -> str:
        """Get semantic branch prefix based on ticket type.

        Returns:
            Conventional prefix for git branch naming following
            conventional commits style.
        """
        prefix_map = {
            TicketType.FEATURE: "feat",
            TicketType.BUG: "fix",
            TicketType.TASK: "chore",
            TicketType.MAINTENANCE: "refactor",
            TicketType.UNKNOWN: "feature",
        }
        return prefix_map.get(self.type, "feature")

    @property
    def safe_branch_name(self) -> str:
        """Generate safe git branch name from ticket.

        Uses semantic prefix based on ticket type and sanitizes
        the branch summary for git compatibility.

        Handles edge cases:
        - GitHub-style IDs like 'owner/repo#42'
        - Special characters (/, spaces, :, etc.)
        - Disallowed git sequences (.., @{, trailing /, .lock suffix)
        - Empty branch_summary (generates from title)

        Returns:
            Git-compatible branch name like 'feat/proj-123-add-user-login'
        """
        prefix = self.semantic_branch_prefix

        # Sanitize ticket ID for git ref safety
        safe_id = self._sanitize_for_git_ref(self.id.lower())

        # Use branch_summary if available, otherwise generate from title
        summary = self.branch_summary
        if not summary and self.title:
            # Generate summary from title using same logic as IssueTrackerProvider
            summary = self.title.lower()[:50]
            summary = re.sub(r"[^a-z0-9-]", "-", summary)
            summary = re.sub(r"-+", "-", summary)
            summary = summary.strip("-")

        if summary:
            safe_summary = self._sanitize_for_git_ref(summary)
            branch = f"{prefix}/{safe_id}-{safe_summary}"
        else:
            branch = f"{prefix}/{safe_id}"

        # Final safety checks for git ref requirements
        return self._finalize_git_ref(branch)

    @staticmethod
    def _sanitize_for_git_ref(value: str) -> str:
        """Sanitize a string component for git ref name.

        Args:
            value: String to sanitize

        Returns:
            Git-safe string with problematic characters replaced
        """
        # Replace slashes, spaces, colons, #, and other problematic chars with hyphens
        result = re.sub(r"[/\s:~^?*\[\]\\@{}<>|\"'#]", "-", value)
        # Collapse multiple hyphens
        result = re.sub(r"-+", "-", result)
        # Strip leading/trailing hyphens and dots
        result = result.strip("-.")
        return result

    @staticmethod
    def _finalize_git_ref(branch: str) -> str:
        """Apply final git ref safety rules.

        Args:
            branch: Branch name to finalize

        Returns:
            Git-safe branch name
        """
        # Remove disallowed sequences
        branch = branch.replace("..", "-")
        branch = branch.replace("@{", "-")

        # Remove trailing slash
        branch = branch.rstrip("/")

        # Remove .lock suffix
        if branch.endswith(".lock"):
            branch = branch[:-5]

        # Ensure no consecutive dots after replacements
        branch = re.sub(r"\.+", ".", branch)

        # Collapse any consecutive hyphens created by replacements
        branch = re.sub(r"-+", "-", branch)

        return branch


class IssueTrackerProvider(ABC):
    """Abstract base class for issue tracker integrations.

    All platform-specific providers must implement this interface.
    This ensures consistent behavior and enables the Open/Closed principle.

    Providers should:
    - Handle all platform-specific API communication
    - Map platform statuses to TicketStatus enum
    - Map platform types to TicketType enum
    - Never call print() or input() directly (use UserInteractionInterface)
    """

    @property
    @abstractmethod
    def platform(self) -> Platform:
        """Return the platform this provider handles.

        Returns:
            The Platform enum value for this provider
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name.

        Returns:
            Display name like 'Jira', 'GitHub Issues', etc.
        """
        pass

    @abstractmethod
    def can_handle(self, input_str: str) -> bool:
        """Check if this provider can handle the given input.

        Args:
            input_str: URL or ticket ID to check

        Returns:
            True if this provider recognizes the input format
        """
        pass

    @abstractmethod
    def parse_input(self, input_str: str) -> str:
        """Parse input and extract normalized ticket ID.

        Args:
            input_str: URL or ticket ID

        Returns:
            Normalized ticket ID (e.g., "PROJECT-123", "owner/repo#42")

        Raises:
            ValueError: If input cannot be parsed
        """
        pass

    @abstractmethod
    def fetch_ticket(self, ticket_id: str) -> GenericTicket:
        """Fetch ticket details from the platform.

        This is the primary method for retrieving ticket information.
        Providers should populate as many GenericTicket fields as possible.

        Args:
            ticket_id: Normalized ticket ID from parse_input()

        Returns:
            Populated GenericTicket with all available fields

        Raises:
            AuthenticationError: If credentials are invalid
            TicketNotFoundError: If ticket doesn't exist
            RateLimitError: If API rate limit is exceeded
            IssueTrackerError: For other API errors
        """
        pass

    @abstractmethod
    def check_connection(self) -> tuple[bool, str]:
        """Verify the integration is properly configured.

        Should test API connectivity and credential validity.

        Returns:
            Tuple of (success: bool, message: str)
            - success: True if connection works
            - message: Human-readable status message
        """
        pass

    def generate_branch_summary(self, ticket: GenericTicket) -> str:
        """Generate a git-friendly branch summary.

        Default implementation - can be overridden by providers
        for platform-specific naming conventions.

        Args:
            ticket: The ticket to generate summary for

        Returns:
            Short lowercase hyphenated summary (max 50 chars)
        """
        summary = ticket.title.lower()[:50]
        # Replace non-alphanumeric with hyphens
        summary = re.sub(r"[^a-z0-9-]", "-", summary)
        # Collapse multiple hyphens
        summary = re.sub(r"-+", "-", summary)
        # Strip leading/trailing hyphens
        return summary.strip("-")

