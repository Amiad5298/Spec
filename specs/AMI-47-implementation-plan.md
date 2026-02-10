# Implementation Plan: AMI-47 - Phase 1.1: Create Backend Error Types

**Ticket:** [AMI-47](https://linear.app/amiadingot/issue/AMI-47/phase-11-create-backend-error-types)
**Status:** Draft
**Date:** 2026-01-31
**Labels:** MultiAgent

---

## Summary

This ticket creates generic error types that apply to all AI backends as part of the Pluggable Multi-Agent Support refactoring. These error types form the foundation of the backend abstraction layer, enabling backend-agnostic error handling throughout the workflow.

**Why This Matters:**
- The current `AuggieRateLimitError` is Auggie-specific and lives in `ingot/integrations/auggie.py`
- When adding Claude, Cursor, or other backends, each needs consistent error handling
- These generic error types allow workflow code to catch `BackendRateLimitError` without knowing which backend threw it
- Proper error types enable better rate limit retry logic, timeout handling, and configuration validation

**Scope:**
- Create `ingot/integrations/backends/__init__.py` (package init)
- Create `ingot/integrations/backends/errors.py` with 4 error types:
  - `BackendRateLimitError` - Replaces `AuggieRateLimitError`
  - `BackendNotInstalledError` - Backend CLI not installed
  - `BackendNotConfiguredError` - No AI backend configured
  - `BackendTimeoutError` - Backend execution timeout

**Reference:** `specs/Pluggable Multi-Agent Support.md` - Phase 1.1 (lines 1242-1295)

---

## Context

This is **Phase 1.1** of the Backend Infrastructure work (AMI-45), which is part of the larger Pluggable Multi-Agent Support initiative.

### Parent Specification

The [Pluggable Multi-Agent Support](./Pluggable%20Multi-Agent%20Support.md) specification defines a phased approach to support multiple AI backends:

- **Phase 0:** Baseline Behavior Tests (AMI-44) ✅ Done
- **Phase 1.0:** Rename Claude Platform Enum (AMI-46) ⏳ Backlog
- **Phase 1.1:** Create Backend Error Types (AMI-47) ← **This Ticket**
- **Phase 1.2:** Create AIBackend Protocol (AMI-48)
- **Phase 1.3+:** BaseBackend, AuggieBackend, Factory, etc.

### Error Type Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ingot/utils/errors.py                                │
│                                                                              │
│   IngotError (base exception with exit_code)                                 │
│       ├── AuggieNotInstalledError                                           │
│       ├── PlatformNotConfiguredError                                        │
│       ├── UserCancelledError                                                │
│       └── GitOperationError                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ inherits from
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ingot/integrations/backends/errors.py                       │
│                                                                              │
│   BackendRateLimitError (replaces AuggieRateLimitError)                     │
│       - output: str (captured output for debugging)                         │
│       - backend_name: str (which backend hit the limit)                     │
│                                                                              │
│   BackendNotInstalledError                                                  │
│       - Simple error when CLI is not found                                  │
│                                                                              │
│   BackendNotConfiguredError                                                 │
│       - No backend configured (neither --backend nor AI_BACKEND)            │
│                                                                              │
│   BackendTimeoutError                                                       │
│       - timeout_seconds: float (how long before timeout)                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Approach

### Comparison: Current vs. New

| Current (Auggie-Specific) | New (Backend-Agnostic) |
|---------------------------|------------------------|
| `AuggieRateLimitError` in `ingot/integrations/auggie.py` | `BackendRateLimitError` in `ingot/integrations/backends/errors.py` |
| `self.output` attribute only | `self.output` + `self.backend_name` attributes |
| Not a `IngotError` subclass | Inherits from `IngotError` |
| No exit code semantics | Inherits `ExitCode.GENERAL_ERROR` (default) |

### Key Design Decisions

1. **Extend `IngotError`**: All backend errors inherit from `IngotError` to leverage:
   - Consistent exit code handling
   - Uniform exception hierarchy
   - Existing error handling patterns

2. **Carry Context**: `BackendRateLimitError` carries `output` and `backend_name` for:
   - Debug logging (what output triggered detection)
   - User-facing messages ("Rate limited by Auggie")
   - Retry logic context

3. **Simple Base Errors**: `BackendNotInstalledError` and `BackendNotConfiguredError` are simple because:
   - Message is sufficient context
   - Exit code inherited from `IngotError`
   - No additional attributes needed

4. **Timeout Context**: `BackendTimeoutError` carries `timeout_seconds` for:
   - User feedback ("Timed out after 120 seconds")
   - Retry logic with adjusted timeouts

5. **Default Exit Codes**: All backend errors inherit `ExitCode.GENERAL_ERROR` from `IngotError`. Custom exit codes (e.g., `BACKEND_NOT_INSTALLED = 6`) can be added in a future ticket if needed for CLI scripting. This keeps the initial implementation simple while preserving flexibility.

---

## Files to Create

| File | Purpose |
|------|---------|
| `ingot/integrations/backends/__init__.py` | Package initialization, exports error types |
| `ingot/integrations/backends/errors.py` | Error type definitions |

---

## Implementation Phases

### Phase 1: Create Package Structure

#### Step 1.1: Create Package Init File

**File:** `ingot/integrations/backends/__init__.py`

```python
"""Backend infrastructure for AI agent integrations.

This package provides a unified abstraction layer for AI backends:
- Auggie (Augment Code CLI)
- Claude (Claude Code CLI)
- Cursor (Cursor IDE)
- Aider (Aider CLI)

Modules:
- errors: Backend-related error types
- base: AIBackend protocol and BaseBackend class (Phase 1.2+)
- factory: Backend factory for instantiation (Phase 1.6+)
"""

from ingot.integrations.backends.errors import (
    BackendNotConfiguredError,
    BackendNotInstalledError,
    BackendRateLimitError,
    BackendTimeoutError,
)

# Explicit public API for IDE support and documentation.
# All exported symbols should be listed here.
__all__ = [
    "BackendRateLimitError",
    "BackendNotInstalledError",
    "BackendNotConfiguredError",
    "BackendTimeoutError",
]
```

### Phase 2: Create Error Types

#### Step 2.1: Create errors.py with All Error Types

**File:** `ingot/integrations/backends/errors.py`

```python
"""Backend-related errors.

Generic error types that apply to all AI backends. These errors provide
a unified error handling interface across Auggie, Claude, Cursor, and
other backends.

All errors inherit from IngotError to leverage exit code semantics and
the existing exception hierarchy.
"""

from ingot.utils.errors import IngotError


class BackendRateLimitError(IngotError):
    """Raised when any backend hits a rate limit.

    Replaces AuggieRateLimitError for backend-agnostic handling.
    Carries backend_name and output for context.

    Attributes:
        output: The output that triggered rate limit detection
        backend_name: Name of the backend that hit the rate limit

    Example:
        >>> raise BackendRateLimitError(
        ...     "Rate limit detected",
        ...     output="Error 429: Too Many Requests",
        ...     backend_name="Auggie",
        ... )
    """

    def __init__(
        self,
        message: str,
        output: str = "",
        backend_name: str = "",
    ) -> None:
        """Initialize the rate limit error.

        Args:
            message: Error message describing the rate limit
            output: The output that triggered rate limit detection
            backend_name: Name of the backend (e.g., "Auggie", "Claude")
        """
        super().__init__(message)
        self.output = output
        self.backend_name = backend_name


class BackendNotInstalledError(IngotError):
    """Raised when backend CLI is not installed.

    This error is raised when attempting to use a backend whose CLI
    tool is not found in the system PATH.

    Example:
        >>> raise BackendNotInstalledError(
        ...     "Claude CLI is not installed. Install with: npm install -g @anthropic/claude-code"
        ... )
    """

    pass


class BackendNotConfiguredError(IngotError):
    """Raised when no AI backend is configured.

    This error is raised when neither CLI --backend flag nor persisted
    AI_BACKEND config is set. Users should run 'ingot init' to configure
    a backend or use --backend flag.

    Example:
        >>> raise BackendNotConfiguredError(
        ...     "No AI backend configured. Run 'ingot init' or use --backend flag."
        ... )
    """

    pass


class BackendTimeoutError(IngotError):
    """Raised when backend execution times out.

    This error is raised when a backend operation exceeds the configured
    timeout duration. Carries the timeout value for user feedback.

    Attributes:
        timeout_seconds: The timeout duration that was exceeded (if known)

    Example:
        >>> raise BackendTimeoutError(
        ...     "Backend execution timed out after 120 seconds",
        ...     timeout_seconds=120.0,
        ... )
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
    ) -> None:
        """Initialize the timeout error.

        Args:
            message: Error message describing the timeout
            timeout_seconds: The timeout duration that was exceeded
        """
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


__all__ = [
    "BackendRateLimitError",
    "BackendNotInstalledError",
    "BackendNotConfiguredError",
    "BackendTimeoutError",
]
```

---

## Migration Notes: Replacing AuggieRateLimitError

### Current Usage Pattern

The current `AuggieRateLimitError` is used in `ingot/workflow/step3_execute.py`:

```python
# Current pattern (ingot/integrations/auggie.py)
class AuggieRateLimitError(Exception):
    def __init__(self, message: str, output: str):
        super().__init__(message)
        self.output = output

# Usage in step3_execute.py
if not success and _looks_like_rate_limit(output):
    raise AuggieRateLimitError("Rate limit detected", output=output)
```

### Future Migration Pattern (Phase 2+)

After Phase 2 workflow integration:

```python
# New pattern (ingot/integrations/backends/errors.py)
from ingot.integrations.backends.errors import BackendRateLimitError

# Usage will become:
if backend.detect_rate_limit(output):
    raise BackendRateLimitError(
        "Rate limit detected",
        output=output,
        backend_name=backend.name,
    )
```

**Note:** The actual migration of `AuggieRateLimitError` to `BackendRateLimitError` will happen in Phase 2 (Workflow Step Integration). This ticket only creates the new error types.

---

## Dependencies

### Upstream Dependencies (Must Be Complete First)

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| [AMI-44](https://linear.app/amiadingot/issue/AMI-44) | Phase 0: Baseline Tests | ✅ Done | Baseline tests must pass before any refactoring |

### Downstream Dependents (Blocked by This Ticket)

| Ticket | Component | Description |
|--------|-----------|-------------|
| [AMI-48](https://linear.app/amiadingot/issue/AMI-48) | Phase 1.2: AIBackend Protocol | Protocol methods will throw these error types |
| **Phase 1.3+** | BaseBackend, AuggieBackend | Implementations will use these error types |
| **Phase 2** | Workflow Integration | Will migrate from `AuggieRateLimitError` to `BackendRateLimitError` |

### Related Tickets

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [AMI-45](https://linear.app/amiadingot/issue/AMI-45) | Phase 1: Backend Infrastructure | Parent ticket |
| [AMI-46](https://linear.app/amiadingot/issue/AMI-46) | Phase 1.0: Rename Claude Platform Enum | Sibling - can be done in parallel |
| [Pluggable Multi-Agent Support](./Pluggable%20Multi-Agent%20Support.md) | Specification | Parent specification |

---

## Testing Strategy

### Unit Tests for Error Types

Create new test file: `tests/test_backend_errors.py`

```python
"""Tests for ingot.integrations.backends.errors module."""

import pytest

from ingot.integrations.backends.errors import (
    BackendNotConfiguredError,
    BackendNotInstalledError,
    BackendRateLimitError,
    BackendTimeoutError,
)
from ingot.utils.errors import IngotError


class TestBackendRateLimitError:
    """Tests for BackendRateLimitError."""

    def test_inherits_from_spec_error(self):
        """Error inherits from IngotError."""
        error = BackendRateLimitError("Rate limit hit")
        assert isinstance(error, IngotError)

    def test_message_stored(self):
        """Message is stored correctly."""
        error = BackendRateLimitError("Rate limit hit")
        assert str(error) == "Rate limit hit"

    def test_output_attribute(self):
        """Output attribute is stored correctly."""
        error = BackendRateLimitError(
            "Rate limit hit",
            output="429 Too Many Requests",
        )
        assert error.output == "429 Too Many Requests"

    def test_backend_name_attribute(self):
        """Backend name attribute is stored correctly."""
        error = BackendRateLimitError(
            "Rate limit hit",
            backend_name="Auggie",
        )
        assert error.backend_name == "Auggie"

    def test_output_default_empty_string(self):
        """Output defaults to empty string."""
        error = BackendRateLimitError("Rate limit hit")
        assert error.output == ""

    def test_backend_name_default_empty_string(self):
        """Backend name defaults to empty string."""
        error = BackendRateLimitError("Rate limit hit")
        assert error.backend_name == ""

    def test_all_attributes_set(self):
        """All attributes can be set together."""
        error = BackendRateLimitError(
            "Rate limit detected",
            output="Error 429",
            backend_name="Claude",
        )
        assert str(error) == "Rate limit detected"
        assert error.output == "Error 429"
        assert error.backend_name == "Claude"

    def test_has_default_exit_code(self):
        """Error has GENERAL_ERROR exit code."""
        from ingot.utils.errors import ExitCode

        error = BackendRateLimitError("Rate limit hit")
        assert error.exit_code == ExitCode.GENERAL_ERROR

    def test_can_be_raised_and_caught(self):
        """Error can be raised and caught in try/except."""
        with pytest.raises(BackendRateLimitError) as exc_info:
            raise BackendRateLimitError(
                "Rate limit hit",
                output="429",
                backend_name="Auggie",
            )
        assert exc_info.value.output == "429"
        assert exc_info.value.backend_name == "Auggie"


class TestBackendNotInstalledError:
    """Tests for BackendNotInstalledError."""

    def test_inherits_from_spec_error(self):
        """Error inherits from IngotError."""
        error = BackendNotInstalledError("CLI not found")
        assert isinstance(error, IngotError)

    def test_message_stored(self):
        """Message is stored correctly."""
        error = BackendNotInstalledError("Claude CLI is not installed")
        assert str(error) == "Claude CLI is not installed"

    def test_has_default_exit_code(self):
        """Error has GENERAL_ERROR exit code."""
        from ingot.utils.errors import ExitCode

        error = BackendNotInstalledError("CLI not found")
        assert error.exit_code == ExitCode.GENERAL_ERROR

    def test_can_be_raised_and_caught(self):
        """Error can be raised and caught in try/except."""
        with pytest.raises(BackendNotInstalledError) as exc_info:
            raise BackendNotInstalledError("Claude CLI is not installed")
        assert str(exc_info.value) == "Claude CLI is not installed"


class TestBackendNotConfiguredError:
    """Tests for BackendNotConfiguredError."""

    def test_inherits_from_spec_error(self):
        """Error inherits from IngotError."""
        error = BackendNotConfiguredError("No backend configured")
        assert isinstance(error, IngotError)

    def test_message_stored(self):
        """Message is stored correctly."""
        error = BackendNotConfiguredError("Run 'ingot init' to configure")
        assert str(error) == "Run 'ingot init' to configure"

    def test_has_default_exit_code(self):
        """Error has GENERAL_ERROR exit code."""
        from ingot.utils.errors import ExitCode

        error = BackendNotConfiguredError("No backend configured")
        assert error.exit_code == ExitCode.GENERAL_ERROR

    def test_can_be_raised_and_caught(self):
        """Error can be raised and caught in try/except."""
        with pytest.raises(BackendNotConfiguredError) as exc_info:
            raise BackendNotConfiguredError("No backend configured")
        assert str(exc_info.value) == "No backend configured"


class TestBackendTimeoutError:
    """Tests for BackendTimeoutError."""

    def test_inherits_from_spec_error(self):
        """Error inherits from IngotError."""
        error = BackendTimeoutError("Execution timed out")
        assert isinstance(error, IngotError)

    def test_message_stored(self):
        """Message is stored correctly."""
        error = BackendTimeoutError("Timed out after 120 seconds")
        assert str(error) == "Timed out after 120 seconds"

    def test_timeout_seconds_attribute(self):
        """Timeout seconds attribute is stored correctly."""
        error = BackendTimeoutError(
            "Timed out",
            timeout_seconds=120.0,
        )
        assert error.timeout_seconds == 120.0

    def test_timeout_seconds_default_none(self):
        """Timeout seconds defaults to None."""
        error = BackendTimeoutError("Timed out")
        assert error.timeout_seconds is None

    def test_has_default_exit_code(self):
        """Error has GENERAL_ERROR exit code."""
        from ingot.utils.errors import ExitCode

        error = BackendTimeoutError("Execution timed out")
        assert error.exit_code == ExitCode.GENERAL_ERROR

    def test_can_be_raised_and_caught(self):
        """Error can be raised and caught in try/except."""
        with pytest.raises(BackendTimeoutError) as exc_info:
            raise BackendTimeoutError("Timed out", timeout_seconds=60.0)
        assert exc_info.value.timeout_seconds == 60.0


class TestErrorImports:
    """Tests for error module exports."""

    def test_all_errors_importable_from_package(self):
        """All errors can be imported from backends package."""
        from ingot.integrations.backends import (
            BackendNotConfiguredError,
            BackendNotInstalledError,
            BackendRateLimitError,
            BackendTimeoutError,
        )

        # Verify they're the correct classes
        assert BackendRateLimitError.__name__ == "BackendRateLimitError"
        assert BackendNotInstalledError.__name__ == "BackendNotInstalledError"
        assert BackendNotConfiguredError.__name__ == "BackendNotConfiguredError"
        assert BackendTimeoutError.__name__ == "BackendTimeoutError"
```

### Running Tests

```bash
# Run backend error tests
pytest tests/test_backend_errors.py -v

# Run with coverage
pytest tests/test_backend_errors.py --cov=ingot.integrations.backends -v

# Verify no regressions in existing tests
pytest tests/ -v
```

---

## Acceptance Criteria

### From Linear Ticket AMI-47

| AC | Description | Verification Method | Status |
|----|-------------|---------------------|--------|
| **AC1** | `ingot/integrations/backends/__init__.py` created (package init) | File exists | [ ] |
| **AC2** | `ingot/integrations/backends/errors.py` created with all 4 error types | File exists with classes | [ ] |
| **AC3** | All errors extend `IngotError` | `isinstance(error, IngotError)` returns True | [ ] |
| **AC4** | `BackendRateLimitError` has `output` and `backend_name` attributes | Unit test verification | [ ] |
| **AC5** | `BackendTimeoutError` has `timeout_seconds` attribute | Unit test verification | [ ] |
| **AC6** | Unit tests for error initialization and attribute access | Tests pass | [ ] |

### Additional Quality Criteria

| QC | Description | Validation Method |
|----|-------------|-------------------|
| **QC1** | Module docstring explains purpose | Code review |
| **QC2** | All error classes have docstrings | Code inspection |
| **QC3** | `__all__` exports defined correctly | Import verification |
| **QC4** | Type hints on all method parameters | mypy check |
| **QC5** | Code follows existing codebase patterns | Code review |
| **QC6** | No import cycles introduced | Import test |
| **QC7** | All errors have `GENERAL_ERROR` exit code | Unit test verification |
| **QC8** | All errors can be raised and caught in try/except | Unit test verification |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import cycle between `errors.py` and `base.py` (future) | Low | Medium | errors.py has no dependencies on other backends modules |
| Confusion between `BackendNotInstalledError` and `AuggieNotInstalledError` | Low | Low | Different namespaces; clear naming |
| Future error types might need different exit codes | Low | Low | Can add `_default_exit_code` override when needed |
| Tests for new error types not comprehensive | Low | Medium | Test template provided; follow TDD |

---

## Verification Commands

After implementation, run these commands to verify:

```bash
# 1. Verify package structure created
ls -la ingot/integrations/backends/
# Expected: __init__.py, errors.py

# 2. Verify errors are importable
python -c "
from ingot.integrations.backends import (
    BackendRateLimitError,
    BackendNotInstalledError,
    BackendNotConfiguredError,
    BackendTimeoutError,
)
print('✅ All errors importable from package')
"

# 3. Verify IngotError inheritance
python -c "
from ingot.integrations.backends.errors import BackendRateLimitError
from ingot.utils.errors import IngotError
assert issubclass(BackendRateLimitError, IngotError)
print('✅ BackendRateLimitError inherits from IngotError')
"

# 4. Verify attributes
python -c "
from ingot.integrations.backends.errors import BackendRateLimitError, BackendTimeoutError

error1 = BackendRateLimitError('test', output='429', backend_name='Auggie')
assert error1.output == '429'
assert error1.backend_name == 'Auggie'
print('✅ BackendRateLimitError has output and backend_name')

error2 = BackendTimeoutError('test', timeout_seconds=120.0)
assert error2.timeout_seconds == 120.0
print('✅ BackendTimeoutError has timeout_seconds')
"

# 5. Run unit tests
pytest tests/test_backend_errors.py -v

# 6. Run type checking
mypy ingot/integrations/backends/errors.py
```

---

## Definition of Done

- [ ] `ingot/integrations/backends/__init__.py` created with exports
- [ ] `ingot/integrations/backends/errors.py` created with all 4 error types
- [ ] All error types inherit from `IngotError`
- [ ] `BackendRateLimitError` has `output` and `backend_name` attributes
- [ ] `BackendTimeoutError` has `timeout_seconds` attribute
- [ ] All errors have `GENERAL_ERROR` exit code (verified by tests)
- [ ] All errors can be raised and caught in try/except (verified by tests)
- [ ] Unit tests created in `tests/test_backend_errors.py`
- [ ] All tests pass
- [ ] mypy reports no type errors
- [ ] Code review approved
- [ ] AMI-47 ticket moved to Done

---

## Estimated Effort

| Phase | Description | Estimate |
|-------|-------------|----------|
| Phase 1 | Create package structure (`__init__.py`) | 0.05 day |
| Phase 2 | Create `errors.py` with all error types | 0.1 day |
| Testing | Create unit tests for all error types | 0.1 day |
| Validation | Run verification commands | 0.05 day |
| **Total** | | **~0.3 day** |

---

## References

### Code References

| File | Relevant Code |
|------|--------------|
| `ingot/utils/errors.py` | `IngotError` base class, `ExitCode` enum |
| `ingot/integrations/auggie.py:140-146` | Current `AuggieRateLimitError` (to be replaced) |
| `ingot/workflow/step3_execute.py:877-881` | Current rate limit error handling |
| `ingot/utils/retry.py:145-172` | `_is_retryable_error()` function |

### Specification References

| Document | Section |
|----------|---------|
| [Pluggable Multi-Agent Support.md](./Pluggable%20Multi-Agent%20Support.md) | Phase 1.1 (lines 1242-1295) |
| [Pluggable Multi-Agent Support.md](./Pluggable%20Multi-Agent%20Support.md) | Phase 6: Rate Limit Handling (lines 3924-3940) |

### Related Implementation Plans

| Document | Purpose |
|----------|---------|
| [AMI-44-implementation-plan.md](./AMI-44-implementation-plan.md) | Baseline behavior tests (upstream) |
| [AMI-46-implementation-plan.md](./AMI-46-implementation-plan.md) | Claude platform enum rename (sibling) |

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-31 | AI Assistant | Initial draft created |
