"""Backend infrastructure for AI agent integrations.

This package provides a unified abstraction layer for AI backends:
- Auggie (Augment Code CLI)
- Claude (Claude Code CLI)
- Cursor (Cursor IDE)
- Aider (Aider CLI)

Modules:
- errors: Backend-related error types
- base: AIBackend protocol, BaseBackend class, and SubagentMetadata
- auggie: AuggieBackend implementation (Phase 1.5)
- factory: Backend factory for instantiation (Phase 1.6+)
"""

from ingot.integrations.backends.auggie import AuggieBackend
from ingot.integrations.backends.base import (
    AIBackend,
    BaseBackend,
    SubagentMetadata,
)
from ingot.integrations.backends.claude import ClaudeBackend
from ingot.integrations.backends.cursor import CursorBackend
from ingot.integrations.backends.errors import (
    BackendNotConfiguredError,
    BackendNotInstalledError,
    BackendRateLimitError,
    BackendTimeoutError,
)
from ingot.integrations.backends.factory import BackendFactory

# Explicit public API for IDE support and documentation.
# All exported symbols should be listed here.
__all__ = [
    # Protocol and base class
    "AIBackend",
    "BaseBackend",
    "SubagentMetadata",
    # Backend implementations
    "AuggieBackend",
    "ClaudeBackend",
    "CursorBackend",
    # Error types
    "BackendRateLimitError",
    "BackendNotInstalledError",
    "BackendNotConfiguredError",
    "BackendTimeoutError",
    # Factory
    "BackendFactory",
]
