# Implementation Plan: AMI-42 - Update spec --config Output for Multi-Platform Support

**Ticket:** [AMI-42](https://linear.app/amiadingot/issue/AMI-42/update-spec-config-output-for-multi-platform-support)
**Status:** Draft
**Date:** 2026-01-29

---

## Summary

The current `spec --config` command output is Jira-centric and doesn't reflect the multi-platform architecture. SPEC now supports **6 ticket platforms** (Jira, Linear, GitHub, Azure DevOps, Monday, Trello), but the config display shows only:

- `Default Jira Project` setting
- No visibility into which platforms are configured
- No display of `DEFAULT_PLATFORM` setting
- No indication of agent integration status per platform
- No visibility into fallback credential configuration status

**Problem Statement:**
Users cannot verify their multi-platform configuration is correct. When debugging credential issues, they have no visibility into which platforms are ready to use versus which need additional configuration.

**Why This Matters:**
- Azure DevOps, Monday, and Trello **require** fallback credentials (no Auggie integration)
- Users need to see at-a-glance which platforms are configured and ready
- The `DEFAULT_PLATFORM` setting is critical for ambiguous ticket IDs but not displayed
- Debugging misconfigured platforms is frustrating without visibility

---

## Technical Approach

### Current Implementation

The `ConfigManager.show()` method in `ingot/config/manager.py` (lines 883-915) displays configuration using Rich formatting, but is Jira-centric:

```python
def show(self) -> None:
    """Display current configuration using Rich formatting."""
    print_header("Current Configuration")

    # ... config file locations ...

    console.print(f"  Default Jira Project: {s.default_jira_project or '(not set)'}")
    # ... other settings ...
```

### New Implementation

Update `ConfigManager.show()` to display:

1. **Platform Settings Section**
   - `DEFAULT_PLATFORM` setting (currently hidden)
   - `Default Jira Project` (preserved for backward compatibility)

2. **Platform Status Table**
   - All 6 platforms with their configuration status
   - Agent integration status per platform (✅/❌)
   - Fallback credential status per platform (✅/❌)
   - Overall "ready to use" status

3. **Architecture Reference**

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           spec --config OUTPUT                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Config File Locations                                                          │
│  ├── Global: ~/.ingot-config                                                     │
│  └── Local: .ingot (if found)                                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Platform Settings                                                               │
│  ├── Default Platform: jira  (or "(not set)")                                   │
│  └── Default Jira Project: PROJ  (legacy, kept for compatibility)              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Platform Configuration Status                                                   │
│  ┌──────────────┬──────────────┬──────────────┬──────────────┐                 │
│  │ Platform     │ Agent MCP    │ Fallback     │ Ready        │                 │
│  ├──────────────┼──────────────┼──────────────┼──────────────┤                 │
│  │ Jira         │ ✅           │ ✅           │ ✅           │                 │
│  │ Linear       │ ✅           │ ❌           │ ✅           │                 │
│  │ GitHub       │ ✅           │ ❌           │ ✅           │                 │
│  │ Azure DevOps │ ❌           │ ✅           │ ✅           │                 │
│  │ Monday       │ ❌           │ ❌           │ ❌           │                 │
│  │ Trello       │ ❌           │ ❌           │ ❌           │                 │
│  └──────────────┴──────────────┴──────────────┴──────────────┘                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ... existing sections (Models, Parallel Execution, Subagents) ...             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Upstream Dependencies

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| AMI-25 | CLI Migration | ✅ Required | Multi-platform CLI with `--platform` flag |
| AMI-22 | AuthenticationManager | ✅ Required | `has_fallback_configured()` method for checking credentials |
| AMI-33 | Fetch Config | ✅ Required | `AgentConfig` with integration status per platform |

### Related Tickets

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-25](https://linear.app/amiadingot/issue/AMI-25) | CLI Migration | Added `DEFAULT_PLATFORM` setting |
| [AMI-33](https://linear.app/amiadingot/issue/AMI-33) | Fetch Configuration | Agent integration settings |
| [AMI-38](https://linear.app/amiadingot/issue/AMI-38) | README Update | References `spec --config` |
| [AMI-39](https://linear.app/amiadingot/issue/AMI-39) | Platform Config Guide | Documents verification via `spec --config` |
| [AMI-41](https://linear.app/amiadingot/issue/AMI-41) | Config Guide Update | References `spec --config` output |
| [AMI-43](https://linear.app/amiadingot/issue/AMI-43) | String Audit | Related user-facing text updates |

---

## Files Requiring Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `ingot/config/manager.py` | **Major Update** | Update `show()` method (lines 883-915) |
| `tests/test_config_manager.py` | **Update** | Update test for `show()` method |

### Import Requirements

The helper methods will use lazy imports to avoid circular dependencies. The following imports are used inside the helper methods:

```python
# In _get_agent_integrations():
from ingot.config.fetch_config import KNOWN_PLATFORMS

# In _get_fallback_status():
from ingot.config.fetch_config import KNOWN_PLATFORMS
from ingot.integrations.auth import AuthenticationManager
from ingot.integrations.providers import Platform

# In _show_platform_status():
from ingot.config.fetch_config import KNOWN_PLATFORMS
from rich.table import Table
```

**Note:** These imports are placed inside the methods (lazy imports) to avoid import cycles between `manager.py` and `auth.py`. The `get_agent_config()` method already exists in `ConfigManager` (from AMI-33) and is used to get dynamic integration status.

---

## Code Changes: Before and After

### Before (Current Output)

```
════════════════ Current Configuration ════════════════
Global config: /Users/user/.ingot-config
Local config:  /path/to/project/.ingot

  Default Model (Legacy): (not set)
  Planning Model: claude-sonnet-4-20250514
  Implementation Model: claude-sonnet-4-20250514
  Default Jira Project: PROJ
  Auto-open Files: True
  Preferred Editor: (auto-detect)
  Skip Clarification: False
  Squash Commits at End: True

  Parallel Execution:
    Enabled: True
    Max Parallel Tasks: 4
    Fail Fast: True

  Subagents:
    Planner: .augment/agents/ingot-planner.md
    Tasklist: .augment/agents/ingot-tasklist-refiner.md
    Implementer: .augment/agents/ingot-implementer.md
    Reviewer: .augment/agents/ingot-reviewer.md
```

### After (New Output)

```
════════════════ Current Configuration ════════════════
Global config: /Users/user/.ingot-config
Local config:  /path/to/project/.ingot

  Platform Settings:
    Default Platform: jira
    Default Jira Project: PROJ

  Platform Status:
    ┌──────────────┬───────────────┬──────────────┬────────────────┐
    │ Platform     │ Agent Support │ Credentials  │ Status         │
    ├──────────────┼───────────────┼──────────────┼────────────────┤
    │ Jira         │ ✅ Yes        │ ✅ Configured│ ✅ Ready       │
    │ Linear       │ ✅ Yes        │ ❌ None      │ ✅ Ready       │
    │ GitHub       │ ✅ Yes        │ ❌ None      │ ✅ Ready       │
    │ Azure DevOps │ ❌ No         │ ✅ Configured│ ✅ Ready       │
    │ Monday       │ ❌ No         │ ❌ None      │ ❌ Needs Config│
    │ Trello       │ ❌ No         │ ❌ None      │ ❌ Needs Config│
    └──────────────┴───────────────┴──────────────┴────────────────┘

  Tip: See docs/platform-configuration.md for credential setup

  Model Settings:
    Default Model (Legacy): (not set)
    Planning Model: claude-sonnet-4-20250514
    Implementation Model: claude-sonnet-4-20250514

  ... (remaining sections unchanged) ...
```

---

## Implementation Phases

### Phase 1: Add Platform Status Helper Methods

#### Step 1.1: Create Helper Method for Agent Integration Status

Add a helper method to determine which platforms have agent integration by reading from `AgentConfig` (per AMI-33 architecture):

```python
# In ConfigManager class, add after line 882

def _get_agent_integrations(self) -> dict[str, bool]:
    """Get agent integration status for all platforms.

    Reads from AgentConfig which is populated from AGENT_INTEGRATION_* config keys.
    Falls back to default Auggie integrations if no explicit config is set.

    Returns:
        Dict mapping platform names to their agent integration status.
    """
    from ingot.config.fetch_config import KNOWN_PLATFORMS

    agent_config = self.get_agent_config()

    # Default integrations for Auggie agent (Jira, Linear, GitHub have MCP integrations)
    default_integrations = {"jira", "linear", "github"}

    result = {}
    for platform in KNOWN_PLATFORMS:
        # Check explicit config first, then fall back to defaults for Auggie
        if agent_config.integrations:
            result[platform] = agent_config.supports_platform(platform)
        else:
            # No explicit config - use Auggie defaults
            result[platform] = platform in default_integrations

    return result
```

**Note:** This uses `AgentConfig.supports_platform()` from AMI-33 to check explicit `AGENT_INTEGRATION_*` config keys. If no integrations are explicitly configured, it falls back to the default Auggie integrations (Jira, Linear, GitHub).

#### Step 1.2: Create Helper Method for Fallback Credential Status

Add a helper method to check fallback credentials:

```python
def _get_fallback_status(self) -> dict[str, bool]:
    """Get fallback credential status for all platforms.

    Returns:
        Dict mapping platform names to whether fallback credentials are configured.
    """
    from ingot.config.fetch_config import KNOWN_PLATFORMS
    from ingot.integrations.auth import AuthenticationManager
    from ingot.integrations.providers import Platform

    auth = AuthenticationManager(self)
    result = {}
    for platform_name in KNOWN_PLATFORMS:
        try:
            platform_enum = Platform[platform_name.upper()]
            result[platform_name] = auth.has_fallback_configured(platform_enum)
        except (KeyError, Exception):
            # Unknown platform or error checking - mark as not configured
            result[platform_name] = False

    return result
```

#### Step 1.3: Create Helper Method for Platform Ready Status

Add a helper to compute "ready to use" status:

```python
def _get_platform_ready_status(
    self,
    agent_integrations: dict[str, bool],
    fallback_status: dict[str, bool],
) -> dict[str, bool]:
    """Determine if each platform is ready to use.

    A platform is ready if:
    - It has agent integration, OR
    - It has fallback credentials configured

    Args:
        agent_integrations: Dict of agent integration status per platform
        fallback_status: Dict of fallback credential status per platform

    Returns:
        Dict mapping platform names to ready status
    """
    from ingot.config.fetch_config import KNOWN_PLATFORMS

    return {
        p: agent_integrations.get(p, False) or fallback_status.get(p, False)
        for p in KNOWN_PLATFORMS
    }
```

### Phase 2: Update show() Method

#### Step 2.1: Update show() to Display Platform Settings

**Location:** `ingot/config/manager.py` lines 895-904

**Current Code (lines 895-904):**
```python
        s = self.settings
        console.print(f"  Default Model (Legacy): {s.default_model or '(not set)'}")
        console.print(f"  Planning Model: {s.planning_model or '(not set)'}")
        console.print(f"  Implementation Model: {s.implementation_model or '(not set)'}")
        console.print(f"  Default Jira Project: {s.default_jira_project or '(not set)'}")
        console.print(f"  Auto-open Files: {s.auto_open_files}")
        console.print(f"  Preferred Editor: {s.preferred_editor or '(auto-detect)'}")
        console.print(f"  Skip Clarification: {s.skip_clarification}")
        console.print(f"  Squash Commits at End: {s.squash_at_end}")
        console.print()
```

**New Code:**
```python
        s = self.settings

        # Platform Settings section (NEW)
        console.print("  [bold]Platform Settings:[/bold]")
        console.print(f"    Default Platform: {s.default_platform or '(not set)'}")
        console.print(f"    Default Jira Project: {s.default_jira_project or '(not set)'}")
        console.print()

        # Platform Status table (NEW)
        self._show_platform_status()

        # Model Settings section (reorganized)
        console.print("  [bold]Model Settings:[/bold]")
        console.print(f"    Default Model (Legacy): {s.default_model or '(not set)'}")
        console.print(f"    Planning Model: {s.planning_model or '(not set)'}")
        console.print(f"    Implementation Model: {s.implementation_model or '(not set)'}")
        console.print()

        # General Settings section (reorganized)
        console.print("  [bold]General Settings:[/bold]")
        console.print(f"    Auto-open Files: {s.auto_open_files}")
        console.print(f"    Preferred Editor: {s.preferred_editor or '(auto-detect)'}")
        console.print(f"    Skip Clarification: {s.skip_clarification}")
        console.print(f"    Squash Commits at End: {s.squash_at_end}")
        console.print()
```

#### Step 2.2: Add Platform Status Display Method

Add a new method to display the platform status table with error handling:

```python
# Platform display names - maps internal names to user-friendly display names
PLATFORM_DISPLAY_NAMES: dict[str, str] = {
    "jira": "Jira",
    "linear": "Linear",
    "github": "GitHub",
    "azure_devops": "Azure DevOps",
    "monday": "Monday",
    "trello": "Trello",
}

def _show_platform_status(self) -> None:
    """Display platform configuration status as a Rich table.

    Handles errors gracefully - if status cannot be determined,
    displays an error message instead of crashing.
    """
    from ingot.config.fetch_config import KNOWN_PLATFORMS

    try:
        from rich.table import Table

        # Get status for all platforms
        agent_integrations = self._get_agent_integrations()
        fallback_status = self._get_fallback_status()
        ready_status = self._get_platform_ready_status(agent_integrations, fallback_status)

        # Create table
        table = Table(title=None, show_header=True, header_style="bold")
        table.add_column("Platform", style="cyan")
        table.add_column("Agent Support")
        table.add_column("Credentials")
        table.add_column("Status")

        for platform in KNOWN_PLATFORMS:
            display_name = PLATFORM_DISPLAY_NAMES.get(platform, platform.title())
            agent = "✅ Yes" if agent_integrations.get(platform, False) else "❌ No"
            creds = "✅ Configured" if fallback_status.get(platform, False) else "❌ None"

            if ready_status.get(platform, False):
                status = "[green]✅ Ready[/green]"
            else:
                status = "[yellow]❌ Needs Config[/yellow]"

            table.add_row(display_name, agent, creds, status)

        console.print("  [bold]Platform Status:[/bold]")
        console.print(table)

        # Show hint for unconfigured platforms
        unconfigured = [p for p, ready in ready_status.items() if not ready]
        if unconfigured:
            console.print()
            console.print(
                "  [dim]Tip: See docs/platform-configuration.md for credential setup[/dim]"
            )
        console.print()

    except Exception as e:
        # Graceful fallback if platform status cannot be displayed
        console.print("  [bold]Platform Status:[/bold]")
        console.print(f"  [dim]Unable to display platform status: {e}[/dim]")
        console.print()
```

**Note:** The `PLATFORM_DISPLAY_NAMES` constant should be defined at module level or within the class. The method uses `KNOWN_PLATFORMS` from `fetch_config.py` to iterate over platforms, ensuring consistency if new platforms are added.

### Phase 3: Update Tests

#### Step 3.1: Update test_show_displays_settings Test

**Location:** `tests/test_config_manager.py` (around line 276-289)

Update the test to verify new platform status display:

```python
@patch("ingot.config.manager.print_header")
@patch("ingot.config.manager.print_info")
@patch("ingot.config.manager.console")
def test_show_displays_settings(self, mock_console, mock_info, mock_header, temp_config_file):
    """Shows all settings including platform status from config file."""
    manager = ConfigManager(temp_config_file)
    manager.load()

    manager.show()

    mock_header.assert_called_once()
    # Should print platform settings, platform status table, and other sections
    assert mock_console.print.call_count >= 10  # Increased from 5

    # Verify platform settings are displayed
    print_calls = [str(call) for call in mock_console.print.call_args_list]
    assert any("Platform Settings" in str(call) for call in print_calls)
    assert any("Default Platform" in str(call) for call in print_calls)
```

#### Step 3.2: Add Test for Platform Status Table

Add a new test specifically for platform status display:

```python
@patch("ingot.config.manager.print_header")
@patch("ingot.config.manager.print_info")
@patch("ingot.config.manager.console")
def test_show_displays_platform_status_table(
    self, mock_console, mock_info, mock_header, temp_config_file
):
    """Shows platform configuration status table."""
    manager = ConfigManager(temp_config_file)
    manager.load()

    manager.show()

    # Verify Rich Table was printed (for platform status)
    from rich.table import Table
    table_printed = any(
        isinstance(call.args[0], Table)
        for call in mock_console.print.call_args_list
        if call.args
    )
    assert table_printed, "Platform status table should be displayed"
```

#### Step 3.3: Add Tests for Helper Methods

Add unit tests for the new helper methods:

```python
class TestPlatformStatusHelpers:
    """Tests for platform status helper methods."""

    def test_get_agent_integrations_uses_agent_config(self, temp_config_file):
        """Returns integration status from AgentConfig."""
        manager = ConfigManager(temp_config_file)
        manager.load()

        integrations = manager._get_agent_integrations()

        # Should return dict with all known platforms
        from ingot.config.fetch_config import KNOWN_PLATFORMS
        assert set(integrations.keys()) == KNOWN_PLATFORMS

        # Default Auggie integrations: jira, linear, github are True
        assert integrations["jira"] is True
        assert integrations["linear"] is True
        assert integrations["github"] is True
        assert integrations["azure_devops"] is False

    def test_get_agent_integrations_respects_explicit_config(self, tmp_path):
        """Respects explicit AGENT_INTEGRATION_* config keys."""
        config_file = tmp_path / ".ingot-config"
        config_file.write_text(
            'AGENT_INTEGRATION_JIRA="false"\n'
            'AGENT_INTEGRATION_MONDAY="true"\n'
        )
        manager = ConfigManager(config_file)
        manager.load()

        integrations = manager._get_agent_integrations()

        # Explicit config should override defaults
        assert integrations["jira"] is False
        assert integrations["monday"] is True

    @patch("ingot.integrations.auth.AuthenticationManager")
    def test_get_fallback_status_checks_all_platforms(
        self, mock_auth_class, temp_config_file
    ):
        """Checks fallback status for all known platforms."""
        mock_auth = mock_auth_class.return_value
        mock_auth.has_fallback_configured.return_value = False

        manager = ConfigManager(temp_config_file)
        manager.load()

        status = manager._get_fallback_status()

        # Should check all platforms
        from ingot.config.fetch_config import KNOWN_PLATFORMS
        assert set(status.keys()) == KNOWN_PLATFORMS

    def test_get_platform_ready_status_logic(self, temp_config_file):
        """Platform is ready if agent OR fallback is configured."""
        manager = ConfigManager(temp_config_file)
        manager.load()

        agent = {"jira": True, "linear": False, "github": False}
        fallback = {"jira": False, "linear": True, "github": False}

        ready = manager._get_platform_ready_status(agent, fallback)

        assert ready["jira"] is True   # agent=True
        assert ready["linear"] is True  # fallback=True
        assert ready["github"] is False  # neither
```

---

## Acceptance Criteria

### From Linear Ticket AMI-42

- [ ] **AC1:** `spec --config` shows the current `default_platform` setting
- [ ] **AC2:** Output shows configured fallback credentials per platform (status only, not values - "masked" per ticket)
- [ ] **AC3:** Output shows agent integration status per platform
- [ ] **AC4:** Output clearly indicates which platforms are ready to use

### Implementation Quality Criteria (Additions)

- [ ] **AC5:** Jira-specific language is replaced with platform-agnostic language where appropriate
- [ ] **AC6:** Existing configuration display (models, parallel execution, subagents) is preserved
- [ ] **QC1:** Output renders correctly in terminal (Rich formatting)
- [ ] **QC2:** Table aligns properly with varying platform names
- [ ] **QC3:** Color coding is accessible (uses emoji plus text, not color alone)
- [ ] **QC4:** Tests verify new output sections
- [ ] **QC5:** Helper methods have dedicated unit tests

---

## Testing Strategy

### Manual Testing

```bash
# 1. Run spec --config and verify new output
spec --config

# 2. Configure fallback credentials for a platform and verify status updates
echo 'FALLBACK_AZURE_DEVOPS_ORGANIZATION=myorg' >> ~/.ingot-config
echo 'FALLBACK_AZURE_DEVOPS_PAT=test' >> ~/.ingot-config
spec --config  # Should show Azure DevOps as "✅ Ready"

# 3. Set default platform and verify it's displayed
echo 'DEFAULT_PLATFORM=linear' >> ~/.ingot-config
spec --config  # Should show "Default Platform: linear"

# 4. Verify output works without any configuration
rm ~/.ingot-config
spec --config  # Should show all platforms with appropriate status
```

### Automated Testing

```bash
# Run config manager tests
pytest tests/test_config_manager.py -v -k "test_show"

# Run CLI tests to ensure --config flag still works
pytest tests/test_cli.py -v -k "test_config"
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Rich Table rendering issues in non-TTY environments | Low | Medium | Use fallback plain text if Rich table fails |
| Import cycle with AuthenticationManager | Medium | High | Lazy import inside `_get_fallback_status()` method |
| Performance impact of credential checks | Low | Low | `has_fallback_configured()` is lightweight (no network calls) |
| Breaking existing test mocks | Medium | Medium | Update test mocks to expect new output structure |

### Import Cycle Mitigation

The `AuthenticationManager` import must be inside the method to avoid import cycles:

```python
def _get_fallback_status(self) -> dict[str, bool]:
    # Import inside method to avoid circular import
    from ingot.integrations.auth import AuthenticationManager
    from ingot.integrations.providers import Platform
    # ...
```

---

## Example Usage

### Complete Example Output

```
$ spec --config

════════════════ Current Configuration ════════════════
ℹ Global config: /Users/user/.ingot-config
ℹ Local config:  /path/to/project/.ingot

  Platform Settings:
    Default Platform: jira
    Default Jira Project: MYPROJ

  Platform Status:
    ┌──────────────┬───────────────┬──────────────┬──────────────┐
    │ Platform     │ Agent Support │ Credentials  │ Status       │
    ├──────────────┼───────────────┼──────────────┼──────────────┤
    │ Jira         │ ✅ Yes        │ ✅ Configured│ ✅ Ready     │
    │ Linear       │ ✅ Yes        │ ❌ None      │ ✅ Ready     │
    │ GitHub       │ ✅ Yes        │ ❌ None      │ ✅ Ready     │
    │ Azure DevOps │ ❌ No         │ ✅ Configured│ ✅ Ready     │
    │ Monday       │ ❌ No         │ ❌ None      │ ❌ Needs Config│
    │ Trello       │ ❌ No         │ ❌ None      │ ❌ Needs Config│
    └──────────────┴───────────────┴──────────────┴──────────────┘

  Tip: See docs/platform-configuration.md for credential setup

  Model Settings:
    Default Model (Legacy): (not set)
    Planning Model: claude-sonnet-4-20250514
    Implementation Model: claude-sonnet-4-20250514

  General Settings:
    Auto-open Files: True
    Preferred Editor: (auto-detect)
    Skip Clarification: False
    Squash Commits at End: True

  Parallel Execution:
    Enabled: True
    Max Parallel Tasks: 4
    Fail Fast: True

  Subagents:
    Planner: .augment/agents/ingot-planner.md
    Tasklist: .augment/agents/ingot-tasklist-refiner.md
    Implementer: .augment/agents/ingot-implementer.md
    Reviewer: .augment/agents/ingot-reviewer.md
```

---

## References

### Related Implementation Plans

| Document | Purpose |
|----------|---------|
| [AMI-25-implementation-plan.md](./AMI-25-implementation-plan.md) | CLI migration with `DEFAULT_PLATFORM` |
| [AMI-22-implementation-plan.md](./AMI-22-implementation-plan.md) | AuthenticationManager implementation |
| [AMI-33-implementation-plan.md](./AMI-33-implementation-plan.md) | Fetch configuration architecture |
| [AMI-38-implementation-plan.md](./AMI-38-implementation-plan.md) | README multi-platform updates |
| [AMI-41-implementation-plan.md](./AMI-41-implementation-plan.md) | Platform configuration guide |

### Code References

| File | Relevant Code |
|------|--------------|
| `ingot/config/manager.py:883-915` | Current `show()` implementation |
| `ingot/integrations/auth.py:186-225` | `has_fallback_configured()` method |
| `ingot/config/fetch_config.py:148-155` | `PLATFORM_REQUIRED_CREDENTIALS` |
| `ingot/config/settings.py:92` | `default_platform` setting |

---

## Estimated Effort

| Phase | Description | Estimate |
|-------|-------------|----------|
| Phase 1 | Add helper methods | 0.25 day |
| Phase 2 | Update show() method | 0.25 day |
| Phase 3 | Update tests | 0.25 day |
| Validation | Manual testing | 0.25 day |
| **Total** | | **~0.5 day** |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-29 | AI Assistant | Initial draft created |
