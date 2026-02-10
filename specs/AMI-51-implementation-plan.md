# AMI-51: Phase 1.5 - Create AuggieBackend

**Ticket:** [AMI-51](https://linear.app/amiadingot/issue/AMI-51/phase-15-create-auggiebackend)
**Status:** In Progress
**Date:** 2026-02-01
**Labels:** MultiAgent
**Parent:** [AMI-45: Pluggable Multi-Agent Support](https://linear.app/amiadingot/issue/AMI-45)

---

## Summary

Create the `AuggieBackend` class that extends `BaseBackend` and wraps the existing `AuggieClient`. This is the first concrete backend implementation in the pluggable multi-agent architecture.

**Why This Matters:**
- AuggieBackend is the reference implementation for all future backends (Claude, Cursor, Aider)
- Demonstrates the delegation pattern: wrapping existing CLI clients without modifying them
- Validates that the `AIBackend` protocol and `BaseBackend` abstract class work correctly
- Enables the Backend Factory (AMI-52) to create backend instances by platform

**Scope:**
- Create `ingot/integrations/backends/auggie.py` containing:
  - `AuggieBackend` class extending `BaseBackend`
  - Implementation of all `AIBackend` protocol methods
  - Delegation to `AuggieClient` for actual CLI execution
  - Parameter mapping (`subagent` → `agent`)
  - Timeout handling via `_run_streaming_with_timeout()` for `run_with_callback()`
- Update `ingot/integrations/backends/__init__.py` to export `AuggieBackend`

**Reference:** `specs/Pluggable Multi-Agent Support.md` - Phase 1.5 (lines 1771-1918)

> **Note:** The Linear ticket AMI-51 contains outdated method names (`_execute_cli()`, `_get_rate_limit_patterns()`) that don't match the parent specification. This implementation plan follows the **parent specification** as the source of truth. The Linear ticket should be updated to match.

---

## Context

Phase 1.5 is positioned between the infrastructure phases (1.1-1.4) and the factory/integration phases (1.6+):

| Phase | Ticket | Description | Status |
|-------|--------|-------------|--------|
| 1.1 | AMI-47 | Backend Error Types | ✅ Done |
| 1.2 | AMI-48 | AIBackend Protocol | ✅ Done |
| 1.3 | AMI-49 | BaseBackend Abstract Class | ✅ Done |
| 1.4 | AMI-50 | Move Subagent Constants | 🔄 Current |
| **1.5** | **AMI-51** | **Create AuggieBackend** | **📋 This ticket** |
| 1.6 | AMI-52 | Create Backend Factory | ⏳ Pending |

AuggieBackend serves as the reference implementation demonstrating how concrete backends should:
- Extend `BaseBackend` to inherit shared functionality
- Implement the `AIBackend` protocol
- Wrap existing CLI clients (delegation pattern)
- Map parameters between protocol and client APIs

## Current State Analysis

### Existing Infrastructure (Dependencies)

1. **`ingot/integrations/backends/errors.py`** (AMI-47)
   - `BackendError`, `BackendNotInstalledError`, `BackendTimeoutError`, `BackendRateLimitError`

2. **`ingot/integrations/backends/base.py`** (AMI-48, AMI-49)
   - `AIBackend` Protocol with all required methods and properties
   - `BaseBackend` ABC with helper methods:
     - `_parse_subagent_prompt()` - Parses YAML frontmatter from subagent files
     - `_resolve_model()` - Model precedence resolution
     - `_run_streaming_with_timeout()` - Watchdog thread pattern for timeouts
   - `SubagentMetadata` dataclass

3. **`ingot/integrations/auggie.py`** (Existing)
   - `AuggieClient` - Core CLI wrapper with methods:
     - `_build_command()` - Builds CLI command with agent/model/flags
     - `run_with_callback()` - Streaming execution with callback
     - `run_print_with_output()` - Returns (bool, str)
     - `run_print_quiet()` - Returns str only
   - `check_auggie_installed()` - CLI installation check
   - `_looks_like_rate_limit()` - Rate limit detection heuristics
   - `AuggieRateLimitError` - Current rate limit exception

## Technical Approach

### File Structure

**Create:** `ingot/integrations/backends/auggie.py`

### Implementation Details

#### Class Definition

```python
class AuggieBackend(BaseBackend):
    """Auggie CLI backend implementation.

    Extends BaseBackend to inherit shared logic (subagent parsing, model resolution).
    Wraps the existing AuggieClient for actual CLI execution.
    """

    def __init__(self, model: str = "") -> None:
        super().__init__(model=model)
        self._client = AuggieClient(model=model)
```

#### Properties

| Property | Value | Notes |
|----------|-------|-------|
| `name` | `"Auggie"` | Human-readable backend name |
| `platform` | `AgentPlatform.AUGGIE` | Enum value for configuration |
| `supports_parallel` | `True` | Auggie handles concurrent invocations |

#### Method Implementations

| Method | Implementation Strategy |
|--------|------------------------|
| `run_with_callback()` | Resolve model via `_resolve_model()`, use `_run_streaming_with_timeout()` when timeout specified, delegate to `AuggieClient.run_with_callback()` otherwise |
| `run_print_with_output()` | Resolve model, delegate to `AuggieClient.run_print_with_output()` |
| `run_print_quiet()` | Resolve model, delegate to `AuggieClient.run_print_quiet()` |
| `run_streaming()` | Delegate to `run_print_with_output()` (non-interactive mode) |
| `check_installed()` | Delegate to `check_auggie_installed()` |
| `detect_rate_limit()` | Delegate to `_looks_like_rate_limit()` |
| `supports_parallel_execution()` | Inherited from `BaseBackend` |
| `close()` | Inherited from `BaseBackend` (no-op) |

#### Parameter Mapping

The protocol uses `subagent` while AuggieClient uses `agent`:

```python
def run_with_callback(
    self,
    prompt: str,
    *,
    subagent: str | None = None,  # Protocol parameter
    ...
) -> tuple[bool, str]:
    # Map to client's parameter name
    return self._client.run_with_callback(
        prompt,
        agent=subagent,  # AuggieClient parameter
        ...
    )
```

### Imports

```python
from ingot.config.fetch_config import AgentPlatform
from ingot.integrations.backends.base import BaseBackend
from ingot.integrations.auggie import (
    AuggieClient,
    check_auggie_installed,
    _looks_like_rate_limit,
)
```

## Implementation Phases

### Phase 1: Create File and Class Structure (~0.5 hours)

1. Create `ingot/integrations/backends/auggie.py`
2. Add module docstring and imports
3. Implement `AuggieBackend` class with `__init__()` and properties
4. Verify imports work correctly

### Phase 2: Implement Core Execution Methods (~1 hour)

1. Implement `run_with_callback()` with timeout support
2. Implement `run_print_with_output()`
3. Implement `run_print_quiet()`
4. Implement `run_streaming()`

### Phase 3: Implement Utility Methods (~0.5 hours)

1. Implement `check_installed()`
2. Implement `detect_rate_limit()`
3. Verify inherited methods work (`supports_parallel_execution()`, `close()`)

### Phase 4: Update Exports (~0.25 hours)

1. Add `AuggieBackend` to `ingot/integrations/backends/__init__.py`

## Testing Strategy

### Unit Tests

**File:** `tests/integrations/backends/test_auggie_backend.py`

```python
class TestAuggieBackend:
    """Tests for AuggieBackend implementation."""

    def test_name_property(self):
        """Backend name is 'Auggie'."""

    def test_platform_property(self):
        """Platform is AgentPlatform.AUGGIE."""

    def test_supports_parallel_property(self):
        """Backend supports parallel execution."""

    def test_run_with_callback_delegates_to_client(self):
        """run_with_callback delegates to AuggieClient."""

    def test_run_with_callback_maps_subagent_to_agent(self):
        """subagent parameter maps to agent in AuggieClient."""

    def test_run_with_callback_resolves_model(self):
        """Model is resolved using _resolve_model()."""

    def test_run_with_callback_uses_timeout_wrapper(self):
        """Timeout triggers _run_streaming_with_timeout()."""

    def test_run_with_callback_without_timeout_delegates_directly(self):
        """Without timeout, delegates directly to AuggieClient.run_with_callback()."""

    def test_run_print_with_output_delegates(self):
        """run_print_with_output delegates to AuggieClient."""

    def test_run_print_quiet_delegates(self):
        """run_print_quiet delegates to AuggieClient."""

    def test_run_streaming_delegates_to_run_print_with_output(self):
        """run_streaming calls run_print_with_output internally."""

    def test_detect_rate_limit_delegates(self):
        """detect_rate_limit uses _looks_like_rate_limit."""

    def test_check_installed_delegates(self):
        """check_installed uses check_auggie_installed."""

    def test_timeout_error_propagates(self):
        """BackendTimeoutError from _run_streaming_with_timeout bubbles up."""


class TestAuggieBackendProtocolCompliance:
    """Tests verifying AIBackend protocol compliance."""

    def test_isinstance_aibackend(self):
        """AuggieBackend satisfies AIBackend protocol via isinstance()."""
        from ingot.integrations.backends import AuggieBackend, AIBackend
        backend = AuggieBackend()
        assert isinstance(backend, AIBackend)

    def test_has_all_required_properties(self):
        """AuggieBackend has all required protocol properties."""

    def test_has_all_required_methods(self):
        """AuggieBackend has all required protocol methods."""


class TestAuggieClientContract:
    """Tests verifying AuggieClient private API contract.

    These tests ensure _build_command() behavior matches AuggieBackend's expectations.
    If these fail, AuggieBackend may need updates.
    """

    def test_build_command_basic_structure(self):
        """Verify _build_command() returns expected command structure."""
        from ingot.integrations.auggie import AuggieClient
        client = AuggieClient()
        cmd = client._build_command("test prompt", print_mode=True)
        assert cmd[0] == "auggie"
        assert "--print" in cmd
        assert cmd[-1] == "test prompt"

    def test_build_command_model_ignored_when_agent_set(self):
        """Verify model parameter is ignored when agent is specified.

        This documents the known limitation - explicit model override
        does not work when a subagent is specified.
        """
        from ingot.integrations.auggie import AuggieClient
        from unittest.mock import patch, MagicMock

        client = AuggieClient()

        # Mock agent definition with its own model
        mock_agent_def = MagicMock()
        mock_agent_def.model = "agent-model"
        mock_agent_def.prompt = "Agent instructions"

        with patch("ingot.integrations.auggie._parse_agent_definition", return_value=mock_agent_def):
            cmd = client._build_command(
                "test prompt",
                agent="test-agent",
                model="explicit-override-model",  # This should be ignored
            )

        # Agent's model is used, not the explicit override
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "agent-model"  # NOT "explicit-override-model"
```

### Integration Tests (Gated)

Integration tests with real Auggie CLI are gated behind `INGOT_INTEGRATION_TESTS=1`:

```python
@pytest.mark.skipif(
    os.environ.get("INGOT_INTEGRATION_TESTS") != "1",
    reason="Integration tests require INGOT_INTEGRATION_TESTS=1",
)
class TestAuggieBackendIntegration:
    """Integration tests with real Auggie CLI."""

    def test_check_installed_returns_version(self):
        """check_installed returns True and version string when Auggie is installed."""

    def test_run_print_quiet_executes_successfully(self):
        """run_print_quiet executes a simple prompt successfully."""
```

### Timeout Handling Note

> **Important:** The `timeout_seconds` parameter is only implemented for `run_with_callback()` in this initial version. The `run_print_with_output()` and `run_print_quiet()` methods accept the parameter (per `AIBackend` protocol) but do not enforce timeout - they delegate directly to `AuggieClient` which does not have timeout support. This matches the parent specification (lines 1855-1887). Timeout support for these methods can be added in a future enhancement if needed.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Parameter mismatch between protocol and client | Low | Medium | Comprehensive tests for parameter mapping |
| Model resolution edge cases | Low | Low | Reuse tested `_resolve_model()` from BaseBackend |
| Timeout handling complexity | Low | Medium | Leverage `_run_streaming_with_timeout()` from BaseBackend |
| **Model override precedence (see below)** | **High** | **Medium** | **Document limitation; do not claim explicit override works** |
| **Private API dependency** | Medium | Low | Add acceptance test for `_build_command()` contract |
| **FileNotFoundError on missing CLI** | Low | Low | Defer to AMI-52 factory validation |

---

## Known Limitations and Design Decisions

This section documents important behavioral constraints that arise from wrapping `AuggieClient`.

### 1. Model Override Precedence Limitation (IMPORTANT)

**Issue:** The `_resolve_model()` precedence (explicit → frontmatter → default) **cannot be fully enforced** when using subagents with Auggie.

**Root Cause:** `AuggieClient._build_command()` (lines 418-424 in `auggie.py`) explicitly ignores the `model` parameter when an `agent` is specified:

```python
# From AuggieClient._build_command():
if agent:
    agent_def = _parse_agent_definition(agent)
    if agent_def:
        # Use model from agent definition
        if agent_def.model:
            cmd.extend(["--model", agent_def.model])  # ← Ignores passed model!
```

The docstring confirms: "*model: Override model for this command (ignored when agent is set)*"

**Consequence:** When `AuggieBackend.run_with_callback(prompt, subagent="ingot-planner", model="claude-3-opus")` is called:
1. `_resolve_model()` correctly returns `"claude-3-opus"` (explicit override)
2. `_build_command()` is called with `model="claude-3-opus"`
3. `_build_command()` **ignores** this and uses the model from `ingot-planner.md` frontmatter instead

**Resolution:** This is an **accepted limitation** for AuggieBackend. The behavior matches the existing `AuggieClient` semantics. Future backends (Claude, Cursor) can implement true model override if their CLIs support it.

**Documentation Update Required:** The Definition of Done item "Model resolution uses `_resolve_model()` precedence" should be clarified:
- ✅ `_resolve_model()` is called and returns correct precedence
- ⚠️ The resolved model is passed to `_build_command()` but may be ignored when subagent is set
- ✅ When no subagent is specified, explicit model override works correctly

### 2. Private API Dependency

**Issue:** `AuggieBackend` calls `self._client._build_command()`, which is a private method (leading underscore).

**Risk:** If `AuggieClient` internal implementation changes, `AuggieBackend` could break silently.

**Resolution:** This is an **intentional design choice** per the parent specification (delegation pattern). Mitigations:
1. Add unit test that verifies `_build_command()` returns expected command structure
2. Document this coupling in code comments
3. Consider promoting `_build_command()` to public API in future refactor

**Acceptance Test:**
```python
def test_build_command_contract():
    """Verify _build_command() contract for AuggieBackend compatibility."""
    client = AuggieClient()
    cmd = client._build_command("test prompt", print_mode=True)
    assert cmd[0] == "auggie"
    assert "--print" in cmd
    assert cmd[-1] == "test prompt"
```

### 3. FileNotFoundError on Missing CLI

**Issue:** When `_run_streaming_with_timeout()` spawns `subprocess.Popen(["auggie", ...])` and `auggie` is not installed, Python raises `FileNotFoundError`, not `BackendNotInstalledError`.

**Resolution:** This is **deferred to AMI-52 (Backend Factory)**. The factory will call `check_installed()` before returning a backend instance, ensuring:
1. CLI availability is validated at backend creation time
2. `BackendNotInstalledError` is raised with actionable message
3. Runtime `FileNotFoundError` should never occur in normal usage

**Alternative (not implemented):** Add try/except in `_run_streaming_with_timeout()`:
```python
try:
    process = subprocess.Popen(cmd, ...)
except FileNotFoundError as e:
    raise BackendNotInstalledError(
        f"Backend CLI not found: {cmd[0]}",
        backend_name=self.name
    ) from e
```

This alternative is noted but **not required** for AMI-51 since factory validation is the cleaner approach.

## Verification Commands

```bash
# Verify file exists
ls -la ingot/integrations/backends/auggie.py

# Verify imports work without cycles
python -c "from ingot.integrations.backends import AuggieBackend; print('Import OK')"

# Verify protocol compliance
python -c "
from ingot.integrations.backends import AuggieBackend, AIBackend
backend = AuggieBackend()
assert isinstance(backend, AIBackend), 'Protocol compliance failed'
print('Protocol compliance OK')
"

# Verify properties
python -c "
from ingot.integrations.backends import AuggieBackend
from ingot.config.fetch_config import AgentPlatform
backend = AuggieBackend()
assert backend.name == 'Auggie', f'Expected Auggie, got {backend.name}'
assert backend.platform == AgentPlatform.AUGGIE, f'Expected AUGGIE, got {backend.platform}'
assert backend.supports_parallel == True, 'Expected supports_parallel=True'
print('Properties OK')
"

# Run unit tests
pytest tests/integrations/backends/test_auggie_backend.py -v

# Run mypy type checking
mypy ingot/integrations/backends/auggie.py --strict

# Verify no import cycles
python -c "
import sys
from ingot.integrations.backends.auggie import AuggieBackend
from ingot.integrations.backends.base import AIBackend, BaseBackend
from ingot.integrations.backends.errors import BackendTimeoutError
print('No import cycles detected')
"
```

## Definition of Done

### Implementation Checklist

- [ ] `ingot/integrations/backends/auggie.py` created
- [ ] `AuggieBackend` class extends `BaseBackend`
- [ ] `AuggieBackend` implements `AIBackend` protocol (verified by `isinstance()`)
- [ ] All abstract methods from `BaseBackend` implemented:
  - [ ] `name` property → returns `"Auggie"`
  - [ ] `platform` property → returns `AgentPlatform.AUGGIE`
  - [ ] `supports_parallel` property → returns `True`
  - [ ] `run_with_callback()` → with timeout wrapper support
  - [ ] `run_print_with_output()` → delegates to AuggieClient
  - [ ] `run_print_quiet()` → delegates to AuggieClient
  - [ ] `run_streaming()` → delegates to `run_print_with_output()`
  - [ ] `check_installed()` → delegates to `check_auggie_installed()`
  - [ ] `detect_rate_limit()` → delegates to `_looks_like_rate_limit()`

### Parameter Mapping

- [ ] `subagent` parameter correctly mapped to `agent` in AuggieClient calls
- [ ] `_resolve_model()` is called with correct precedence (explicit → subagent frontmatter → instance default)
- [ ] ⚠️ **Known limitation:** When subagent is set, `_build_command()` uses agent file's model (see "Known Limitations" section)
- [ ] When no subagent is specified, explicit model override works correctly
- [ ] Timeout handling uses `_run_streaming_with_timeout()` for `run_with_callback()`

### Private API Coupling

- [ ] Unit test verifies `_build_command()` contract (command structure)
- [ ] Code comment documents dependency on private `_build_command()` method

### Exports

- [ ] `AuggieBackend` exported from `ingot/integrations/backends/__init__.py`

### Quality Checklist

- [ ] All methods and properties have complete docstrings
- [ ] `mypy --strict` reports no type errors
- [ ] No import cycles introduced
- [ ] Unit tests pass (`pytest tests/integrations/backends/test_auggie_backend.py`)
- [ ] No regressions in existing tests (`pytest tests/`)

## Estimated Effort

~0.45 days (similar complexity to AMI-49 BaseBackend)

- Phase 1 (Structure): ~0.5 hours
- Phase 2 (Core Methods): ~1 hour
- Phase 3 (Utility Methods): ~0.5 hours
- Phase 4 (Exports): ~0.25 hours
- Testing: ~1.5 hours

## Dependencies

### Upstream (Required Before Starting)

| Ticket | Description | Status |
|--------|-------------|--------|
| AMI-47 | Backend Error Types | ✅ Done |
| AMI-48 | AIBackend Protocol | ✅ Done |
| AMI-49 | BaseBackend Abstract Class | ✅ Done |
| AMI-50 | Move Subagent Constants | 🔄 Current |

### Downstream (Blocked By This)

| Ticket | Description |
|--------|-------------|
| AMI-52 | Create Backend Factory |
| AMI-53+ | Additional backend implementations |

## References

- **Parent Specification:** `specs/Pluggable Multi-Agent Support.md` (lines 1772-1918)
- **Protocol Definition:** `ingot/integrations/backends/base.py` (AIBackend, BaseBackend)
- **Error Types:** `ingot/integrations/backends/errors.py`
- **Wrapped Client:** `ingot/integrations/auggie.py` (AuggieClient)
- **Related Plans:**
  - `specs/AMI-47-implementation-plan.md`
  - `specs/AMI-48-implementation-plan.md`
  - `specs/AMI-49-implementation-plan.md`
  - `specs/AMI-50-implementation-plan.md`

---

## Appendix: Full AuggieBackend Class Structure

The complete implementation as specified in the parent spec:

```python
"""Auggie CLI backend implementation."""
from typing import Callable

from ingot.config.fetch_config import AgentPlatform
from ingot.integrations.backends.base import BaseBackend
from ingot.integrations.auggie import (
    AuggieClient,
    check_auggie_installed,
    _looks_like_rate_limit,
)


class AuggieBackend(BaseBackend):
    """Auggie CLI backend implementation.

    Extends BaseBackend to inherit shared logic (subagent parsing, model resolution).
    Wraps the existing AuggieClient for actual CLI execution.

    Attributes:
        _client: The underlying AuggieClient instance for CLI execution.
    """

    def __init__(self, model: str = "") -> None:
        """Initialize the Auggie backend.

        Args:
            model: Default model to use for commands.
        """
        super().__init__(model=model)
        self._client = AuggieClient(model=model)

    @property
    def name(self) -> str:
        """Return the backend name."""
        return "Auggie"

    @property
    def platform(self) -> AgentPlatform:
        """Return the platform identifier."""
        return AgentPlatform.AUGGIE

    @property
    def supports_parallel(self) -> bool:
        """Return whether this backend supports parallel execution."""
        return True  # Auggie handles concurrent invocations

    def run_with_callback(
        self,
        prompt: str,
        *,
        output_callback: Callable[[str], None],
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Execute with streaming callback and optional timeout.

        Uses BaseBackend._run_streaming_with_timeout() for timeout enforcement.
        This wraps the AuggieClient call with the streaming-safe watchdog pattern.

        Args:
            prompt: The prompt to send to Auggie.
            output_callback: Callback function for streaming output.
            subagent: Optional subagent name (mapped to 'agent' in AuggieClient).
            model: Optional model override.
            dont_save_session: If True, don't save the session.
            timeout_seconds: Optional timeout in seconds.

        Returns:
            Tuple of (success, output).

        Raises:
            BackendTimeoutError: If timeout_seconds is specified and exceeded.
        """
        resolved_model = self._resolve_model(model, subagent)

        # Build auggie CLI command
        cmd = self._client._build_command(
            prompt,
            agent=subagent,
            model=resolved_model,
            dont_save_session=dont_save_session,
        )

        # Use streaming timeout wrapper from BaseBackend
        if timeout_seconds:
            exit_code, output = self._run_streaming_with_timeout(
                cmd,
                output_callback=output_callback,
                timeout_seconds=timeout_seconds,
            )
            success = exit_code == 0
            return success, output
        else:
            # No timeout - delegate to client's original implementation
            return self._client.run_with_callback(
                prompt,
                output_callback=output_callback,
                agent=subagent,
                model=resolved_model,
                dont_save_session=dont_save_session,
            )

    def run_print_with_output(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Run with --print flag, return success status and captured output.

        Note: timeout_seconds is accepted per protocol but not enforced in this version.
        """
        resolved_model = self._resolve_model(model, subagent)
        return self._client.run_print_with_output(
            prompt,
            agent=subagent,
            model=resolved_model,
            dont_save_session=dont_save_session,
        )

    def run_print_quiet(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        dont_save_session: bool = False,
        timeout_seconds: float | None = None,
    ) -> str:
        """Run with --print --quiet, return output only.

        Note: timeout_seconds is accepted per protocol but not enforced in this version.
        """
        resolved_model = self._resolve_model(model, subagent)
        return self._client.run_print_quiet(
            prompt,
            agent=subagent,
            model=resolved_model,
            dont_save_session=dont_save_session,
        )

    def run_streaming(
        self,
        prompt: str,
        *,
        subagent: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> tuple[bool, str]:
        """Execute in streaming mode (non-interactive).

        Uses run_print_with_output internally as Auggie's non-interactive mode.
        """
        return self.run_print_with_output(
            prompt,
            subagent=subagent,
            model=model,
            timeout_seconds=timeout_seconds,
        )

    # NOTE: run_print() is NOT exposed - see Final Decision #4 in parent spec
    # Legacy callers must be refactored to use TUI + run_streaming()

    def check_installed(self) -> tuple[bool, str]:
        """Check if Auggie CLI is installed.

        Returns:
            Tuple of (is_installed, version_or_error_message).
        """
        return check_auggie_installed()

    def detect_rate_limit(self, output: str) -> bool:
        """Detect if output indicates a rate limit error.

        Args:
            output: The output string to check.

        Returns:
            True if output looks like a rate limit error.
        """
        return _looks_like_rate_limit(output)

    # supports_parallel_execution() and close() inherited from BaseBackend
```

---

## Changelog

| Date | Author | Changes |
|------|--------|---------|
| 2026-02-01 | Implementation Plan Created | Initial version with all sections |
| 2026-02-01 | Plan Review | Added Verification Commands, Definition of Done, Appendix, and Changelog sections per review recommendations |
| 2026-02-01 | Additional Improvements | Added "Why This Matters", "Scope", and "Reference" sections to Summary for consistency with AMI-49 pattern |
| 2026-02-01 | Gap Analysis | Added "Known Limitations and Design Decisions" section addressing: (1) Model override precedence limitation with `_build_command()`, (2) Private API dependency risk, (3) FileNotFoundError handling deferred to AMI-52. Updated Definition of Done and Testing Strategy accordingly. |
