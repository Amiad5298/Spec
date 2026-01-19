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


def sanitize_for_branch_component(value: str) -> str:
    """Sanitize a string component for use in git branch names.

    This is the core sanitizer that ensures output contains only git-safe
    characters: lowercase letters, digits, and hyphens.

    Steps:
    1. Lowercase the input
    2. Replace any character not in [a-z0-9-] with hyphen
    3. Collapse multiple consecutive hyphens
    4. Strip leading/trailing hyphens
    5. Handle empty result gracefully

    Args:
        value: The string to sanitize

    Returns:
        A git-safe string containing only [a-z0-9-]
    """
    if not value:
        return ""
    # Lowercase first
    result = value.lower()
    # Replace any non-[a-z0-9-] with hyphens
    result = re.sub(r"[^a-z0-9-]", "-", result)
    # Collapse multiple hyphens
    result = re.sub(r"-+", "-", result)
    # Strip leading/trailing hyphens
    result = result.strip("-")
    return result


def sanitize_title_for_branch(title: str, max_length: int = 50) -> str:
    """Sanitize a title string for use in git branch names.

    Converts title to lowercase, replaces non-alphanumeric characters
    with hyphens, collapses consecutive hyphens, and strips leading/trailing
    hyphens. Ensures output does not end with a hyphen after truncation.

    Args:
        title: The title to sanitize
        max_length: Maximum length of the output (default: 50)

    Returns:
        A git-friendly branch summary string (max `max_length` chars,
        no trailing hyphens)
    """
    # Truncate first, then sanitize to get consistent behavior
    truncated = title[:max_length]
    result = sanitize_for_branch_component(truncated)
    # Ensure truncation didn't leave trailing hyphens
    return result.rstrip("-")


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

    # Default max length for branch summary (same as sanitize_title_for_branch)
    _BRANCH_SUMMARY_MAX_LENGTH: int = 50

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
        - Empty sanitized ticket ID (uses deterministic fallback)
        - Long branch_summary (truncated to max 50 chars)

        Output is deterministic, lowercase, and contains only git-safe
        characters: [a-z0-9/-] (slash only in prefix separator).

        Guarantees:
        - Never returns just prefix without ticket component
        - Always has format: prefix/id or prefix/id-summary
        - Maximum summary length is enforced

        Returns:
            Git-compatible branch name like 'feat/proj-123-add-user-login'
        """
        prefix = self.semantic_branch_prefix

        # Sanitize ticket ID using shared sanitizer (ensures [a-z0-9-] only)
        safe_id = sanitize_for_branch_component(self.id)

        # Handle empty sanitized ID (e.g., ticket ID was only emojis/special chars)
        if not safe_id:
            safe_id = self._generate_fallback_id()

        # Use branch_summary if available, otherwise generate from title
        summary = self.branch_summary
        if summary:
            # Apply max length limit to user-provided summary
            safe_summary = sanitize_title_for_branch(
                summary, max_length=self._BRANCH_SUMMARY_MAX_LENGTH
            )
        elif self.title:
            safe_summary = sanitize_title_for_branch(self.title)
        else:
            safe_summary = ""

        # Build branch name
        if safe_summary:
            branch = f"{prefix}/{safe_id}-{safe_summary}"
        else:
            branch = f"{prefix}/{safe_id}"

        # Final safety checks for git ref requirements
        return self._finalize_git_ref(branch)

    def _generate_fallback_id(self) -> str:
        """Generate a deterministic fallback ID when sanitized ticket ID is empty.

        Uses a short hash of the original ticket ID to maintain determinism
        and avoid collisions.

        Returns:
            Fallback ID string like 'ticket-a1b2c3'
        """
        import hashlib

        # Create deterministic hash from original ID
        id_hash = hashlib.sha256(self.id.encode("utf-8")).hexdigest()[:6]
        return f"ticket-{id_hash}"

    @staticmethod
    def _finalize_git_ref(branch: str) -> str:
        """Apply final git ref safety rules.

        Handles sequences that are invalid in git refs even when individual
        characters are valid: consecutive dots, @{ sequences, .lock suffix,
        trailing slashes.

        Args:
            branch: Branch name to finalize

        Returns:
            Git-safe branch name
        """
        # Remove disallowed sequences (these can't appear with new sanitizer
        # but kept for safety)
        branch = branch.replace("..", "-")
        branch = branch.replace("@{", "-")

        # Remove trailing slash
        branch = branch.rstrip("/")

        # Remove .lock suffix
        if branch.endswith(".lock"):
            branch = branch[:-5]

        # Collapse any consecutive hyphens created by replacements
        branch = re.sub(r"-+", "-", branch)

        # Strip any trailing hyphens that might result
        branch = branch.rstrip("-")

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
        return sanitize_title_for_branch(ticket.title)

