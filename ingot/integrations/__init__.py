"""External integrations for INGOT.

This package contains:
- git: Git operations (branch management, commits, etc.)
- auggie: Auggie CLI wrapper and model management
- auth: Authentication management for fallback credentials
"""

from ingot.integrations.auggie import (
    AuggieClient,
    AuggieModel,
    check_auggie_installed,
    get_auggie_version,
    install_auggie,
    list_models,
    version_gte,
)
from ingot.integrations.auth import (
    AuthenticationManager,
    PlatformCredentials,
)
from ingot.integrations.cache import (
    CacheConfigurationError,
    CachedTicket,
    CacheKey,
    FileBasedTicketCache,
    InMemoryTicketCache,
    TicketCache,
)
from ingot.integrations.git import (
    DirtyStateAction,
    add_to_gitignore,
    branch_exists,
    checkout_branch,
    create_branch,
    create_checkpoint_commit,
    get_current_branch,
    get_current_commit,
    get_status_short,
    handle_dirty_state,
    is_dirty,
    is_git_repo,
    squash_commits,
)
from ingot.integrations.ticket_service import (
    TicketService,
    create_ticket_service,
)

# Note: INGOT_AGENT_* constants are NOT re-exported here to avoid
# circular imports. Import them directly from ingot.workflow.constants.

__all__ = [
    # Authentication
    "AuthenticationManager",
    "PlatformCredentials",
    # Cache
    "CacheKey",
    "CachedTicket",
    "CacheConfigurationError",
    "TicketCache",
    "InMemoryTicketCache",
    "FileBasedTicketCache",
    # Git
    "DirtyStateAction",
    "is_git_repo",
    "is_dirty",
    "get_current_branch",
    "get_current_commit",
    "get_status_short",
    "handle_dirty_state",
    "create_branch",
    "branch_exists",
    "checkout_branch",
    "add_to_gitignore",
    "create_checkpoint_commit",
    "squash_commits",
    # Auggie
    "AuggieModel",
    "AuggieClient",
    "version_gte",
    "get_auggie_version",
    "check_auggie_installed",
    "install_auggie",
    "list_models",
    # TicketService
    "TicketService",
    "create_ticket_service",
]
