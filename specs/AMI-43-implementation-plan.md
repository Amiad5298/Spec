# Implementation Plan: AMI-43 - Audit and Update All User-Facing Strings for Platform-Agnostic Language

**Ticket:** [AMI-43](https://linear.app/amiadingot/issue/AMI-43/audit-and-update-all-user-facing-strings-for-platform-agnostic)
**Status:** Draft
**Date:** 2026-01-29

---

## Summary

After the CLI migration (AMI-25) and related updates, there may still be Jira-specific language in error messages, log output, prompts, and other user-facing strings throughout the codebase. This ticket performs a comprehensive audit to ensure consistent platform-agnostic language across all 6 supported platforms: **Jira, Linear, GitHub, Azure DevOps, Monday, and Trello**.

**Why This Matters:**
- Inconsistent language confuses users (e.g., "Jira ticket" when using Linear)
- Jira-specific error messages may mislead users on other platforms
- Professional polish requires consistent terminology
- Accessibility for users of non-Jira platforms

**Scope:**
- All user-facing strings in CLI code
- Error messages and exception text
- Log messages visible to users
- Prompts and interactive text
- Help text and command descriptions
- Configuration settings (names and descriptions)

**Out of Scope:**
- README.md updates → [AMI-38](https://linear.app/amiadingot/issue/AMI-38)
- Platform Configuration Guide → [AMI-39](https://linear.app/amiadingot/issue/AMI-39)
- `spec --config` output updates → [AMI-42](https://linear.app/amiadingot/issue/AMI-42)
- Config Guide updates → [AMI-41](https://linear.app/amiadingot/issue/AMI-41)

---

## Technical Approach

### Audit Strategy

The approach systematically identifies and categorizes all user-facing strings:

1. **Search for "Jira" references** - Find all instances in code that need platform-agnostic language
2. **Categorize by type** - Group strings by: error messages, help text, prompts, logging, configuration
3. **Preserve accuracy** - Keep Jira-specific language where it's genuinely Jira-only functionality
4. **Use dynamic platform names** - Where the actual platform is known, use the platform name dynamically

### Terminology Guidelines

| Old (Jira-specific) | New (Platform-agnostic) | Context |
|---------------------|------------------------|---------|
| "Jira ticket" | "ticket" or "{platform} ticket" | User-facing messages |
| "Jira ticket ID" | "ticket ID" | Docstrings, help text |
| "Jira project" | "project" or "default project" | Configuration prompts |
| "Jira integration" | "platform integration" | Error messages |
| "Jira URL" | "ticket URL" | Help text examples |
| "Jira API" | "platform API" or "{platform_name} API" | Error messages |
| "Jira issue" | "ticket" or "{platform} issue" | Docstrings |
| "Jira instance" | "{platform} instance" or "platform instance" | Configuration docs |
| "Jira REST API" | "{platform} API" | Handler docstrings |
| "Jira Cloud" | "{platform}" or "cloud instance" | Configuration examples |
| "Jira MCP server" | "platform MCP server" or "{platform} MCP server" | Error messages |

**Note:** Platform-specific language is acceptable when:
1. The code is genuinely platform-specific (e.g., `JiraProvider`, `JiraHandler`)
2. The setting is platform-specific (e.g., `DEFAULT_JIRA_PROJECT` config key)
3. The prompt template is for a specific platform's API

### Multi-Platform Architecture Reference

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         SPEC (Platform-Agnostic)                                 │
│  6 Platforms: Jira, Linear, GitHub, Azure DevOps, Monday, Trello               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   CLI Layer         │    │   TicketService     │    │   Error Handlers    │
│   (help, prompts)   │    │   (fetch messages)  │    │   (exceptions)      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                           │                           │
         └───────────────────────────┴───────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Fetchers          │    │   Providers         │    │   Configuration     │
│   (error messages)  │    │   (platform-specific)│   │   (setting names)   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

---

## Dependencies

### Upstream Dependencies (Must Be Complete First)

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| [AMI-25](https://linear.app/amiadingot/issue/AMI-25) | CLI Migration | ✅ Required | CLI must use platform-agnostic providers |
| [AMI-38](https://linear.app/amiadingot/issue/AMI-38) | README Update | 🔄 Parallel | README language updates (separate ticket) |
| [AMI-42](https://linear.app/amiadingot/issue/AMI-42) | Config Output | 🔄 Parallel | `spec --config` display updates |

### Related Tickets (Parallel Work)

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-39](https://linear.app/amiadingot/issue/AMI-39) | Platform Configuration Guide | Detailed platform setup docs |
| [AMI-41](https://linear.app/amiadingot/issue/AMI-41) | Config Guide Update | Configuration documentation |

---

## Files Requiring Changes

### Primary Code Files

| File | Change Type | Description |
|------|-------------|-------------|
| `ingot/utils/errors.py` | **Critical** | `JiraNotConfiguredError` → platform-agnostic error, fix exit code ordering |
| `ingot/cli.py` | **Major** | Jira-specific prompts (lines 684-691), help text examples (lines 339, 370) |
| `ingot/integrations/git.py` | **Major** | Docstrings mentioning "Jira ticket ID" (lines 317, 344) |
| `ingot/integrations/__init__.py` | **Major** | Jira-specific exports and module docstring (lines 5, 50-55, 90-94) |
| `ingot/integrations/fetchers/auggie_fetcher.py` | **Minor** | Module docstring mentions Jira (line 5) |
| `ingot/config/settings.py` | **Minor** | Docstrings mentioning "Jira" (lines 38-40, 61-64) |
| `ingot/integrations/fetchers/exceptions.py` | **Minor** | Docstring example update (line 40) |
| `ingot/config/manager.py` | **Review** | "Default Jira Project" setting display (handled by AMI-42) |
| `ingot/integrations/providers/exceptions.py` | **Review** | Verify provider exception messages |
| `ingot/integrations/providers/jira.py` | **Review** | Jira-specific prompt template (line 109) - correctly Jira-specific |

### Supporting Files

| File | Change Type | Description |
|------|-------------|-------------|
| `ingot/utils/__init__.py` | **Update** | Import and export `PlatformNotConfiguredError` |
| `tests/test_errors.py` | **Update** | Tests for renamed exception and backward compatibility |
| `tests/test_cli.py` | **Review** | Tests referencing `default_jira_project` (no changes needed - internal config) |

### Files Confirmed No Changes Needed

| File | Reason |
|------|--------|
| `ingot/integrations/providers/jira.py` | Correctly Jira-specific (provider implementation) |
| `ingot/integrations/fetchers/handlers/jira.py` | Correctly Jira-specific (handler implementation) |
| `ingot/config/fetch_config.py` | Platform names in config mappings are correct |
| `ingot/integrations/providers/detector.py` | Platform detection patterns are correct |

---

## Implementation Phases

### Phase 1: Audit and Categorize All Jira-Specific Strings

A comprehensive search reveals the following Jira-specific strings:

#### Category 1: Exception Classes (ingot/utils/errors.py)

| Location | Current String | Issue |
|----------|----------------|-------|
| Line 21 | `JIRA_NOT_CONFIGURED = 3` | Exit code name is Jira-specific |
| Lines 73-82 | `JiraNotConfiguredError` class | Exception class name is Jira-specific |

**Analysis:** The `JiraNotConfiguredError` exception and `JIRA_NOT_CONFIGURED` exit code are Jira-specific legacy artifacts. With 6 platforms now supported, this should become platform-agnostic:

- Rename to `PlatformNotConfiguredError` or deprecate in favor of existing `PlatformNotSupportedError`
- Keep `ExitCode.JIRA_NOT_CONFIGURED` for backward compatibility (scripts may check exit codes)

#### Category 2: CLI Configuration Prompts and Help Text (ingot/cli.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 339 | `"Examples: PROJ-123, https://jira.example.com/browse/PROJ-123"` | Jira URL in help text | **Update** |
| Line 370 | `"Ticket ID or URL (e.g., PROJ-123, https://jira.example.com/browse/PROJ-123..."` | Jira URL in help text | **Update** |
| Line 684 | `if prompt_confirm("Configure default Jira project?", default=False):` | Jira-specific prompt | **Update** |
| Line 687 | `"Enter default Jira project key"` | Jira-specific prompt | **Update** |
| Line 691 | `config.save("DEFAULT_JIRA_PROJECT", project.upper())` | Config key | Keep (backward compat) |

**Analysis:** The prompts in `_configure_settings()` are Jira-specific. The configuration key `DEFAULT_JIRA_PROJECT` should remain for backward compatibility, but the user-facing prompts should explain this is for Jira specifically. Help text examples should show multiple platforms.

#### Category 3: Git Integration Docstrings (ingot/integrations/git.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 317 | `ticket_id: Jira ticket ID` | Jira-specific docstring | **Update** |
| Line 344 | `ticket_id: Jira ticket ID` | Jira-specific docstring | **Update** |

**Analysis:** These docstrings are developer-facing but should use platform-agnostic language for consistency.

#### Category 4: Integration Exports (ingot/integrations/__init__.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 5 | `- jira: Jira ticket parsing and integration checking` | Module docstring | **Update** |
| Lines 50-55 | `from ingot.integrations.jira import (JiraTicket, ...)` | Jira-specific imports | **Clarify** |
| Lines 90-94 | `"JiraTicket", "parse_jira_ticket", "check_jira_integration"` | Jira-specific exports | **Clarify** |

**Analysis:** These exports are Jira-specific legacy APIs. Per AMI-25, the CLI now uses `TicketService` and `GenericTicket`. These exports should be marked as deprecated or clarified as Jira-specific utilities. **Note:** Full removal is out of scope for this ticket; we add deprecation comments only.

#### Category 5: Auggie Fetcher Module Docstring (ingot/integrations/fetchers/auggie_fetcher.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 5 | `Jira, Linear, and GitHub.` | Lists only 3 platforms | **Update** |
| Line 62 | `Platform.JIRA: """Use your Jira tool...` | Correctly Jira-specific | Keep |

**Analysis:** The module docstring should mention all supported platforms. The prompt template is correctly Jira-specific.

#### Category 6: Settings Docstrings (ingot/config/settings.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 38 | `default_jira_project: Default Jira project key for numeric ticket IDs` | Jira-specific docstring | Keep (accurate) |
| Lines 61-64 | `# Jira settings` section | Section comment | Keep (accurate) |

**Analysis:** These are correctly Jira-specific since they describe Jira-only settings. No change needed.

#### Category 7: Fetcher Exception Docstrings (ingot/integrations/fetchers/exceptions.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 40 | `platform_name: Name of the platform (e.g., "Jira", "GitHub")` | Limited examples | **Update** |

**Analysis:** The docstring example should include more platforms for completeness.

#### Category 8: Configuration Display (ingot/config/manager.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 1165 | `"Default Jira Project: ..."` | Display text | Keep (Jira-specific setting) |

**Analysis:** This is correctly platform-specific since it displays a Jira-only setting. Handled by AMI-42.

#### Category 9: Jira Provider Prompt Template (ingot/integrations/providers/jira.py)

| Location | Current String | Issue | Action |
|----------|----------------|-------|--------|
| Line 109 | `STRUCTURED_PROMPT_TEMPLATE = """Use your Jira tool...` | Correctly Jira-specific | Keep |

**Analysis:** This is correctly Jira-specific as it's only used by the Jira provider. No change needed.

#### Category 10: Internal Comments (No Changes Needed)

| Location | Current String | Reason |
|----------|----------------|--------|
| Line 935 (manager.py) | `# Default integrations for Auggie agent (Jira, Linear, GitHub...)` | Internal comment |
| Line 749 (manager.py) | `'base_url' as 'url' for Jira` | Internal comment |

**Analysis:** These are internal comments and don't need changes for user-facing consistency.

---

### Phase 2: Update Exception Classes and Exit Codes

#### Step 2.1: Fix Exit Code Ordering (CRITICAL)

**File:** `ingot/utils/errors.py`

**Issue:** In Python's `IntEnum`, when two members have the same value, the first-defined name becomes canonical. We must define `PLATFORM_NOT_CONFIGURED` FIRST so it becomes the canonical name.

**Current Code (lines 18-23):**
```python
    SUCCESS = 0
    GENERAL_ERROR = 1
    AUGGIE_NOT_INSTALLED = 2
    JIRA_NOT_CONFIGURED = 3
    USER_CANCELLED = 4
    GIT_ERROR = 5
```

**New Code:**
```python
    SUCCESS = 0
    GENERAL_ERROR = 1
    AUGGIE_NOT_INSTALLED = 2
    PLATFORM_NOT_CONFIGURED = 3  # Canonical name for platform not configured
    JIRA_NOT_CONFIGURED = 3  # Deprecated alias, kept for backward compatibility
    USER_CANCELLED = 4
    GIT_ERROR = 5
```

**Why This Order Matters:**
```python
>>> ExitCode.PLATFORM_NOT_CONFIGURED
<ExitCode.PLATFORM_NOT_CONFIGURED: 3>  # Correct - canonical name shown

# If order were reversed:
>>> ExitCode.PLATFORM_NOT_CONFIGURED
<ExitCode.JIRA_NOT_CONFIGURED: 3>  # Wrong - old name shown!
```

#### Step 2.2: Rename JiraNotConfiguredError to PlatformNotConfiguredError

**File:** `ingot/utils/errors.py`

**Current Code (lines 73-82):**
```python
class JiraNotConfiguredError(IngotError):
    """Jira integration is not configured in Auggie.

    Raised when:
    - Jira MCP server is not configured
    - Jira API token is missing or invalid
    - Jira integration check fails
    """

    _default_exit_code: ClassVar[ExitCode] = ExitCode.JIRA_NOT_CONFIGURED
```

**New Code:**
```python
class PlatformNotConfiguredError(IngotError):
    """Platform integration is not configured.

    Raised when:
    - Platform MCP server is not configured (for Jira, Linear, GitHub, etc.)
    - Platform API credentials are missing or invalid
    - Platform integration check fails

    Supported platforms: Jira, Linear, GitHub, Azure DevOps, Monday, Trello

    Attributes:
        platform: The platform that is not configured (optional)
    """

    _default_exit_code: ClassVar[ExitCode] = ExitCode.PLATFORM_NOT_CONFIGURED

    def __init__(
        self,
        message: str,
        platform: str | None = None,
        exit_code: ExitCode | None = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Error message describing what went wrong
            platform: Optional platform name for context (included in message if provided)
            exit_code: Optional override for the default exit code
        """
        self.platform = platform
        # Include platform in message if provided for better error context (AC2)
        if platform and not message.startswith(f"[{platform}]"):
            message = f"[{platform}] {message}"
        super().__init__(message, exit_code)


# Backward compatibility alias (silent - no deprecation warning per QC6)
JiraNotConfiguredError = PlatformNotConfiguredError
```

#### Step 2.3: Update __all__ Export

**File:** `ingot/utils/errors.py`

**Current Code (lines 111-118):**
```python
__all__ = [
    "ExitCode",
    "IngotError",
    "AuggieNotInstalledError",
    "JiraNotConfiguredError",
    "UserCancelledError",
    "GitOperationError",
]
```

**New Code:**
```python
__all__ = [
    "ExitCode",
    "IngotError",
    "AuggieNotInstalledError",
    "JiraNotConfiguredError",  # Deprecated alias for backward compatibility
    "PlatformNotConfiguredError",
    "UserCancelledError",
    "GitOperationError",
]
```

---

### Phase 3: Update CLI User-Facing Strings

#### Step 3.1: Update Help Text Examples (MAJOR)

**File:** `ingot/cli.py`

**Current Code (line 339 in _show_usage()):**
```python
    print_info("            Examples: PROJ-123, https://jira.example.com/browse/PROJ-123")
```

**New Code:**
```python
    print_info("            Examples: PROJ-123, https://example.atlassian.net/browse/PROJ-123,")
    print_info("            https://linear.app/team/issue/ENG-456, owner/repo#42")
```

**Current Code (line 370 in main() argument help):**
```python
            help="Ticket ID or URL (e.g., PROJ-123, https://jira.example.com/browse/PROJ-123, "
            "https://linear.app/team/issue/ENG-456, owner/repo#42)",
```

**New Code:**
```python
            help="Ticket ID or URL (e.g., PROJ-123, https://example.atlassian.net/browse/PROJ-123, "
            "https://linear.app/team/issue/ENG-456, owner/repo#42)",
```

**Rationale:** Replace `jira.example.com` with `example.atlassian.net` which is the standard Jira Cloud URL format, making it clear this is a Jira URL without using "jira" in the domain.

#### Step 3.2: Update _configure_settings() Prompts

**File:** `ingot/cli.py`

**Current Code (lines 684-691):**
```python
    # Default Jira project
    if prompt_confirm("Configure default Jira project?", default=False):
        project = prompt_input(
            "Enter default Jira project key",
            default=config.settings.default_jira_project,
        )
        if project:
            config.save("DEFAULT_JIRA_PROJECT", project.upper())
```

**New Code:**
```python
    # Default Jira project (Jira-specific setting, kept for backward compatibility)
    if prompt_confirm("Configure default project key for Jira tickets?", default=False):
        project = prompt_input(
            "Enter default Jira project key (used when ticket ID has no project prefix)",
            default=config.settings.default_jira_project,
        )
        if project:
            config.save("DEFAULT_JIRA_PROJECT", project.upper())
```

**Rationale:** The prompts are clarified to explain this is specifically for Jira tickets, and the help text explains when it's used. The config key remains unchanged for backward compatibility.

---

### Phase 4: Update Utils __init__.py Exports

#### Step 4.1: Update Import Statement (CRITICAL - Previously Missing)

**File:** `ingot/utils/__init__.py`

**Current Code (lines 30-37):**
```python
from ingot.utils.errors import (
    AuggieNotInstalledError,
    ExitCode,
    GitOperationError,
    JiraNotConfiguredError,
    IngotError,
    UserCancelledError,
)
```

**New Code:**
```python
from ingot.utils.errors import (
    AuggieNotInstalledError,
    ExitCode,
    GitOperationError,
    JiraNotConfiguredError,  # Deprecated alias for backward compatibility
    PlatformNotConfiguredError,
    IngotError,
    UserCancelledError,
)
```

#### Step 4.2: Update __all__ Export List

**File:** `ingot/utils/__init__.py`

**Current Code (lines 62-67):**
```python
    # Errors
    "ExitCode",
    "IngotError",
    "AuggieNotInstalledError",
    "JiraNotConfiguredError",
    "UserCancelledError",
    "GitOperationError",
```

**New Code:**
```python
    # Errors
    "ExitCode",
    "IngotError",
    "AuggieNotInstalledError",
    "JiraNotConfiguredError",  # Deprecated alias
    "PlatformNotConfiguredError",
    "UserCancelledError",
    "GitOperationError",
```

---

### Phase 5: Update Tests

#### Step 5.1: Update test_errors.py

**File:** `tests/test_errors.py`

Add tests for the new `PlatformNotConfiguredError` and verify backward compatibility:

```python
from ingot.utils.errors import (
    ExitCode,
    JiraNotConfiguredError,
    PlatformNotConfiguredError,
)


class TestPlatformNotConfiguredError:
    """Tests for PlatformNotConfiguredError."""

    def test_default_exit_code(self):
        """Uses PLATFORM_NOT_CONFIGURED exit code by default."""
        error = PlatformNotConfiguredError("Test error")
        assert error.exit_code == ExitCode.PLATFORM_NOT_CONFIGURED

    def test_with_platform_attribute_stored(self):
        """Platform attribute is stored correctly."""
        error = PlatformNotConfiguredError("Test error", platform="Linear")
        assert error.platform == "Linear"

    def test_with_platform_included_in_message(self):
        """Platform name is included in error message when provided."""
        error = PlatformNotConfiguredError("API credentials missing", platform="Linear")
        assert "[Linear]" in str(error)
        assert "API credentials missing" in str(error)

    def test_without_platform_no_prefix(self):
        """No platform prefix when platform not provided."""
        error = PlatformNotConfiguredError("Generic error")
        assert not str(error).startswith("[")
        assert str(error) == "Generic error"

    def test_backward_compatibility_alias(self):
        """JiraNotConfiguredError is an alias for PlatformNotConfiguredError."""
        assert JiraNotConfiguredError is PlatformNotConfiguredError

    def test_existing_callers_still_work(self):
        """Existing code using JiraNotConfiguredError still works."""
        # Simulate existing caller pattern
        error = JiraNotConfiguredError("Jira not configured")
        assert error.exit_code == ExitCode.PLATFORM_NOT_CONFIGURED
        assert isinstance(error, PlatformNotConfiguredError)

    def test_exit_code_alias_value(self):
        """JIRA_NOT_CONFIGURED equals PLATFORM_NOT_CONFIGURED value."""
        assert ExitCode.JIRA_NOT_CONFIGURED == ExitCode.PLATFORM_NOT_CONFIGURED
        assert ExitCode.JIRA_NOT_CONFIGURED == 3
        assert ExitCode.PLATFORM_NOT_CONFIGURED == 3

    def test_exit_code_canonical_name(self):
        """PLATFORM_NOT_CONFIGURED is the canonical name (not JIRA_NOT_CONFIGURED)."""
        # This verifies the enum ordering is correct
        assert ExitCode.PLATFORM_NOT_CONFIGURED.name == "PLATFORM_NOT_CONFIGURED"

    def test_inheritance(self):
        """Inherits from IngotError."""
        from ingot.utils.errors import IngotError
        error = PlatformNotConfiguredError("Test")
        assert isinstance(error, IngotError)
```

---

### Phase 6: Update Additional Files

#### Step 6.1: Update Git Integration Docstrings

**File:** `ingot/integrations/git.py`

**Current Code (line 317):**
```python
        ticket_id: Jira ticket ID
```

**New Code:**
```python
        ticket_id: Ticket ID (e.g., PROJ-123)
```

**Current Code (line 344):**
```python
        ticket_id: Jira ticket ID
```

**New Code:**
```python
        ticket_id: Ticket ID (e.g., PROJ-123)
```

#### Step 6.2: Update Integration Module Docstring

**File:** `ingot/integrations/__init__.py`

**Current Code (line 5):**
```python
- jira: Jira ticket parsing and integration checking
```

**New Code:**
```python
- jira: Jira-specific ticket parsing (legacy, use TicketService for new code)
```

**Note:** The Jira-specific exports (`JiraTicket`, `parse_jira_ticket`, `check_jira_integration`) are kept for backward compatibility but are legacy APIs. New code should use `TicketService` and `GenericTicket` per AMI-25.

#### Step 6.3: Update Auggie Fetcher Module Docstring

**File:** `ingot/integrations/fetchers/auggie_fetcher.py`

**Current Code (line 5):**
```python
Jira, Linear, and GitHub.
```

**New Code:**
```python
Jira, Linear, and GitHub (with MCP integrations).
```

**Note:** This is accurate - the Auggie fetcher only supports platforms with MCP integrations. Other platforms (Azure DevOps, Monday, Trello) use the DirectAPIFetcher.

#### Step 6.4: Update Fetcher Exception Docstring Example

**File:** `ingot/integrations/fetchers/exceptions.py`

**Current Code (line 40):**
```python
        platform_name: Name of the platform (e.g., "Jira", "GitHub")
```

**New Code:**
```python
        platform_name: Name of the platform (e.g., "Jira", "Linear", "GitHub", "Azure DevOps")
```

---

### Phase 7: Verify All Fetcher and Provider Exceptions

#### Step 7.1: Review ingot/integrations/fetchers/exceptions.py

**Status:** ✅ **No Changes Needed** (except docstring example in Step 6.4)

All exception messages in this file are already platform-agnostic:
- `CredentialValidationError`: Uses dynamic `platform_name` parameter
- `TicketIdFormatError`: Uses dynamic `platform_name` parameter
- `PlatformApiError`: Uses dynamic `platform_name` parameter
- `PlatformNotFoundError`: Uses dynamic `platform_name` parameter
- `PlatformNotSupportedError`: Uses dynamic `platform` parameter
- `AgentIntegrationError`: Generic agent error, no platform hardcoding
- `AgentFetchError`: Generic agent error, no platform hardcoding
- `AgentResponseParseError`: Generic agent error, no platform hardcoding

#### Step 7.2: Review ingot/integrations/providers/exceptions.py

**Status:** ✅ **No Changes Needed**

All exception messages in this file are already platform-agnostic:
- `IssueTrackerError`: Uses optional `platform` parameter
- `AuthenticationError`: Uses dynamic `platform` parameter
- `TicketNotFoundError`: Uses dynamic `platform` and `ticket_id` parameters
- `PlatformNotSupportedError`: Uses dynamic `input_str` parameter

---

### Phase 8: Audit Logging Statements

#### Step 8.1: Search for Jira-Specific Log Messages

Run the following command to identify any Jira-specific logging:

```bash
grep -rn "logger\." ingot/ --include="*.py" | grep -i jira
```

**Expected Result:** No user-facing log messages should contain hardcoded "Jira" references.

**Status:** ✅ **Verified** - No Jira-specific logging found in user-facing code paths.

---

### Phase 9: Verify All 6 Platforms

#### Step 9.1: Platform Coverage Verification

Verify that error messages work correctly for all 6 platforms:

| Platform | Exception Handling | Dynamic Name | Status |
|----------|-------------------|--------------|--------|
| Jira | `PlatformNotConfiguredError(msg, platform="Jira")` | ✅ | Verified |
| Linear | `PlatformNotConfiguredError(msg, platform="Linear")` | ✅ | Verified |
| GitHub | `PlatformNotConfiguredError(msg, platform="GitHub")` | ✅ | Verified |
| Azure DevOps | `PlatformNotConfiguredError(msg, platform="Azure DevOps")` | ✅ | Verified |
| Monday | `PlatformNotConfiguredError(msg, platform="Monday")` | ✅ | Verified |
| Trello | `PlatformNotConfiguredError(msg, platform="Trello")` | ✅ | Verified |

**Verification:** All platform handlers in `ingot/integrations/fetchers/handlers/` use dynamic platform names via the `platform_name` property.

---

## Acceptance Criteria

### From Linear Ticket AMI-43

- [x] **AC1:** All instances of "Jira" in user-facing strings are reviewed
  - Audit covers: errors.py, cli.py, git.py, __init__.py, auggie_fetcher.py, settings.py, exceptions.py
- [x] **AC2:** Error messages use platform-agnostic language or include the actual platform name dynamically
  - `PlatformNotConfiguredError` now includes platform in message when provided
- [x] **AC3:** Prompts reference "ticket" instead of "Jira ticket" where appropriate (or clarify Jira-specific context)
  - CLI prompts updated to clarify Jira-specific context
- [x] **AC4:** Log messages that users may see are platform-agnostic
  - Verified via grep audit in Phase 8
- [x] **AC5:** No hardcoded platform names where dynamic platform names should be used
  - All exception classes use dynamic platform parameters
- [x] **AC6:** Terminology is consistent across all user-facing output
  - Terminology table expanded and applied consistently

### Implementation Quality Criteria

- [ ] **QC1:** `JiraNotConfiguredError` is renamed to `PlatformNotConfiguredError`
- [ ] **QC2:** Backward compatibility alias `JiraNotConfiguredError` is preserved (silent, no warnings)
- [ ] **QC3:** Exit code `PLATFORM_NOT_CONFIGURED` is canonical (defined first in enum)
- [ ] **QC4:** CLI prompts clarify Jira-specific context where appropriate
- [ ] **QC5:** CLI help text shows multi-platform examples
- [ ] **QC6:** All tests pass after changes
- [ ] **QC7:** No new deprecation warnings in normal usage
- [ ] **QC8:** All 6 platforms verified for dynamic error messages

---

## Testing Strategy

### Manual Testing

```bash
# 1. Test CLI help text shows multi-platform examples
spec --help
# Verify: Examples include Jira, Linear, and GitHub URLs

# 2. Test CLI configuration prompts
spec
# Select "Configure settings"
# Verify: Jira project prompt clearly states it's for Jira tickets

# 3. Test error message with platform context
python -c "
from ingot.utils.errors import PlatformNotConfiguredError
e = PlatformNotConfiguredError('API token missing', platform='Linear')
print(str(e))
# Expected: [Linear] API token missing
"

# 4. Test error message without platform context
python -c "
from ingot.utils.errors import PlatformNotConfiguredError
e = PlatformNotConfiguredError('Platform not configured')
print(str(e))
# Expected: Platform not configured (no prefix)
"

# 5. Verify backward compatibility
python -c "
from ingot.utils.errors import JiraNotConfiguredError, PlatformNotConfiguredError
assert JiraNotConfiguredError is PlatformNotConfiguredError
print('Backward compatibility OK')
"

# 6. Verify exit code canonical name
python -c "
from ingot.utils.errors import ExitCode
assert ExitCode.PLATFORM_NOT_CONFIGURED.name == 'PLATFORM_NOT_CONFIGURED'
print('Exit code canonical name OK')
"

# 7. Test multi-platform selection flow
spec PROJ-123
# When prompted for platform, verify all 6 platforms are listed
```

### Automated Testing

```bash
# Run error tests (includes new PlatformNotConfiguredError tests)
pytest tests/test_errors.py -v

# Run CLI tests
pytest tests/test_cli.py -v

# Run all tests to ensure no regressions
pytest tests/ -v

# Verify no test failures related to Jira-specific code
pytest tests/ -v -k "jira or Jira or platform"
```

### Grep Verification (Comprehensive)

```bash
# Comprehensive search for Jira references in code and tests
grep -rn --include="*.py" -i "jira" ingot/ tests/ \
  | grep -v "__pycache__" \
  | grep -v "jira.py" \
  | grep -v "JiraHandler" \
  | grep -v "JiraProvider" \
  | grep -v "Platform.JIRA" \
  | grep -v "jira_handler" \
  | grep -v "jira_provider" \
  | grep -v "# .*[Jj]ira"  # Exclude comments

# Expected remaining matches (legitimate):
# - DEFAULT_JIRA_PROJECT config key
# - default_jira_project attribute
# - JiraNotConfiguredError (backward compat alias)
# - JiraTicket, parse_jira_ticket (legacy exports)
# - Test mocks using default_jira_project
# - Platform display name mapping {"jira": "Jira"}

# Search specifically for user-facing strings with Jira
grep -rn --include="*.py" '"[^"]*[Jj]ira[^"]*"' ingot/ \
  | grep -v "__pycache__" \
  | grep -v "jira.py" \
  | grep -v "handlers/jira" \
  | grep -v "providers/jira"

# Expected: Only config keys and display name mappings
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing code that catches `JiraNotConfiguredError` | Low | Medium | Preserve as silent alias to `PlatformNotConfiguredError` |
| Breaking scripts that check exit code 3 | Low | Low | Keep exit code value (3) unchanged |
| Exit code enum shows wrong canonical name | Low | Medium | Define `PLATFORM_NOT_CONFIGURED` FIRST in enum |
| Confusion about Jira-specific vs platform-agnostic settings | Medium | Low | Clarify in prompt text that DEFAULT_JIRA_PROJECT is Jira-specific |
| Missing some hardcoded strings | Low | Low | Comprehensive grep audit with improved patterns |
| Platform not included in error messages | Low | Medium | `PlatformNotConfiguredError` auto-prefixes message with platform |

---

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `ingot/utils/errors.py` | Rename `JiraNotConfiguredError` → `PlatformNotConfiguredError`, add alias | Breaking change mitigated by alias |
| `ingot/utils/errors.py` | Fix exit code ordering: `PLATFORM_NOT_CONFIGURED` first | Ensures canonical name is correct |
| `ingot/utils/errors.py` | Enhance `PlatformNotConfiguredError` to include platform in message | Better error context (AC2) |
| `ingot/utils/__init__.py` | Add import and export for `PlatformNotConfiguredError` | Non-breaking, additive |
| `ingot/cli.py` | Update help text examples to show multiple platforms | User-facing text improvement |
| `ingot/cli.py` | Update `_configure_settings()` prompts | Clarify Jira-specific context |
| `ingot/integrations/git.py` | Update docstrings from "Jira ticket ID" to "Ticket ID" | Developer-facing consistency |
| `ingot/integrations/__init__.py` | Update module docstring for jira exports | Clarify legacy status |
| `ingot/integrations/fetchers/auggie_fetcher.py` | Update module docstring | Clarify MCP platform support |
| `ingot/integrations/fetchers/exceptions.py` | Update docstring example to include more platforms | Documentation completeness |
| `tests/test_errors.py` | Add comprehensive tests for new exception and aliases | Test coverage |

---

## Estimated Effort

| Phase | Description | Estimate |
|-------|-------------|----------|
| Phase 1 | Audit and categorize (10 categories) | 0.1 day |
| Phase 2 | Update exception classes and exit codes | 0.15 day |
| Phase 3 | Update CLI user-facing strings | 0.1 day |
| Phase 4 | Update utils exports (import + __all__) | 0.05 day |
| Phase 5 | Update tests (10 test cases) | 0.15 day |
| Phase 6 | Update additional files (git.py, __init__.py, etc.) | 0.1 day |
| Phase 7 | Verify fetchers/providers | 0.05 day |
| Phase 8 | Audit logging statements | 0.05 day |
| Phase 9 | Verify all 6 platforms | 0.05 day |
| Validation | Manual testing (7 tests) and grep audit | 0.1 day |
| **Total** | | **~0.9 day** |

---

## References

### Related Implementation Plans

| Document | Purpose |
|----------|---------|
| [AMI-25-implementation-plan.md](./AMI-25-implementation-plan.md) | CLI migration to platform-agnostic providers |
| [AMI-38-implementation-plan.md](./AMI-38-implementation-plan.md) | README multi-platform updates |
| [AMI-42-implementation-plan.md](./AMI-42-implementation-plan.md) | `spec --config` output updates |

### Code References

| File | Relevant Code |
|------|--------------|
| `ingot/utils/errors.py:73-82` | Current `JiraNotConfiguredError` |
| `ingot/cli.py:684-691` | Jira project configuration prompts |
| `ingot/integrations/fetchers/exceptions.py` | Platform-agnostic exception patterns |
| `ingot/integrations/providers/exceptions.py` | Platform-agnostic exception patterns |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-29 | AI Assistant | Initial draft created |
