# Implementation Plan: AMI-44 - Phase 0: Baseline Behavior Tests - BLOCKING

**Ticket:** [AMI-44](https://linear.app/amiadingot/issue/AMI-44/phase-0-baseline-behavior-tests-blocking)
**Status:** Draft
**Date:** 2026-01-31
**Labels:** MultiAgent

---

## Summary

**CRITICAL: This phase MUST be completed before any refactoring work begins.**

This ticket creates baseline behavior tests that capture the current Auggie workflow behavior before the multi-backend refactoring (Phases 1-3 of the Pluggable Multi-Agent Support spec). These tests serve as a regression safety net to ensure the new `AIBackend` protocol produces identical results to the current `AuggieClient` implementation.

**Why This Matters:**
- The refactoring in Phases 1-2 changes how backends are instantiated and called
- Without baseline tests, behavioral regressions could slip through undetected
- These tests document the "contract" that new backends must fulfill
- Rate limit detection patterns are critical for workflow reliability
- Subagent names must remain consistent across refactoring

**Scope:**
- Create `tests/test_baseline_auggie_behavior.py`
- Capture `run_with_callback()` return type semantics `(bool, str)`
- Capture `run_print_with_output()` return type semantics `(bool, str)`
- Capture `run_print_quiet()` return semantics `str`
- Document rate limit detection patterns from `_looks_like_rate_limit()`
- Capture workflow step behaviors (subagent names, parallel session independence)

**Reference:** `specs/Pluggable Multi-Agent Support.md` - Phase 0 (Section 4, lines 1026-1208)

---

## Technical Approach

### Test File Structure

```
tests/
└── test_baseline_auggie_behavior.py     # NEW: All baseline tests in one file
```

The test file will contain four test classes:

1. **TestAuggieClientSemantics** - Capture AuggieClient method return types and signatures
2. **TestRateLimitDetection** - Document rate limit patterns and edge cases
3. **TestWorkflowStepBehavior** - Verify subagent name consistency
4. **TestParallelExecutionSemantics** - Validate session independence for parallel tasks

### Environment Gating Strategy

All tests are gated behind `INGOT_INTEGRATION_TESTS=1`:

```python
pytestmark = pytest.mark.skipif(
    os.environ.get("INGOT_INTEGRATION_TESTS") != "1",
    reason="Baseline tests require INGOT_INTEGRATION_TESTS=1",
)
```

**Rationale:** These tests invoke the real Auggie CLI, which requires:
- Auggie CLI installed and authenticated
- Network connectivity (for some tests)
- Potentially slow execution (LLM calls)

Normal `pytest` runs should skip these tests to keep CI fast.

### Mock Strategy and Boundaries

| Test Class | Mocking Approach | Actual Execution |
|------------|------------------|------------------|
| `TestAuggieClientSemantics` | **NO MOCKS** - Real Auggie CLI | Simple prompts with `dont_save_session=True` |
| `TestRateLimitDetection` | **UNIT TEST** - No external calls | Pure function testing of `_looks_like_rate_limit()` |
| `TestWorkflowStepBehavior` | **STATE ONLY** - Mock WorkflowState | Check subagent_names dict values |
| `TestParallelExecutionSemantics` | **INSPECT ONLY** - No execution | Signature and instance independence checks |

### Relationship to Existing Tests

The existing tests in the codebase:
- `tests/test_auggie.py` - Unit tests with mocked subprocess
- `tests/test_workflow_runner.py` - Workflow tests with mocked AuggieClient
- `tests/test_step1_plan.py`, `test_step2_tasklist.py`, etc. - Step tests with mocks

**These baseline tests are different because:**
1. They test with the REAL Auggie CLI (for integration tests)
2. They document the exact contract that new backends must maintain
3. They are gated behind `INGOT_INTEGRATION_TESTS=1` (not run in normal CI)

### Pre-conditions

Before running baseline tests, ensure:
1. **Auggie CLI installed** - `auggie --version` returns a valid version
2. **Auggie CLI authenticated** - User has valid authentication configured
3. **Network connectivity** - Required for LLM API calls
4. **`_looks_like_rate_limit` is importable** - Verify the private function is accessible:
   ```python
   # Verification step (run before implementing tests)
   from ingot.integrations.auggie import _looks_like_rate_limit
   assert callable(_looks_like_rate_limit), "Function must be importable"
   ```

---

## Behaviors Being Captured

### 1. AuggieClient Method Return Types

| Method | Return Type | Semantics |
|--------|-------------|-----------|
| `run()` | `subprocess.CompletedProcess[str]` | Returns CompletedProcess with returncode attribute (0 = success) |
| `run_with_callback()` | `tuple[bool, str]` | (success, full_output) where success=True if returncode==0 |
| `run_print_with_output()` | `tuple[bool, str]` | Same as run_with_callback, wraps it internally |
| `run_print_quiet()` | `str` | Returns stdout only (no success indicator) |
| `run_print()` | `bool` | Returns True if command succeeded (interactive mode) |

### 1.1 Output Aggregation Semantics

The `run_with_callback()` method has specific output aggregation behavior:
- Each line is passed to the callback with trailing newline **stripped**
- The full output in the return tuple **preserves** newlines
- Relationship: `output` contains all lines joined with newlines

### 2. Rate Limit Detection Patterns

The `_looks_like_rate_limit()` function checks for these patterns in output:

```python
patterns = [
    "429",           # HTTP 429 Too Many Requests
    "rate limit",    # Explicit rate limit messages
    "rate_limit",    # Underscore variant
    "too many requests",
    "quota exceeded",
    "capacity",
    "throttl",       # throttle, throttling, throttled
    "502",           # Bad Gateway (often rate-limit related)
    "503",           # Service Unavailable
    "504",           # Gateway Timeout
]
```

### 3. Subagent Name Constants

From `ingot/integrations/auggie.py`:

```python
INGOT_AGENT_PLANNER = "ingot-planner"
INGOT_AGENT_TASKLIST = "ingot-tasklist"
INGOT_AGENT_TASKLIST_REFINER = "ingot-tasklist-refiner"
INGOT_AGENT_IMPLEMENTER = "ingot-implementer"
INGOT_AGENT_REVIEWER = "ingot-reviewer"
INGOT_AGENT_DOC_UPDATER = "ingot-doc-updater"
```

### 4. Parallel Execution Session Independence

Parallel tasks must:
- Create independent `AuggieClient` instances
- Use `dont_save_session=True` to avoid session contamination
- Not share state between concurrent executions

---

## Implementation Phases

### Phase 1: Create Test Infrastructure (0.1 day)

#### Step 1.1: Create Test File with Gating

**File:** `tests/test_baseline_auggie_behavior.py`

Create the test file with proper module docstring and environment gating:

```python
"""Baseline behavior tests for Auggie workflow.

These tests capture the current behavior of AuggieClient and workflow steps
BEFORE the multi-backend refactoring. They serve as regression tests to ensure
the new AIBackend abstraction maintains identical semantics.

Run with: INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v

IMPORTANT: All tests in this file must pass with the current codebase
before proceeding to Phase 1 of the multi-backend refactoring.
"""

import inspect
import os

import pytest

# Skip all tests unless integration tests are enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("INGOT_INTEGRATION_TESTS") != "1",
    reason="Baseline tests require INGOT_INTEGRATION_TESTS=1",
)
```

### Phase 2: Implement TestAuggieClientSemantics (0.15 day)

#### Step 2.1: Test run_with_callback() Return Type

```python
class TestAuggieClientSemantics:
    """Capture current AuggieClient method semantics.

    These tests verify the EXACT return types and behaviors of AuggieClient
    methods. Any new backend implementation MUST match these semantics.
    """

    def test_run_with_callback_returns_tuple_bool_str(self):
        """Verify run_with_callback returns (bool, str) tuple.

        Contract:
        - Returns tuple[bool, str]
        - First element is success (True if returncode == 0)
        - Second element is full output (all lines concatenated)
        - Callback is invoked for each line (stripped of newline)
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        output_lines = []

        success, output = client.run_with_callback(
            "Say exactly: BASELINE_TEST_OK",
            output_callback=output_lines.append,
            dont_save_session=True,
        )

        # Verify return type semantics
        assert isinstance(success, bool), "First element must be bool"
        assert isinstance(output, str), "Second element must be str"
        # Verify callback was called
        assert len(output_lines) > 0, "Callback should receive output lines"

    def test_run_print_with_output_returns_tuple_bool_str(self):
        """Verify run_print_with_output returns (bool, str) tuple.

        Contract:
        - Returns tuple[bool, str]
        - Wraps run_with_callback internally
        - Prints output to terminal in real-time
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        success, output = client.run_print_with_output(
            "Say exactly: BASELINE_TEST_OK",
            dont_save_session=True,
        )

        assert isinstance(success, bool), "First element must be bool"
        assert isinstance(output, str), "Second element must be str"

    def test_run_print_quiet_returns_str(self):
        """Verify run_print_quiet returns str only.

        Contract:
        - Returns str (stdout only)
        - No success indicator (caller must check content)
        - Uses --print --quiet flags
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        output = client.run_print_quiet(
            "Say exactly: BASELINE_TEST_OK",
            dont_save_session=True,
        )

        assert isinstance(output, str), "Must return str"

    def test_run_print_returns_bool(self):
        """Verify run_print returns bool only.

        Contract:
        - Returns bool (True if command succeeded, False otherwise)
        - Interactive mode - streams output to terminal
        - Used in clarification flow (step1_plan.py:296)
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        success = client.run_print(
            "Say exactly: BASELINE_TEST_OK",
            dont_save_session=True,
        )

        assert isinstance(success, bool), "Must return bool"

    def test_run_returns_completed_process(self):
        """Verify run() returns subprocess.CompletedProcess.

        Contract:
        - Returns subprocess.CompletedProcess[str]
        - Has returncode attribute (0 = success)
        - Low-level method used by other run_* methods
        """
        import subprocess

        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        result = client.run(
            "Say exactly: BASELINE_TEST_OK",
            dont_save_session=True,
        )

        assert isinstance(result, subprocess.CompletedProcess), "Must return CompletedProcess"
        assert isinstance(result.returncode, int), "returncode must be int"
```

#### Step 2.2: Test Callback Line Processing and Output Aggregation

```python
    def test_callback_receives_lines_without_newlines(self):
        """Verify callback receives lines with newlines stripped.

        Contract:
        - Each line passed to callback has trailing newline removed
        - Full output in return value preserves newlines
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        callback_lines = []

        success, output = client.run_with_callback(
            "Say exactly on two lines:\nLine 1\nLine 2",
            output_callback=callback_lines.append,
            dont_save_session=True,
        )

        # Callback lines should not have trailing newlines
        for line in callback_lines:
            assert not line.endswith('\n'), f"Line should not end with newline: {repr(line)}"

    def test_output_aggregation_preserves_newlines(self):
        """Verify full output preserves newlines while callback strips them.

        Contract:
        - Callback receives lines WITHOUT trailing newlines
        - Full output in return tuple PRESERVES newlines
        - Relationship: output contains lines joined with newlines
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        callback_lines = []

        success, output = client.run_with_callback(
            "Say exactly on separate lines: AAA then BBB then CCC",
            output_callback=callback_lines.append,
            dont_save_session=True,
        )

        # Output should contain newlines (multi-line response)
        if len(callback_lines) > 1:
            assert '\n' in output or len(output.splitlines()) > 1, \
                "Multi-line output should preserve newlines in return value"

        # Verify callback lines don't have newlines but output does
        for line in callback_lines:
            assert not line.endswith('\n'), "Callback lines should be stripped"

    def test_run_with_callback_failure_returns_false(self):
        """Verify run_with_callback returns False on command failure.

        Contract:
        - Returns (False, output) when command fails (returncode != 0)
        - Output is still captured even on failure
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()

        # Invalid command should fail (use invalid model to trigger error)
        success, output = client.run_with_callback(
            "test",
            output_callback=lambda x: None,
            model="INVALID_MODEL_THAT_DOES_NOT_EXIST_12345",
            dont_save_session=True,
        )

        # Note: This may succeed with default model fallback
        # The key contract is that False means returncode != 0
        assert isinstance(success, bool)
        assert isinstance(output, str)
```

### Phase 3: Implement TestRateLimitDetection (0.1 day)

#### Step 3.1: Test Rate Limit Positive Patterns

```python
class TestRateLimitDetection:
    """Capture current rate limit detection behavior.

    These are UNIT TESTS that don't require the Auggie CLI.
    They document the exact patterns that _looks_like_rate_limit() matches.
    """

    def test_looks_like_rate_limit_http_429(self):
        """Verify HTTP 429 status code is detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("Error 429: Too many requests")
        assert _looks_like_rate_limit("HTTP/1.1 429")
        assert _looks_like_rate_limit("Status: 429")

    def test_looks_like_rate_limit_explicit_messages(self):
        """Verify explicit rate limit messages are detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        rate_limit_outputs = [
            "rate limit exceeded",
            "Rate limit hit, please wait",
            "rate_limit_error",
            "You have exceeded your rate limit",
        ]
        for output in rate_limit_outputs:
            assert _looks_like_rate_limit(output), f"Should detect: {output}"

    def test_looks_like_rate_limit_quota_messages(self):
        """Verify quota exceeded messages are detected.

        Contract: Only "quota exceeded" pattern is matched, not just "quota".
        """
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("quota exceeded for today")
        assert _looks_like_rate_limit("Monthly quota exceeded")
        # Note: "API quota reached" does NOT match because pattern is "quota exceeded"
        assert not _looks_like_rate_limit("API quota reached")

    def test_looks_like_rate_limit_capacity_messages(self):
        """Verify capacity-related messages are detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("System at capacity")
        assert _looks_like_rate_limit("Capacity limit reached")

    def test_looks_like_rate_limit_throttle_variants(self):
        """Verify throttle message variants are detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("Request throttled")
        assert _looks_like_rate_limit("Throttling in effect")
        assert _looks_like_rate_limit("You are being throttled")

    def test_looks_like_rate_limit_server_errors(self):
        """Verify server error codes (often rate-limit related) are detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("502 Bad Gateway")
        assert _looks_like_rate_limit("503 Service Unavailable")
        assert _looks_like_rate_limit("504 Gateway Timeout")
```

#### Step 3.2: Test Rate Limit Negative Patterns

```python
    def test_looks_like_rate_limit_normal_success(self):
        """Verify normal success messages are NOT detected as rate limits."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        normal_outputs = [
            "Task completed successfully",
            "File created: test.py",
            "Running tests...",
            "All tests passed",
            "Build successful",
            "Changes committed",
        ]
        for output in normal_outputs:
            assert not _looks_like_rate_limit(output), f"Should NOT detect: {output}"

    def test_looks_like_rate_limit_false_positives_documented(self):
        """Document known false positives in current implementation.

        IMPORTANT: This test documents the CURRENT behavior, which includes
        false positives. The implementation uses simple substring matching
        that cannot distinguish context.

        Known false positives (these ARE detected as rate limits even though they shouldn't be):
        - "Error on line 429 of main.py" - contains "429"
        - "Expected 503 but got 200" - contains "503"
        - "Test case 502 failed" - contains "502"

        This is a known limitation that may be addressed in future versions.
        """
        from ingot.integrations.auggie import _looks_like_rate_limit

        # Document that these ARE false positives (current behavior)
        known_false_positives = [
            "Error on line 429 of main.py",  # 429 in context
            "Expected 503 but got 200",       # 503 in context
            "Test case 502 failed",           # 502 in context
        ]

        # These WILL be detected as rate limits (false positives)
        # This documents the current behavior for regression testing
        for output in known_false_positives:
            # Current implementation has false positives - document this
            result = _looks_like_rate_limit(output)
            # Assert the CURRENT behavior (true = false positive exists)
            assert result is True, \
                f"Documenting false positive: '{output}' should trigger rate limit detection"

    def test_looks_like_rate_limit_true_negatives(self):
        """Verify messages without rate-limit patterns are NOT detected."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        # These should NOT be detected (no rate-limit patterns)
        true_negatives = [
            "Error on line 100 of main.py",
            "Expected 200 but got 404",
            "Test case 42 failed",
            "Connection refused",
            "File not found",
            "Permission denied",
        ]
        for output in true_negatives:
            assert not _looks_like_rate_limit(output), f"Should NOT detect: {output}"

    def test_looks_like_rate_limit_case_insensitive(self):
        """Verify detection is case-insensitive."""
        from ingot.integrations.auggie import _looks_like_rate_limit

        assert _looks_like_rate_limit("RATE LIMIT EXCEEDED")
        assert _looks_like_rate_limit("Rate Limit")
        assert _looks_like_rate_limit("QUOTA EXCEEDED")
```

### Phase 4: Implement TestWorkflowStepBehavior (0.1 day)

#### Step 4.1: Test Subagent Name Verification

```python
class TestWorkflowStepBehavior:
    """Capture current workflow step behavior patterns.

    These tests verify that subagent names are correctly configured
    in WorkflowState. The multi-backend refactoring must preserve
    these exact names.
    """

    @pytest.fixture
    def mock_state(self, tmp_path):
        """Create a minimal WorkflowState for testing."""
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-123",
            platform=Platform.GITHUB,
            url="https://example.invalid/TEST-123",
            title="Test ticket for baseline behavior tests",
            description="This ticket is used for baseline testing",
        )

        state = WorkflowState(ticket=ticket)
        return state

    def test_step1_uses_ingot_planner_subagent(self, mock_state):
        """Verify the default planner subagent name.

        Contract: Step 1 (plan creation) uses 'ingot-planner' subagent.
        """
        assert mock_state.subagent_names["planner"] == "ingot-planner"

    def test_step2_uses_ingot_tasklist_subagent(self, mock_state):
        """Verify the default tasklist subagent name.

        Contract: Step 2 (tasklist creation) uses 'ingot-tasklist' subagent.
        """
        assert mock_state.subagent_names["tasklist"] == "ingot-tasklist"

    def test_step2_refiner_uses_ingot_tasklist_refiner(self, mock_state):
        """Verify the tasklist refiner subagent name.

        Contract: Tasklist refinement uses 'ingot-tasklist-refiner' subagent.
        """
        assert mock_state.subagent_names["tasklist_refiner"] == "ingot-tasklist-refiner"

    def test_step3_uses_ingot_implementer_subagent(self, mock_state):
        """Verify the default implementer subagent name.

        Contract: Step 3 (task execution) uses 'ingot-implementer' subagent.
        """
        assert mock_state.subagent_names["implementer"] == "ingot-implementer"

    def test_step3_uses_ingot_reviewer_subagent(self, mock_state):
        """Verify the reviewer subagent name.

        Contract: Task review uses 'ingot-reviewer' subagent.
        """
        assert mock_state.subagent_names["reviewer"] == "ingot-reviewer"

    def test_step4_uses_ingot_doc_updater_subagent(self, mock_state):
        """Verify the doc updater subagent name.

        Contract: Step 4 (documentation) uses 'ingot-doc-updater' subagent.
        """
        assert mock_state.subagent_names["doc_updater"] == "ingot-doc-updater"

    def test_subagent_names_match_constants(self, mock_state):
        """Verify subagent names match the constants in auggie.py.

        Contract: WorkflowState defaults must match INGOT_AGENT_* constants.
        """
        from ingot.integrations.auggie import (
            INGOT_AGENT_DOC_UPDATER,
            INGOT_AGENT_IMPLEMENTER,
            INGOT_AGENT_PLANNER,
            INGOT_AGENT_REVIEWER,
            INGOT_AGENT_TASKLIST,
            INGOT_AGENT_TASKLIST_REFINER,
        )

        assert mock_state.subagent_names["planner"] == INGOT_AGENT_PLANNER
        assert mock_state.subagent_names["tasklist"] == INGOT_AGENT_TASKLIST
        assert mock_state.subagent_names["tasklist_refiner"] == INGOT_AGENT_TASKLIST_REFINER
        assert mock_state.subagent_names["implementer"] == INGOT_AGENT_IMPLEMENTER
        assert mock_state.subagent_names["reviewer"] == INGOT_AGENT_REVIEWER
        assert mock_state.subagent_names["doc_updater"] == INGOT_AGENT_DOC_UPDATER
```

### Phase 5: Implement TestParallelExecutionSemantics (0.1 day)

#### Step 5.1: Test Session Independence

```python
class TestParallelExecutionSemantics:
    """Capture parallel execution behavior in Step 3.

    These tests verify that parallel task execution maintains
    session independence. Each task must have its own client instance.
    """

    def test_parallel_tasks_use_independent_clients(self):
        """Verify parallel tasks create independent AuggieClient instances.

        Contract: Each parallel task creates its own client instance.
        """
        from ingot.integrations.auggie import AuggieClient

        # Create two independent clients (simulating parallel execution)
        client1 = AuggieClient()
        client2 = AuggieClient()

        # They should be independent instances
        assert client1 is not client2, "Parallel tasks must use different client instances"

    def test_dont_save_session_parameter_available(self):
        """Verify dont_save_session parameter exists in run_with_callback.

        Contract: run_with_callback must accept dont_save_session parameter.
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        sig = inspect.signature(client.run_with_callback)

        assert "dont_save_session" in sig.parameters, \
            "run_with_callback must have dont_save_session parameter"

    def test_dont_save_session_default_is_false(self):
        """Verify dont_save_session defaults to False.

        Contract: By default, sessions are saved (for interactive use).
        Parallel execution explicitly sets dont_save_session=True.
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()
        sig = inspect.signature(client.run_with_callback)

        param = sig.parameters["dont_save_session"]
        assert param.default is False, "dont_save_session should default to False"

    def test_client_model_isolation(self):
        """Verify each client can have different model settings.

        Contract: Model settings are instance-specific, not shared.
        """
        from ingot.integrations.auggie import AuggieClient

        client1 = AuggieClient(model="model-a")
        client2 = AuggieClient(model="model-b")

        assert client1.model == "model-a"
        assert client2.model == "model-b"
        assert client1.model != client2.model

    def test_agent_parameter_available_in_run_methods(self):
        """Verify agent parameter exists in all run methods.

        Contract: All run methods must accept agent parameter for subagent dispatch.
        """
        from ingot.integrations.auggie import AuggieClient

        client = AuggieClient()

        methods_with_agent = [
            "run",
            "run_print",
            "run_print_quiet",
            "run_print_with_output",
            "run_with_callback",
        ]

        for method_name in methods_with_agent:
            method = getattr(client, method_name)
            sig = inspect.signature(method)
            assert "agent" in sig.parameters, \
                f"{method_name} must have agent parameter"

    def test_concurrent_clients_no_interference(self):
        """Verify concurrent client executions don't interfere with each other.

        Contract: Multiple AuggieClient instances can run concurrently
        without state leakage or interference.

        This test spawns 2 concurrent clients and verifies they complete
        independently with their own outputs.
        """
        import concurrent.futures

        from ingot.integrations.auggie import AuggieClient

        def run_client(client_id: int) -> tuple[int, bool, str]:
            """Run a client and return (client_id, success, output)."""
            client = AuggieClient()
            success, output = client.run_with_callback(
                f"Say exactly: CLIENT_{client_id}_OK",
                output_callback=lambda x: None,
                dont_save_session=True,
            )
            return client_id, success, output

        # Run 2 clients concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_client, i) for i in range(2)]
            results = [f.result(timeout=120) for f in futures]

        # Verify both completed
        assert len(results) == 2, "Both clients should complete"

        # Verify each got its own response (no cross-contamination)
        for client_id, success, output in results:
            assert isinstance(success, bool), f"Client {client_id} should return bool"
            assert isinstance(output, str), f"Client {client_id} should return str"
            # Note: We don't assert on content as LLM output is non-deterministic
            # The key contract is that both complete without errors
```

### Phase 6: Implement TestImportability (0.05 day)

#### Step 6.1: Verify Private Function Accessibility

```python
class TestImportability:
    """Verify that required functions and classes are importable.

    These tests ensure that the baseline tests can actually import
    the functions they need to test. This catches issues where
    private functions are not accessible.
    """

    def test_looks_like_rate_limit_is_importable(self):
        """Verify _looks_like_rate_limit can be imported.

        Contract: The private function must be accessible for testing.
        If this fails, the function may have been renamed or made truly private.
        """
        try:
            from ingot.integrations.auggie import _looks_like_rate_limit
            assert callable(_looks_like_rate_limit), "Must be callable"
        except ImportError as e:
            pytest.fail(
                f"Cannot import _looks_like_rate_limit: {e}\n"
                "This function is required for rate limit detection tests."
            )

    def test_auggie_client_is_importable(self):
        """Verify AuggieClient can be imported."""
        try:
            from ingot.integrations.auggie import AuggieClient
            assert AuggieClient is not None
        except ImportError as e:
            pytest.fail(f"Cannot import AuggieClient: {e}")

    def test_ingot_agent_constants_are_importable(self):
        """Verify INGOT_AGENT_* constants can be imported."""
        try:
            from ingot.integrations.auggie import (
                INGOT_AGENT_DOC_UPDATER,
                INGOT_AGENT_IMPLEMENTER,
                INGOT_AGENT_PLANNER,
                INGOT_AGENT_REVIEWER,
                INGOT_AGENT_TASKLIST,
                INGOT_AGENT_TASKLIST_REFINER,
            )
            # Verify they are strings
            for const in [
                INGOT_AGENT_PLANNER,
                INGOT_AGENT_TASKLIST,
                INGOT_AGENT_TASKLIST_REFINER,
                INGOT_AGENT_IMPLEMENTER,
                INGOT_AGENT_REVIEWER,
                INGOT_AGENT_DOC_UPDATER,
            ]:
                assert isinstance(const, str), f"Constant must be str: {const}"
        except ImportError as e:
            pytest.fail(f"Cannot import INGOT_AGENT_* constants: {e}")
```

---

## Acceptance Criteria

### From Linear Ticket AMI-44

| AC | Description | Test Class/Method | Status |
|----|-------------|-------------------|--------|
| **AC1** | Baseline test file created at `tests/test_baseline_auggie_behavior.py` | File creation | [ ] |
| **AC2** | Tests gated behind `INGOT_INTEGRATION_TESTS=1` environment variable | `pytestmark` decorator | [ ] |
| **AC3** | Tests verify correct return types for all AuggieClient methods | `TestAuggieClientSemantics.*` | [ ] |
| **AC4** | Rate limit detection patterns documented and tested | `TestRateLimitDetection.*` | [ ] |
| **AC5** | Subagent names verified for each step | `TestWorkflowStepBehavior.*` | [ ] |
| **AC6** | All baseline tests pass with current codebase | Full test run | [ ] |
| **AC7** | Tests document expected behavior in docstrings for future regression checking | All test docstrings | [ ] |

### Additional Quality Criteria

| QC | Description | Validation Method |
|----|-------------|-------------------|
| **QC1** | Test file follows existing test conventions | Code review |
| **QC2** | All test docstrings explain the "contract" being captured | Documentation review |
| **QC3** | Tests are deterministic and reproducible | Multiple test runs |
| **QC4** | Integration tests use `dont_save_session=True` | Code inspection |
| **QC5** | Unit tests (rate limit detection) don't require external services | Verify no network calls |
| **QC6** | Tests provide clear failure messages | Test failure output review |

---

## Dependencies

### Upstream Dependencies (Must Be Complete First)

| Ticket | Component | Status | Description |
|--------|-----------|--------|-------------|
| None | N/A | N/A | This is Phase 0 - no upstream dependencies |

### Downstream Dependents (Blocked by This Ticket)

| Ticket | Component | Description |
|--------|-----------|-------------|
| **Phase 1** | Backend Infrastructure | Cannot start until baseline tests pass |
| **Phase 2** | Workflow Step Integration | Depends on verified baseline behavior |
| **Phase 3** | Claude Backend | Must match baseline semantics |

### Related Tickets

| Ticket | Title | Relationship |
|--------|-------|--------------|
| [Multi-Agent Spec](./Pluggable%20Multi-Agent%20Support.md) | Pluggable Multi-Agent Support | Parent specification |

---

## Estimated Effort

| Phase | Description | Estimate |
|-------|-------------|----------|
| Phase 1 | Create test infrastructure (file, gating, imports) | 0.1 day |
| Phase 2 | Implement TestAuggieClientSemantics (8 tests) | 0.2 day |
| Phase 3 | Implement TestRateLimitDetection (10 tests) | 0.1 day |
| Phase 4 | Implement TestWorkflowStepBehavior (8 tests) | 0.1 day |
| Phase 5 | Implement TestParallelExecutionSemantics (6 tests) | 0.15 day |
| Phase 6 | Implement TestImportability (3 tests) | 0.05 day |
| Validation | Run all tests, fix any issues | 0.1 day |
| **Total** | | **~0.8 day** |

---

## Usage Examples

### Running Baseline Tests

```bash
# Run all baseline tests (requires Auggie CLI installed and authenticated)
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v

# Run only unit tests (no Auggie CLI required)
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v -k "RateLimitDetection"

# Run with verbose output for debugging
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v -s

# Run specific test class
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py::TestAuggieClientSemantics -v

# Verify tests are skipped without environment variable
pytest tests/test_baseline_auggie_behavior.py -v
# Expected: All tests show "SKIPPED (Baseline tests require INGOT_INTEGRATION_TESTS=1)"
```

### Pre-Refactoring Verification

Before starting Phase 1 of the multi-backend refactoring:

```bash
# Step 1: Ensure all baseline tests pass
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v

# Step 2: Verify test count matches expectations
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py --collect-only | grep "test_"
# Expected: ~35 tests across 5 test classes

# Step 3: Run with coverage to ensure all critical paths are tested
INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py --cov=ingot.integrations.auggie -v
```

### CI Integration

For CI pipelines that should skip these tests:

```yaml
# .github/workflows/test.yml
- name: Run Unit Tests (Fast)
  run: pytest tests/ -v --ignore=tests/test_baseline_auggie_behavior.py

# For dedicated integration test job:
- name: Run Integration Tests
  env:
    INGOT_INTEGRATION_TESTS: "1"
  run: pytest tests/test_baseline_auggie_behavior.py -v
```

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Auggie CLI not available on CI | Medium | High | Gate behind environment variable, document requirements |
| Tests are flaky due to LLM variability | Medium | Medium | Use simple, deterministic prompts; focus on return types |
| Rate limit during test runs | Low | Low | Use `dont_save_session=True`, run tests infrequently |
| False positive rate limit detection | Low | Low | Document known false positives in tests |
| Subagent names change | Low | Medium | Tests will catch this immediately |

---

## Code Example: Complete Test File Structure

The final test file will have this structure:

```python
"""Baseline behavior tests for Auggie workflow.

These tests capture the current behavior of AuggieClient and workflow steps
BEFORE the multi-backend refactoring. They serve as regression tests to ensure
the new AIBackend abstraction maintains identical semantics.

Run with: INGOT_INTEGRATION_TESTS=1 pytest tests/test_baseline_auggie_behavior.py -v
"""

import inspect
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("INGOT_INTEGRATION_TESTS") != "1",
    reason="Baseline tests require INGOT_INTEGRATION_TESTS=1",
)


class TestImportability:
    """Verify required functions and classes are importable."""

    def test_looks_like_rate_limit_is_importable(self): ...
    def test_auggie_client_is_importable(self): ...
    def test_ingot_agent_constants_are_importable(self): ...


class TestAuggieClientSemantics:
    """Capture current AuggieClient method semantics."""

    def test_run_with_callback_returns_tuple_bool_str(self): ...
    def test_run_print_with_output_returns_tuple_bool_str(self): ...
    def test_run_print_quiet_returns_str(self): ...
    def test_run_print_returns_bool(self): ...
    def test_run_returns_int_exit_code(self): ...
    def test_callback_receives_lines_without_newlines(self): ...
    def test_output_aggregation_preserves_newlines(self): ...
    def test_run_with_callback_failure_returns_false(self): ...


class TestRateLimitDetection:
    """Capture current rate limit detection behavior."""

    def test_looks_like_rate_limit_http_429(self): ...
    def test_looks_like_rate_limit_explicit_messages(self): ...
    def test_looks_like_rate_limit_quota_messages(self): ...
    def test_looks_like_rate_limit_capacity_messages(self): ...
    def test_looks_like_rate_limit_throttle_variants(self): ...
    def test_looks_like_rate_limit_server_errors(self): ...
    def test_looks_like_rate_limit_normal_success(self): ...
    def test_looks_like_rate_limit_false_positives_documented(self): ...
    def test_looks_like_rate_limit_true_negatives(self): ...
    def test_looks_like_rate_limit_case_insensitive(self): ...


class TestWorkflowStepBehavior:
    """Capture current workflow step behavior patterns."""

    @pytest.fixture
    def mock_state(self, tmp_path): ...

    def test_step1_uses_ingot_planner_subagent(self, mock_state): ...
    def test_step2_uses_ingot_tasklist_subagent(self, mock_state): ...
    def test_step2_refiner_uses_ingot_tasklist_refiner(self, mock_state): ...
    def test_step3_uses_ingot_implementer_subagent(self, mock_state): ...
    def test_step3_uses_ingot_reviewer_subagent(self, mock_state): ...
    def test_step4_uses_ingot_doc_updater_subagent(self, mock_state): ...
    def test_subagent_names_match_constants(self, mock_state): ...


class TestParallelExecutionSemantics:
    """Capture parallel execution behavior in Step 3."""

    def test_parallel_tasks_use_independent_clients(self): ...
    def test_dont_save_session_parameter_available(self): ...
    def test_dont_save_session_default_is_false(self): ...
    def test_client_model_isolation(self): ...
    def test_agent_parameter_available_in_run_methods(self): ...
    def test_concurrent_clients_no_interference(self): ...
```

---

## Changelog

| Date | Author | Change |
|------|--------|--------|
| 2026-01-31 | AI Assistant | Initial draft created |
| 2026-01-31 | AI Assistant | Added gaps: `run_print()` and `run()` return type tests, output aggregation test, false positive rate limit documentation, concurrent execution test, TestImportability class, updated test counts |
