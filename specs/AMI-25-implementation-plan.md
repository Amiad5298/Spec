# Implementation Plan: AMI-25 - Migrate CLI to Remove Jira-Specific Code and Use Platform-Agnostic Providers

**Ticket:** [AMI-25](https://linear.app/amiadspec/issue/AMI-25/migrate-cli-to-remove-jira-specific-code-and-use-platform-agnostic)
**Status:** Draft
**Date:** 2026-01-27

---

## Summary

This ticket migrates the CLI (`spec/cli.py`) from using Jira-specific code (`parse_jira_ticket()`, `JiraTicket`) to the platform-agnostic `TicketService` orchestration layer. After this migration, the CLI will support **all 6 platforms**: Jira, Linear, GitHub, Azure DevOps, Monday, and Trello.

> **⚠️ Clean-Slate Implementation:** This is a new system rollout with **no backward compatibility requirements**. All Jira-specific code will be completely removed and replaced with the new platform-agnostic implementation. There is no need for deprecation periods, feature flags, or gradual migration paths.

**Key Changes:**
- Remove `parse_jira_ticket()` and replace with `TicketService.get_ticket()`
- Remove `JiraTicket` usage and use `GenericTicket` throughout
- Add `--platform` flag for disambiguating ambiguous ticket IDs (e.g., "PROJ-123" matches both Jira and Linear)
- Add `default_platform` configuration setting for persistent platform preference
- Handle async/sync boundary (CLI is synchronous, TicketService is async)
- Update help text and prompts to be platform-agnostic
- Remove Jira-specific CLI options (e.g., `--force-jira-check`)

**Scope:**
- `spec/cli.py` - Main CLI entry point
- CLI-related tests in `tests/test_cli.py`
- Configuration updates for `default_platform` setting

**Out of Scope (handled by follow-up tickets):**
- README.md and user documentation updates → [AMI-38](https://linear.app/amiadspec/issue/AMI-38)
- Platform configuration guide → [AMI-39](https://linear.app/amiadspec/issue/AMI-39)
- End-to-end integration tests → [AMI-40](https://linear.app/amiadspec/issue/AMI-40)
- `spec --config` output updates → [AMI-42](https://linear.app/amiadspec/issue/AMI-42)
- Comprehensive user-facing string audit → [AMI-43](https://linear.app/amiadspec/issue/AMI-43)

> **Note:** Workflow engine migration is handled by [AMI-24](https://linear.app/amiadspec/issue/AMI-24). This ticket focuses exclusively on CLI entry point changes.

---

## Technical Approach

### Architecture Fit

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SPECFLOW CLI (THIS TICKET)                          │
│  spec <ticket_url_or_id> [--platform jira|linear|github|...]                    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     │ async (asyncio.run)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     TicketService (AMI-32) - Entry Point                         │
│                                                                                  │
│   async def get_ticket(input_str: str) -> GenericTicket                         │
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │  1. Platform detection (ProviderRegistry, optional --platform override) │   │
│   │  2. Input parsing (provider.parse_input)                                 │   │
│   │  3. Cache check                                                          │   │
│   │  4. Fetch (AuggieMediatedFetcher primary, DirectAPIFetcher fallback)    │   │
│   │  5. Normalize to GenericTicket                                           │   │
│   │  6. Cache and return                                                     │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    Workflow Engine (AMI-24 - Already Migrated)                   │
│                                                                                  │
│   run_spec_driven_workflow(ticket: GenericTicket, ...)                          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **TicketService as Entry Point** - All ticket fetching goes through `TicketService.get_ticket()` which returns `GenericTicket` directly.

2. **Async/Sync Boundary** - CLI uses `asyncio.run()` to bridge sync CLI framework (Typer) with async TicketService.

3. **Platform Disambiguation Strategy** (from AMI-25 comments):
   - URLs are unambiguous → use detected platform directly
   - Ambiguous IDs (e.g., "PROJ-123") follow resolution order:
     1. `--platform` flag if provided
     2. `default_platform` config setting if configured
     3. Interactive user prompt listing matching platforms

4. **Cache Integration** (from AMI-32 comments):
   - Use `create_ticket_service()` factory with explicit cache injection
   - DO NOT use deprecated `get_global_cache()`, `set_global_cache()`, `clear_global_cache()` functions

5. **DirectAPIFetcher Lifecycle** (from AMI-31 comments):
   - Use async context manager pattern for proper HTTP client cleanup
   - `TicketService` owns `DirectAPIFetcher` lifecycle

6. **6 Platform Support** (from ticket description update):
   - Jira, Linear, GitHub - AuggieMediatedFetcher (primary) + DirectAPIFetcher (fallback)
   - Azure DevOps, Monday, Trello - DirectAPIFetcher only

---

## Dependencies

### Upstream Dependencies (Must Be Complete First)

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| AMI-17 | ProviderRegistry | ✅ Complete | Platform detection and provider lookup |
| AMI-18 | JiraProvider | ✅ Complete | Jira URL/ID parsing and normalization |
| AMI-19 | GitHubProvider | ✅ Complete | GitHub URL/ID parsing and normalization |
| AMI-20 | LinearProvider | ✅ Complete | Linear URL/ID parsing and normalization |
| AMI-21 | AzureDevOps/Monday/Trello | ✅ Complete | Additional platform providers |
| AMI-23 | TicketCache | ✅ Complete | In-memory and file-based caching |
| AMI-24 | WorkflowState Migration | ✅ Complete | Workflow engine accepts GenericTicket |
| AMI-29 | TicketFetcher Protocol | ✅ Complete | Fetcher abstraction layer |
| AMI-30 | AuggieMediatedFetcher | ✅ Complete | Agent-mediated ticket fetching |
| AMI-31 | DirectAPIFetcher | ✅ Complete | Direct API fallback fetching |
| AMI-32 | TicketService | ✅ Complete | Orchestration layer |

### Integration Points

| Component | Integration Type | Notes |
|-----------|------------------|-------|
| `TicketService` (AMI-32) | Primary entry point | Replaces `parse_jira_ticket()` |
| `create_ticket_service()` | Factory function | Creates configured service with cache |
| `ProviderRegistry` (AMI-17) | Platform detection | Auto-detect from URL/ID |
| `GenericTicket` | Data model | Platform-agnostic ticket representation |
| `AuthenticationManager` (AMI-22) | Credentials | For DirectAPIFetcher fallback |
| `AuggieClient` | Agent client | For AuggieMediatedFetcher |

---

## Files Requiring Changes

### Production Code Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `spec/cli.py` | **Core Migration** | Replace `parse_jira_ticket()` with async TicketService |
| `spec/config/settings.py` | **New Setting** | Add `default_platform` configuration |
| `spec/config/__init__.py` | **Export** | Export new setting if needed |

### Test File Changes

| File | Changes Needed |
|------|----------------|
| `tests/test_cli.py` | Update mocks, add platform flag tests, add disambiguation tests |

---

## Code Changes: Before and After

### Current Code (Jira-Specific)

**File:** `spec/cli.py` (lines 459-470)

```python
from spec.integrations.jira import parse_jira_ticket
from spec.integrations.providers import GenericTicket
from spec.workflow.runner import run_spec_driven_workflow

# Parse ticket and convert to GenericTicket
# TODO(AMI-25): Replace with TicketService.get_ticket() for full platform support
jira_ticket = parse_jira_ticket(
    ticket,
    default_project=config.settings.default_jira_project,
)
```

### New Code (Platform-Agnostic)

```python
from spec.integrations import create_ticket_service
from spec.integrations.providers import GenericTicket, Platform
from spec.workflow.runner import run_spec_driven_workflow

# Fetch ticket using platform-agnostic TicketService
# Supports: Jira, Linear, GitHub, Azure DevOps, Monday, Trello
generic_ticket = asyncio.run(
    _fetch_ticket_async(
        ticket_input=ticket,
        config=config,
        platform_override=platform,  # From --platform flag
    )
)
```

---

## Implementation Steps

### Phase 1: Add Configuration Support for Default Platform

#### Step 1.1: Add default_platform Setting

**File:** `spec/config/settings.py`

Add new setting to `SpecSettings`:

```python
@dataclass
class SpecSettings:
    # ... existing settings ...

    # Platform settings (new)
    default_platform: str | None = None  # e.g., "jira", "linear", "github"

    def get_default_platform(self) -> Platform | None:
        """Get default platform as Platform enum, or None if not configured."""
        if self.default_platform is None:
            return None
        try:
            return Platform[self.default_platform.upper()]
        except KeyError:
            return None
```

### Phase 2: Add --platform CLI Flag

#### Step 2.1: Update CLI Main Function Signature

**File:** `spec/cli.py`

Add new parameter to `main()` function:

```python
@app.command()
def main(
    ticket: Annotated[...] = None,
    platform: Annotated[
        str | None,
        typer.Option(
            "--platform",
            "-p",
            help="Override platform detection (jira, linear, github, azure_devops, monday, trello)",
        ),
    ] = None,
    # ... existing parameters ...
) -> None:
```

#### Step 2.2: Validate --platform Flag

Add validation for the platform flag value:

```python
def _validate_platform(platform: str | None) -> Platform | None:
    """Validate and convert platform string to Platform enum.

    Args:
        platform: Platform name string (case-insensitive) or None

    Returns:
        Platform enum value or None if not provided

    Raises:
        typer.BadParameter: If platform string is invalid
    """
    if platform is None:
        return None

    try:
        return Platform[platform.upper()]
    except KeyError:
        valid = ", ".join(p.name.lower() for p in Platform)
        raise typer.BadParameter(
            f"Invalid platform: {platform}. Valid options: {valid}"
        )
```

### Phase 3: Create Async Ticket Fetching Function

#### Step 3.1: Implement _fetch_ticket_async()

**File:** `spec/cli.py`

```python
async def _fetch_ticket_async(
    ticket_input: str,
    config: ConfigManager,
    platform_override: Platform | None = None,
) -> GenericTicket:
    """Fetch ticket using TicketService with platform detection.

    This function handles the full ticket fetching flow:
    1. Creates TicketService with proper lifecycle management
    2. Resolves platform (override > config default > auto-detect with prompt)
    3. Fetches and returns GenericTicket

    Args:
        ticket_input: URL or ticket ID from user
        config: Configuration manager
        platform_override: Optional platform from --platform flag

    Returns:
        GenericTicket with full ticket data

    Raises:
        SpecError: On fetch failure
        UserCancelledError: If user cancels disambiguation prompt
    """
    from spec.auggie.client import AuggieClient
    from spec.integrations import create_ticket_service
    from spec.integrations.auth import AuthenticationManager
    from spec.integrations.providers import ProviderRegistry, PlatformNotSupportedError

    auggie = AuggieClient()
    auth_manager = AuthenticationManager(config)

    async with await create_ticket_service(
        auggie_client=auggie,
        auth_manager=auth_manager,
        config_manager=config,
    ) as service:
        # Handle platform resolution
        effective_input = ticket_input

        if platform_override:
            # User explicitly specified platform - use it
            effective_input = _resolve_with_platform_hint(
                ticket_input, platform_override
            )

        try:
            return await service.get_ticket(effective_input)
        except PlatformNotSupportedError as e:
            # Check if this is an ambiguous ID that needs disambiguation
            if _is_ambiguous_ticket_id(ticket_input):
                platform = _disambiguate_platform(
                    ticket_input, config
                )
                effective_input = _resolve_with_platform_hint(
                    ticket_input, platform
                )
                return await service.get_ticket(effective_input)
            raise SpecError(
                f"Could not detect platform: {e}",
                exit_code=ExitCode.INVALID_INPUT,
            ) from e
```

### Phase 4: Implement Disambiguation Logic

#### Step 4.1: Detect Ambiguous Ticket IDs

Per the AMI-25 comments, both Jira and Linear use the `PROJECT-123` format, making bare IDs ambiguous.

```python
def _is_ambiguous_ticket_id(input_str: str) -> bool:
    """Check if input is an ambiguous ticket ID (not a URL).

    URLs are unambiguous (domain identifies platform).
    Bare IDs like "PROJ-123" could be Jira or Linear.

    Args:
        input_str: URL or ticket ID

    Returns:
        True if input is a bare ID matching multiple platforms
    """
    import re

    # URLs are unambiguous
    if input_str.startswith("http://") or input_str.startswith("https://"):
        return False

    # GitHub format (owner/repo#123) is unambiguous
    if re.match(r"^[^/]+/[^#]+#\d+$", input_str):
        return False

    # PROJECT-123 format is ambiguous (Jira or Linear)
    if re.match(r"^[A-Za-z][A-Za-z0-9]*-\d+$", input_str):
        return True

    return False
```

#### Step 4.2: Implement Platform Disambiguation

```python
def _disambiguate_platform(
    ticket_input: str,
    config: ConfigManager,
) -> Platform:
    """Resolve ambiguous ticket ID to a specific platform.

    Resolution order:
    1. default_platform from config
    2. Interactive prompt asking user to choose

    Args:
        ticket_input: Ambiguous ticket ID
        config: Configuration manager

    Returns:
        Selected Platform enum

    Raises:
        UserCancelledError: If user cancels selection
    """
    from spec.integrations.providers import Platform
    from spec.ui.prompts import prompt_select
    from spec.errors import UserCancelledError

    # Check config default
    default_platform = config.settings.get_default_platform()
    if default_platform is not None:
        return default_platform

    # Interactive prompt (only Jira and Linear match PROJECT-123)
    print_info(
        f"Ticket ID '{ticket_input}' could be from multiple platforms."
    )

    options = [
        ("jira", "Jira"),
        ("linear", "Linear"),
    ]

    choice = prompt_select(
        prompt="Which platform is this ticket from?",
        options=options,
    )

    if choice is None:
        raise UserCancelledError("Platform selection cancelled")

    return Platform[choice.upper()]


def _resolve_with_platform_hint(
    ticket_input: str,
    platform: Platform,
) -> str:
    """Enhance ticket input with platform hint for TicketService.

    For bare IDs, we need to ensure TicketService uses the correct
    provider. The ProviderRegistry will detect based on input, so
    for ambiguous cases we use a platform-specific URL format.

    Args:
        ticket_input: Original ticket ID or URL
        platform: Target platform

    Returns:
        Enhanced input that ProviderRegistry will detect correctly
    """
    # If already a URL, return as-is (URLs are unambiguous)
    if ticket_input.startswith("http://") or ticket_input.startswith("https://"):
        return ticket_input

    # For bare IDs, construct a minimal platform-identifying URL
    # This ensures ProviderRegistry routes to the correct provider
    match platform:
        case Platform.JIRA:
            # Keep as-is - Jira provider handles bare IDs
            return ticket_input
        case Platform.LINEAR:
            # Linear URLs have a specific pattern
            return f"https://linear.app/team/issue/{ticket_input}"
        case Platform.GITHUB:
            # GitHub IDs are already unambiguous (owner/repo#123)
            return ticket_input
        case Platform.AZURE_DEVOPS:
            return ticket_input
        case Platform.MONDAY:
            return ticket_input
        case Platform.TRELLO:
            return ticket_input
        case _:
            return ticket_input
```

### Phase 5: Update _run_workflow() Function

#### Step 5.1: Remove parse_jira_ticket Usage

**File:** `spec/cli.py`

Replace the current Jira-specific code block:

```python
def _run_workflow(
    ticket: str,
    config: ConfigManager,
    platform: Platform | None = None,  # NEW: from --platform flag
    model: str | None = None,
    # ... rest of parameters ...
) -> None:
    """Run the AI-assisted workflow.

    Args:
        ticket: Ticket URL or ID (any supported platform)
        config: Configuration manager
        platform: Optional platform override from --platform flag
        # ... rest of docstring ...
    """
    import asyncio
    from spec.integrations.providers import GenericTicket
    from spec.workflow.runner import run_spec_driven_workflow
    from spec.workflow.state import DirtyTreePolicy, RateLimitConfig

    # Fetch ticket using platform-agnostic TicketService
    try:
        generic_ticket = asyncio.run(
            _fetch_ticket_async(
                ticket_input=ticket,
                config=config,
                platform_override=platform,
            )
        )
    except Exception as e:
        print_error(f"Failed to fetch ticket: {e}")
        raise typer.Exit(ExitCode.EXTERNAL_SERVICE_ERROR) from e

    # ... rest of function unchanged ...
```

### Phase 6: Update Help Text and Prompts

#### Step 6.1: Update Argument Help Text

Change from Jira-specific to platform-agnostic:

```python
# Before
ticket: Annotated[
    str | None,
    typer.Argument(
        help="Jira ticket ID or URL (e.g., PROJECT-123)",
    ),
] = None,

# After
ticket: Annotated[
    str | None,
    typer.Argument(
        help="Ticket ID or URL (e.g., PROJ-123, https://jira.example.com/browse/PROJ-123, "
             "https://linear.app/team/issue/ENG-456, https://github.com/owner/repo/issues/42)",
    ),
] = None,
```

#### Step 6.2: Update Main Menu Prompt

```python
# Before (in _run_main_menu)
ticket = prompt_input("Enter Jira ticket ID or URL")

# After
ticket = prompt_input("Enter ticket ID or URL")
```

#### Step 6.3: Update Docstring

```python
# Before
"""SPEC - Spec-driven development workflow using Auggie CLI.

Start a spec-driven development workflow for a Jira ticket.
If no ticket is provided, shows the interactive main menu.
"""

# After
"""SPEC - Spec-driven development workflow using Auggie CLI.

Start a spec-driven development workflow for a ticket from any
supported platform (Jira, Linear, GitHub, Azure DevOps, Monday, Trello).
If no ticket is provided, shows the interactive main menu.
"""
```

### Phase 7: Remove Jira-Specific Options

#### Step 7.1: Remove --force-jira-check Flag

This flag is no longer needed since we're using TicketService which handles all integrations:

```python
# REMOVE this parameter:
force_jira_check: Annotated[
    bool,
    typer.Option(
        "--force-jira-check",
        help="Force fresh Jira integration check",
    ),
] = False,
```

Replace with a more general option if needed:

```python
force_integration_check: Annotated[
    bool,
    typer.Option(
        "--force-integration-check",
        help="Force fresh platform integration check",
    ),
] = False,
```

#### Step 7.2: Update check_jira_integration Call

```python
# Before
check_jira_integration(config, auggie, force=force_jira_check)

# After (or remove entirely if not needed)
# Integration is now checked automatically by TicketService
```

---

## Testing Strategy

### Unit Tests

#### Test: Platform Flag Validation

```python
# tests/test_cli.py

def test_validate_platform_valid_jira():
    """Valid Jira platform string returns Platform.JIRA."""
    assert _validate_platform("jira") == Platform.JIRA
    assert _validate_platform("JIRA") == Platform.JIRA
    assert _validate_platform("Jira") == Platform.JIRA


def test_validate_platform_valid_linear():
    """Valid Linear platform string returns Platform.LINEAR."""
    assert _validate_platform("linear") == Platform.LINEAR


def test_validate_platform_none():
    """None input returns None."""
    assert _validate_platform(None) is None


def test_validate_platform_invalid():
    """Invalid platform raises BadParameter."""
    with pytest.raises(typer.BadParameter) as exc_info:
        _validate_platform("invalid")
    assert "Invalid platform" in str(exc_info.value)
```

#### Test: Ambiguous ID Detection

```python
def test_is_ambiguous_ticket_id_bare_id():
    """Bare PROJECT-123 format is ambiguous."""
    assert _is_ambiguous_ticket_id("PROJ-123") is True
    assert _is_ambiguous_ticket_id("ENG-456") is True
    assert _is_ambiguous_ticket_id("ABC-1") is True


def test_is_ambiguous_ticket_id_url():
    """URLs are not ambiguous."""
    assert _is_ambiguous_ticket_id("https://jira.example.com/browse/PROJ-123") is False
    assert _is_ambiguous_ticket_id("https://linear.app/team/issue/ENG-456") is False


def test_is_ambiguous_ticket_id_github():
    """GitHub format (owner/repo#123) is not ambiguous."""
    assert _is_ambiguous_ticket_id("owner/repo#42") is False
```

#### Test: Platform Resolution

```python
def test_resolve_with_platform_hint_jira():
    """Jira keeps bare ID as-is."""
    result = _resolve_with_platform_hint("PROJ-123", Platform.JIRA)
    assert result == "PROJ-123"


def test_resolve_with_platform_hint_linear():
    """Linear wraps in URL for detection."""
    result = _resolve_with_platform_hint("ENG-456", Platform.LINEAR)
    assert "linear.app" in result
    assert "ENG-456" in result


def test_resolve_with_platform_hint_url_passthrough():
    """URLs pass through unchanged."""
    url = "https://jira.example.com/browse/PROJ-123"
    assert _resolve_with_platform_hint(url, Platform.LINEAR) == url
```

### Integration Tests

#### Test: Full CLI Flow with Mocked TicketService

```python
@pytest.mark.asyncio
async def test_cli_main_with_platform_flag(monkeypatch):
    """CLI correctly passes --platform flag to TicketService."""
    captured_input = {}

    async def mock_get_ticket(self, input_str):
        captured_input["input"] = input_str
        return GenericTicket(
            id="PROJ-123",
            title="Test Ticket",
            description="Test description",
            platform=Platform.JIRA,
        )

    monkeypatch.setattr(TicketService, "get_ticket", mock_get_ticket)

    result = runner.invoke(app, ["PROJ-123", "--platform", "jira"])

    assert result.exit_code == 0
    assert captured_input["input"] == "PROJ-123"


@pytest.mark.asyncio
async def test_cli_fetch_linear_ticket():
    """Fetching Linear ticket works end-to-end."""
    # Uses mocked TicketService
    result = runner.invoke(app, [
        "https://linear.app/team/issue/ENG-456",
    ])
    assert result.exit_code == 0
```

### Mock Strategy

```python
@pytest.fixture
def mock_ticket_service(monkeypatch):
    """Mock TicketService for CLI testing."""

    async def mock_create(*args, **kwargs):
        class MockService:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get_ticket(self, input_str: str) -> GenericTicket:
                return GenericTicket(
                    id="MOCK-123",
                    title="Mock Ticket",
                    description="Mock description",
                    platform=Platform.JIRA,
                )

        return MockService()

    monkeypatch.setattr(
        "spec.integrations.create_ticket_service",
        mock_create,
    )
```

---

## Acceptance Criteria

### Functional Requirements

- [ ] **AC1:** CLI accepts ticket URLs and IDs from all 6 platforms (Jira, Linear, GitHub, Azure DevOps, Monday, Trello)
- [ ] **AC2:** `--platform` / `-p` flag allows explicit platform selection
- [ ] **AC3:** Invalid `--platform` values show clear error with valid options
- [ ] **AC4:** Ambiguous IDs (PROJ-123 format) prompt user if no default configured
- [ ] **AC5:** `default_platform` config setting allows setting persistent default
- [ ] **AC6:** URLs bypass disambiguation (domain is unambiguous)
- [ ] **AC7:** Help text shows platform-agnostic examples
- [ ] **AC8:** Jira-specific code (`parse_jira_ticket()`, `JiraTicket`) completely removed from CLI

### Technical Requirements (from AMI-25 and AMI-32 Comments)

- [ ] **TR1:** Uses `create_ticket_service()` factory (not deprecated global cache functions)
- [ ] **TR2:** Async context manager pattern for TicketService lifecycle
- [ ] **TR3:** Proper error handling with appropriate exit codes
- [ ] **TR4:** No import-time side effects from new imports
- [ ] **TR5:** GenericTicket passed to workflow engine (not JiraTicket)

### Quality Requirements

- [ ] **QR1:** All CLI tests pass (updated tests for new platform-agnostic implementation)
- [ ] **QR2:** Tests cover platform flag, disambiguation, and multi-platform flows
- [ ] **QR3:** Type hints complete and mypy passes
- [ ] **QR4:** No regressions in CLI startup time

---

## Estimated Effort

### Per-Phase Estimates

| Phase | Description | Estimate | Risk |
|-------|-------------|----------|------|
| Phase 1 | Configuration support for `default_platform` | 0.5 day | Low |
| Phase 2 | Add `--platform` CLI flag | 0.5 day | Low |
| Phase 3 | Async ticket fetching function | 1 day | Medium |
| Phase 4 | Disambiguation logic | 1 day | Medium |
| Phase 5 | Update `_run_workflow()` | 0.5 day | Low |
| Phase 6 | Update help text and prompts | 0.25 day | Low |
| Phase 7 | Remove Jira-specific options | 0.25 day | Low |
| Testing | Unit + integration tests | 1 day | Medium |
| **Total** | | **5 days** | **Medium** |

### Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Async/sync integration issues | High | Follow established `asyncio.run()` pattern |
| Disambiguation UX confusion | Medium | Clear prompts with platform examples |
| Cache lifecycle management | Medium | Use `create_ticket_service()` factory pattern |
| TicketService integration issues | Medium | Follow established patterns from AMI-32 |

---

## Example Usage

### Basic Usage (All Platforms)

```bash
# Jira (URL)
spec https://company.atlassian.net/browse/PROJ-123

# Jira (ID - if default_platform is jira or prompted)
spec PROJ-123

# Linear (URL)
spec https://linear.app/myteam/issue/ENG-456

# Linear (ID with explicit platform)
spec ENG-456 --platform linear

# GitHub
spec https://github.com/owner/repo/issues/42
spec owner/repo#42

# Azure DevOps
spec https://dev.azure.com/org/project/_workitems/edit/789
spec AB#789 --platform azure_devops

# Monday
spec https://company.monday.com/boards/123456/pulses/789012

# Trello
spec https://trello.com/c/abc123XY/42-card-title
```

### Disambiguation Scenarios

```bash
# Scenario 1: Ambiguous ID without --platform flag
$ spec PROJ-123

Ticket ID 'PROJ-123' could be from multiple platforms.
? Which platform is this ticket from?
> Jira
  Linear

# Scenario 2: Using --platform to avoid prompt
$ spec PROJ-123 --platform jira
✓ Fetching ticket from Jira...

# Scenario 3: Using config default
$ spec config set default_platform linear
$ spec ENG-456  # Now uses Linear without prompting
```

### Error Handling Examples

```bash
# Invalid platform
$ spec PROJ-123 --platform invalid
Error: Invalid platform: invalid. Valid options: jira, linear, github, azure_devops, monday, trello

# Ticket not found
$ spec PROJ-999
Error: Ticket 'PROJ-999' not found on Jira

# Network error with fallback
$ spec https://linear.app/team/issue/ENG-456
Warning: Primary fetcher failed, trying direct API...
✓ Fetched ticket via direct API
```

---

## References

### Related Tickets (Upstream Dependencies)

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-17](https://linear.app/amiadspec/issue/AMI-17) | ProviderRegistry | Platform detection used for routing |
| [AMI-24](https://linear.app/amiadspec/issue/AMI-24) | WorkflowState Migration | Workflow engine accepts GenericTicket |
| [AMI-32](https://linear.app/amiadspec/issue/AMI-32) | TicketService | Core orchestration layer this ticket uses |
| [AMI-31](https://linear.app/amiadspec/issue/AMI-31) | DirectAPIFetcher | Fallback fetcher lifecycle |
| [AMI-30](https://linear.app/amiadspec/issue/AMI-30) | AuggieMediatedFetcher | Primary fetcher |
| [AMI-22](https://linear.app/amiadspec/issue/AMI-22) | AuthenticationManager | Credentials for DirectAPIFetcher |

### Follow-up Tickets (Blocked by AMI-25)

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-38](https://linear.app/amiadspec/issue/AMI-38) | Update User Documentation for Multi-Platform Support | README and docs updates |
| [AMI-39](https://linear.app/amiadspec/issue/AMI-39) | Create Platform Configuration Guide | User setup documentation |
| [AMI-40](https://linear.app/amiadspec/issue/AMI-40) | Add End-to-End Integration Tests for Multi-Platform CLI | Comprehensive integration testing |
| [AMI-42](https://linear.app/amiadspec/issue/AMI-42) | Update spec --config Output for Multi-Platform Support | Config display updates |
| [AMI-43](https://linear.app/amiadspec/issue/AMI-43) | Audit and Update All User-Facing Strings | Platform-agnostic language |

### Architecture Documents

- [00_Architecture_Refactor_Spec.md](./00_Architecture_Refactor_Spec.md) - Overall architecture reference
- [AMI-32-implementation-plan.md](./AMI-32-implementation-plan.md) - TicketService design
- [AMI-24-implementation-plan.md](./AMI-24-implementation-plan.md) - Workflow engine migration

### Codebase References

| File | Purpose |
|------|---------|
| `spec/cli.py` | Main CLI entry point (this ticket modifies) |
| `spec/integrations/ticket_service.py` | TicketService implementation |
| `spec/integrations/providers/registry.py` | ProviderRegistry for platform detection |
| `spec/integrations/providers/detector.py` | PlatformDetector patterns |
| `spec/integrations/jira.py` | Contains `parse_jira_ticket()` (to be removed from CLI usage) |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-27 | AI Assistant | Initial draft created |
