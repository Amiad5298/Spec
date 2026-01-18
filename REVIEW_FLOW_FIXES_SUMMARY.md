# Review Flow Fixes - Summary

## Overview
This patch implements targeted fixes to the phase review feature (`--enable-review`) to address logic and UX issues in the review checkpoint flow.

## Changes Made

### A) User-Controlled Review Failure Stopping

**Problem**: `_run_phase_review()` always returned `True`, so the workflow could never actually stop on review failure.

**Solution**:
- Modified `_run_phase_review()` to return `False` when the user explicitly chooses to stop after a failed review
- Added a final prompt: "Continue workflow despite review issues?" (default: True)
- Only stops if user explicitly declines to continue
- Updated call sites in `step_3_execute()` to respect the return value:
  - Phase 1 review checkpoint (line 627-634): Stops workflow if review returns False
  - Final review checkpoint (line 687-694): Stops workflow if review returns False

**Behavior**:
- Review passes → continue automatically
- Review fails + user chooses auto-fix → continue after fix attempt
- Review fails + user declines to continue → workflow stops
- Review crashes (exception) → continue with warning (advisory behavior)

### B) Robust PASS/NEEDS_ATTENTION Parsing

**Problem**: Brittle string-contains parsing (`"PASS" in output and "NEEDS_ATTENTION" not in output`) prone to false positives.

**Solution**: Implemented `_parse_review_status()` function with robust parsing:

**Features**:
- Uses regex to find `**Status**: PASS` or `Status: NEEDS_ATTENTION` markers
- Handles bold markers (`**Status**` or plain `Status`)
- Case-insensitive matching
- Tolerant of whitespace variations
- Uses **last occurrence** as final verdict (handles multi-stage reviews)
- Fallback detection for standalone markers at end of output
- Fail-safe: returns `NEEDS_ATTENTION` for ambiguous/empty output

**Edge Cases Handled**:
- PASS appearing in normal text (e.g., "will PASS all tests") → ignored unless after Status: marker
- Multiple status markers → uses last one
- Empty output → returns NEEDS_ATTENTION
- Missing status marker → returns NEEDS_ATTENTION
- Mixed bold/plain markers → handles both

**Testing**: Added comprehensive test suite in `tests/test_review_parser.py` with 14 test cases covering all edge cases.

### C) Re-Review After Auto-Fix

**Problem**: After auto-fix, workflow just continued without verifying the fix worked.

**Solution**:
- After successful auto-fix, prompt user: "Run review again after auto-fix?" (default: True)
- If yes:
  - Re-run review checkpoint with updated diff
  - Parse new status (PASS or NEEDS_ATTENTION)
  - Report result to user
- If still NEEDS_ATTENTION after re-review:
  - Show warning: "Issues remain after auto-fix. Please review manually."
  - Fall through to continue prompt (advisory behavior)

**Flow**:
```
Review → NEEDS_ATTENTION
  ↓
Offer auto-fix? → Yes
  ↓
Run auto-fix
  ↓
Run review again? → Yes
  ↓
Re-review → PASS ✓ (continue)
         → NEEDS_ATTENTION (show warning, ask to continue)
```

### D) Advisory Behavior Preserved

**Principle**: Reviews are advisory by default; workflow only stops on explicit user choice.

**Implementation**:
- Review passes → continue automatically
- Review fails → offer auto-fix, then ask to continue (default: Yes)
- Review crashes → show warning, continue automatically
- User can always choose to continue despite issues
- Only stops when user explicitly chooses "No" to continue prompt

## Files Modified

1. **spec/workflow/step3_execute.py**:
   - Added `_parse_review_status()` function (lines 150-213)
   - Updated `_run_phase_review()` function (lines 428-532):
     - Use robust parser
     - Implement re-review after auto-fix
     - Return False when user chooses to stop
   - Updated Phase 1 review checkpoint (lines 627-634)
   - Updated Final review checkpoint (lines 687-694)

2. **tests/test_review_parser.py** (new file):
   - 14 comprehensive test cases for `_parse_review_status()`
   - All tests passing ✓

## Testing

Run the test suite:
```bash
python -m pytest tests/test_review_parser.py -v
```

All 14 tests pass successfully.

## Backward Compatibility

- No breaking changes to existing CLI flags or behavior
- `--enable-review` flag works as before
- When review is disabled, no changes to workflow
- When review is enabled, behavior is now more robust and user-friendly

## Example Usage

```bash
# Enable phase reviews
spec PROJECT-123 --enable-review

# Review flow:
# 1. After Phase 1 tasks complete → review runs
# 2. If NEEDS_ATTENTION → offer auto-fix
# 3. If auto-fix accepted → offer re-review
# 4. If still issues → ask to continue or stop
# 5. User controls whether to stop or continue
```

## Edge Case Handling

1. **Empty review output**: Treated as NEEDS_ATTENTION (fail-safe)
2. **Review agent crashes**: Show warning, continue workflow (advisory)
3. **Ambiguous status**: Defaults to NEEDS_ATTENTION (fail-safe)
4. **Multiple status markers**: Uses last one (final verdict)
5. **Auto-fix fails**: Still offers to continue (advisory)
6. **Re-review crashes**: Show warning, ask to continue (advisory)

## Design Principles

1. **Minimal changes**: Focused fixes, no large refactors
2. **Fail-safe defaults**: Ambiguous cases default to NEEDS_ATTENTION
3. **User control**: User always has final say on stopping
4. **Advisory by default**: Reviews don't block unless user chooses
5. **Robust parsing**: Handles real-world agent output variations

