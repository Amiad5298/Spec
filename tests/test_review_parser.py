"""Tests for review status parser in ingot.workflow.review module.

Tests cover:
- Canonical Status: format (bold and non-bold)
- Bullet format (- **PASS** - description)
- Standalone markers near the end
- Multiple status markers (last one wins)
- False positive prevention (PASS in normal prose)
"""

from unittest.mock import MagicMock, call, patch

import pytest

from ingot.workflow.review import ExitReason, ReviewStatus, parse_review_status


class TestParseReviewStatusCanonical:
    def test_parse_pass_with_bold_markers(self):
        output = """## Task Review: Example Task

**Status**: PASS

**Summary**: Everything looks good!
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_parse_pass_without_bold_markers(self):
        output = """## Task Review: Example Task

Status: PASS

Summary: Everything looks good!
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_parse_needs_attention_with_bold_markers(self):
        output = """## Task Review: Example Task

**Status**: NEEDS_ATTENTION

**Issues**:
- Missing error handling
- Incomplete tests
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_parse_needs_attention_without_bold_markers(self):
        output = """## Task Review: Example Task

Status: NEEDS_ATTENTION

Issues:
- Missing error handling
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_case_insensitive_matching(self):
        assert parse_review_status("**Status**: pass\n\nLooks good!") == ReviewStatus.PASS
        assert parse_review_status("**Status**: Pass\n") == ReviewStatus.PASS
        assert parse_review_status("Status: needs_attention\n") == ReviewStatus.NEEDS_ATTENTION

    def test_whitespace_variations(self):
        assert parse_review_status("**Status**:    PASS   \n") == ReviewStatus.PASS
        assert parse_review_status("Status :PASS\n") == ReviewStatus.PASS
        assert parse_review_status("**Status** : NEEDS_ATTENTION") == ReviewStatus.NEEDS_ATTENTION


class TestParseReviewStatusBulletFormat:
    def test_bullet_pass_with_description(self):
        output = """## Review Complete

- **PASS** - Changes look good, ready to proceed
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_bullet_needs_attention_with_description(self):
        output = """## Review Complete

- **NEEDS_ATTENTION** - Issues found that should be addressed

**Issues**:
1. Missing test coverage
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_bullet_without_trailing_dash(self):
        output = """## Review

- **PASS**
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_bullet_needs_attention_without_trailing_dash(self):
        output = """## Review

- **NEEDS_ATTENTION**
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION


class TestParseReviewStatusStandalone:
    def test_standalone_bold_pass_at_end(self):
        output = """## Task Review

Everything looks good.

**PASS**
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_standalone_pass_at_end(self):
        output = """## Task Review

Everything looks good.

PASS
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_standalone_needs_attention_at_end(self):
        output = """## Task Review

Found some issues.

NEEDS_ATTENTION
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_standalone_bold_needs_attention_at_end(self):
        output = """## Task Review

Found issues.

**NEEDS_ATTENTION**
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION


class TestParseReviewStatusMultipleMarkers:
    def test_uses_last_status_marker(self):
        output = """## Initial Review

**Status**: NEEDS_ATTENTION

Issues found.

## After Fix

**Status**: PASS

All issues resolved!
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_both_markers_present_uses_last(self):
        output = """**Status**: PASS

Wait, actually found an issue.

**Status**: NEEDS_ATTENTION
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_mixed_bold_and_plain_markers(self):
        output = """Status: NEEDS_ATTENTION

After review:

**Status**: PASS
"""
        assert parse_review_status(output) == ReviewStatus.PASS

    def test_canonical_overrides_bullet_if_later(self):
        output = """- **NEEDS_ATTENTION** - Initial review

After fixes:

**Status**: PASS
"""
        assert parse_review_status(output) == ReviewStatus.PASS


class TestParseReviewStatusFalsePositives:
    def test_ignores_pass_in_normal_text(self):
        output = """## Task Review: Example Task

The implementation will PASS all tests once complete.

**Status**: NEEDS_ATTENTION

**Issues**:
- Tests not yet written
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_ignores_pass_in_sentence(self):
        output = """This will PASS the validation checks.

**Status**: NEEDS_ATTENTION
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_ignores_pass_without_status_marker(self):
        output = """## Review

The tests will PASS once you add the missing import.
Please fix the import and try again.
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_pass_in_code_block_ignored(self):
        output = """## Review

```python
assert result == "PASS"
```

No status marker here.
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION


class TestParseReviewStatusEdgeCases:
    def test_empty_output_returns_needs_attention(self):
        assert parse_review_status("") == ReviewStatus.NEEDS_ATTENTION
        assert parse_review_status("   ") == ReviewStatus.NEEDS_ATTENTION
        assert parse_review_status("\n\n") == ReviewStatus.NEEDS_ATTENTION

    def test_no_status_marker_returns_needs_attention(self):
        output = """## Task Review

Some review text without a clear status marker.
"""
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_none_input_handled(self):
        assert parse_review_status("") == ReviewStatus.NEEDS_ATTENTION

    def test_very_long_output_uses_last_500_chars_for_fallback(self):
        # Create long output with PASS early (should be ignored) and nothing at end
        preamble = "x" * 1000
        output = f"{preamble}\n\nPASS\n\n{'y' * 600}"
        # PASS is in the middle, not in last 500 chars, so should be NEEDS_ATTENTION
        assert parse_review_status(output) == ReviewStatus.NEEDS_ATTENTION

    def test_long_output_with_pass_at_end(self):
        preamble = "x" * 1000
        output = f"{preamble}\n\n**Status**: PASS\n"
        assert parse_review_status(output) == ReviewStatus.PASS


class TestBuildReviewPrompt:
    def test_builds_prompt_with_phase_and_diff(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "specs/TEST-123-plan.md"
        state.user_context = ""

        result = build_review_prompt(
            state=state,
            phase="fundamental",
            diff_output="diff --git a/file.py b/file.py\n+new line",
            is_truncated=False,
        )

        assert "fundamental" in result
        assert "specs/TEST-123-plan.md" in result
        assert "diff --git a/file.py b/file.py" in result
        assert "**Status**: PASS" in result
        assert "Large Changeset" not in result

    def test_includes_large_changeset_instructions_when_truncated(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "specs/PROJ-456-plan.md"
        state.user_context = ""

        result = build_review_prompt(
            state=state,
            phase="final",
            diff_output="file1.py | 10 ++++\nfile2.py | 5 ++",
            is_truncated=True,
        )

        assert "final" in result
        assert "Large Changeset" in result
        assert "git diff -- <file_path>" in result

    def test_includes_review_instructions(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "plan.md"
        state.user_context = ""

        result = build_review_prompt(
            state=state,
            phase="fundamental",
            diff_output="some diff",
            is_truncated=False,
        )

        assert "Review Instructions" in result
        assert "align with the implementation plan" in result
        assert "NEEDS_ATTENTION" in result

    def test_includes_user_context_when_provided(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "plan.md"
        state.user_context = "Focus on backward compatibility"

        result = build_review_prompt(
            state=state,
            phase="fundamental",
            diff_output="some diff",
            is_truncated=False,
        )

        assert "Additional Context" in result
        assert "Focus on backward compatibility" in result

    def test_excludes_user_context_when_empty(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "plan.md"
        state.user_context = ""

        result = build_review_prompt(
            state=state,
            phase="fundamental",
            diff_output="some diff",
            is_truncated=False,
        )

        assert "Additional Context" not in result

    def test_excludes_user_context_when_whitespace_only(self):
        from unittest.mock import MagicMock

        from ingot.workflow.review import build_review_prompt

        state = MagicMock()
        state.get_plan_path.return_value = "plan.md"
        state.user_context = "   \n  "

        result = build_review_prompt(
            state=state,
            phase="fundamental",
            diff_output="some diff",
            is_truncated=False,
        )

        assert "Additional Context" not in result


class TestGetDiffForReview:
    def test_uses_baseline_when_available(self):
        from unittest.mock import MagicMock, patch

        from ingot.workflow.review import _get_diff_for_review

        state = MagicMock()
        state.diff_baseline_ref = "abc123"

        with patch("ingot.workflow.review.get_smart_diff_from_baseline") as mock_baseline:
            mock_baseline.return_value = ("diff output", False, False)
            result = _get_diff_for_review(state)

            mock_baseline.assert_called_once_with("abc123", include_working_tree=True)
            assert result == ("diff output", False, False)

    def test_falls_back_to_smart_diff_when_no_baseline(self):
        from unittest.mock import MagicMock, patch

        from ingot.workflow.review import _get_diff_for_review

        state = MagicMock()
        state.diff_baseline_ref = None

        with patch("ingot.workflow.review.get_smart_diff") as mock_smart:
            mock_smart.return_value = ("legacy diff", True, False)
            result = _get_diff_for_review(state)

            mock_smart.assert_called_once()
            assert result == ("legacy diff", True, False)


class TestRunPhaseReview:
    def test_returns_true_when_no_changes(self):
        from unittest.mock import MagicMock, patch

        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None

        with patch("ingot.workflow.review.get_smart_diff") as mock_diff:
            mock_diff.return_value = ("", False, False)  # Empty diff
            with patch("ingot.workflow.review.print_info"):
                result = run_phase_review(state, MagicMock(), "fundamental", backend=MagicMock())

        assert result is True

    def test_returns_true_when_review_passes(self):
        from unittest.mock import MagicMock, patch

        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (True, "**Status**: PASS")

        with patch("ingot.workflow.review.get_smart_diff") as mock_diff:
            mock_diff.return_value = ("diff content", False, False)
            with patch("ingot.workflow.review.print_step"):
                with patch("ingot.workflow.review.print_success"):
                    result = run_phase_review(
                        state, MagicMock(), "fundamental", backend=mock_backend
                    )

        assert result is True

    def test_prompts_for_git_error(self):
        from unittest.mock import MagicMock, patch

        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None

        with patch("ingot.workflow.review.get_smart_diff") as mock_diff:
            mock_diff.return_value = ("", False, True)  # git_error=True
            with patch("ingot.workflow.review.prompt_confirm") as mock_confirm:
                mock_confirm.return_value = True  # User continues
                with patch("ingot.workflow.review.print_warning"):
                    with patch("ingot.workflow.review.print_info"):
                        with patch("ingot.workflow.review.print_step"):
                            result = run_phase_review(
                                state, MagicMock(), "final", backend=MagicMock()
                            )

        assert result is True
        mock_confirm.assert_called_once()

    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_returns_false_when_user_stops_after_git_error(
        self, mock_diff, mock_confirm, _warn, _info, _step
    ):
        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None

        mock_diff.return_value = ("", False, True)  # git_error=True
        mock_confirm.return_value = False  # User stops

        result = run_phase_review(state, MagicMock(), "final", backend=MagicMock())

        assert result is False

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_offers_autofix_on_needs_attention(self, mock_diff, mock_confirm, _step, _warn):
        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}
        state.max_review_fix_attempts = 3

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (
            True,
            "**Status**: NEEDS_ATTENTION\n**Issues**: 1. Bug",
        )

        mock_diff.return_value = ("diff content", False, False)
        # First confirm = auto-fix (No), second = continue (Yes)
        mock_confirm.side_effect = [False, True]

        result = run_phase_review(state, MagicMock(), "fundamental", backend=mock_backend)

        assert result is True
        # Should be called twice: auto-fix prompt and continue prompt
        assert mock_confirm.call_count == 2

    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review._run_review_fix_loop")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_runs_autofix_loop_when_user_accepts(
        self, mock_diff, mock_confirm, mock_loop, _step, _warn, _info
    ):
        from ingot.workflow.review import ReviewFixResult, run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}
        state.max_review_fix_attempts = 3

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (True, "**Status**: NEEDS_ATTENTION")

        mock_diff.return_value = ("diff content", False, False)
        # auto-fix (Yes), then continue (Yes)
        mock_confirm.side_effect = [True, True]
        mock_loop.return_value = ReviewFixResult(
            passed=False, exit_reason=ExitReason.EXHAUSTED, fix_attempts=3, max_attempts=3
        )

        result = run_phase_review(state, MagicMock(), "fundamental", backend=mock_backend)

        mock_loop.assert_called_once()
        assert result is True

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_no_autofix_offer_when_max_attempts_zero(self, mock_diff, mock_confirm, _step, _warn):
        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}
        state.max_review_fix_attempts = 0

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (True, "**Status**: NEEDS_ATTENTION")

        mock_diff.return_value = ("diff content", False, False)
        # Only continue prompt (no auto-fix offered)
        mock_confirm.return_value = True

        result = run_phase_review(state, MagicMock(), "fundamental", backend=mock_backend)

        assert result is True
        # Only one prompt: "Continue workflow despite review issues?"
        assert mock_confirm.call_count == 1

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review._run_review_fix_loop")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_loop_passes_returns_true(self, mock_diff, mock_confirm, mock_loop, _step, _warn):
        from ingot.workflow.review import ReviewFixResult, run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}
        state.max_review_fix_attempts = 3

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (True, "**Status**: NEEDS_ATTENTION")

        mock_diff.return_value = ("diff content", False, False)
        mock_confirm.return_value = True  # Accept auto-fix
        mock_loop.return_value = ReviewFixResult(
            passed=True, exit_reason=ExitReason.PASSED, fix_attempts=1, max_attempts=3
        )

        result = run_phase_review(state, MagicMock(), "fundamental", backend=mock_backend)

        assert result is True
        # Only auto-fix prompt, no continue prompt needed
        assert mock_confirm.call_count == 1

    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_handles_review_execution_exception(self, mock_diff, _step, _warn, _info):
        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.side_effect = Exception("Network error")

        mock_diff.return_value = ("diff content", False, False)

        result = run_phase_review(state, MagicMock(), "fundamental", backend=mock_backend)

        # Should continue workflow on review crash (advisory behavior)
        assert result is True

    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.prompt_confirm")
    @patch("ingot.workflow.review.get_smart_diff")
    def test_prompts_user_on_execution_failure(self, mock_diff, mock_confirm, _step, _warn, _info):
        from ingot.workflow.review import run_phase_review

        state = MagicMock()
        state.diff_baseline_ref = None
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (False, "Error output")

        mock_diff.return_value = ("diff content", False, False)
        mock_confirm.return_value = True

        result = run_phase_review(state, MagicMock(), "final", backend=mock_backend)

        assert result is True
        mock_confirm.assert_called_once()


class TestRunReviewFixLoop:
    @patch("ingot.workflow.review.print_success")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_passes_on_first_attempt(self, mock_autofix, mock_diff, _step, _success):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (True, "**Status**: PASS")

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is True
        assert result.fix_attempts == 1
        assert result.max_attempts == 3
        mock_autofix.assert_called_once()

    @patch("ingot.workflow.review.print_success")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_passes_on_second_attempt(self, mock_autofix, mock_diff, _step, _warn, _success):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        # First verify: NEEDS_ATTENTION, second verify: PASS
        mock_backend.run_with_callback.side_effect = [
            (True, "**Status**: NEEDS_ATTENTION\nStill has bugs"),
            (True, "**Status**: PASS"),
        ]

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is True
        assert result.fix_attempts == 2
        assert mock_autofix.call_count == 2

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_all_attempts_exhausted(self, mock_autofix, mock_diff, _step, _warn):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 2
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (
            True,
            "**Status**: NEEDS_ATTENTION\nBugs remain",
        )

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is False
        assert result.fix_attempts == 2
        assert result.max_attempts == 2
        assert mock_autofix.call_count == 2

    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_no_diff_after_fix_returns_passed(self, mock_autofix, mock_diff, _step, _info):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_autofix.return_value = True
        mock_diff.return_value = ("", False, False)  # No diff after fix

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is True
        assert result.fix_attempts == 1
        # No review call since no diff
        mock_backend.run_with_callback.assert_not_called()

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_git_error_during_verify_returns_failed(self, mock_autofix, mock_diff, _step, _warn):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_autofix.return_value = True
        mock_diff.return_value = ("", False, True)  # git_error=True

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is False
        assert result.fix_attempts == 1

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_review_exception_during_verify_returns_failed(
        self, mock_autofix, mock_diff, _step, _warn
    ):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.side_effect = Exception("Network error")

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is False
        assert result.fix_attempts == 1

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_verify_execution_failure_returns_failed(self, mock_autofix, mock_diff, _step, _warn):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.return_value = (False, "error")

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is False
        assert result.fix_attempts == 1

    @patch("ingot.workflow.review.print_info")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_autofix_failure_proceeds_to_verify(self, mock_autofix, mock_diff, _step, _warn, _info):
        """When run_auto_fix reports failure, the loop still proceeds to verify.

        Autofix fails and the reviewer still reports NEEDS_ATTENTION,
        but the key assertion is that verification was attempted at all.
        """
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        # Autofix fails; reviewer still reports issues (no partial fix helped)
        mock_autofix.return_value = False
        mock_diff.return_value = ("diff content", False, False)
        mock_backend.run_with_callback.return_value = (
            True,
            "**Status**: NEEDS_ATTENTION\nStill has issues",
        )

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        # Verify phase IS reached even when autofix fails
        mock_backend.run_with_callback.assert_called()
        assert result.fix_attempts >= 1

    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_feedback_propagation_across_attempts(self, mock_autofix, mock_diff, _step, _warn):
        """Review output from attempt N feeds into fix attempt N+1."""
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 2
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        mock_backend.run_with_callback.side_effect = [
            (True, "**Status**: NEEDS_ATTENTION\nNew issues from attempt 1"),
            (True, "**Status**: NEEDS_ATTENTION\nNew issues from attempt 2"),
        ]

        mock_autofix.return_value = True
        mock_diff.return_value = ("diff content", False, False)

        log_dir = MagicMock()
        _run_review_fix_loop(state, "initial feedback", log_dir, "final", mock_backend)

        # First call uses initial feedback, second uses output from first verify
        autofix_calls = mock_autofix.call_args_list
        assert autofix_calls[0] == call(state, "initial feedback", log_dir, mock_backend)
        assert autofix_calls[1] == call(
            state,
            "**Status**: NEEDS_ATTENTION\nNew issues from attempt 1",
            log_dir,
            mock_backend,
        )

    @patch("ingot.workflow.review.print_step")
    def test_zero_max_attempts_returns_failed_immediately(self, _step):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 0
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is False
        assert result.exit_reason == ExitReason.EXHAUSTED
        assert result.fix_attempts == 0
        # No backend calls should have been made
        mock_backend.run_with_callback.assert_not_called()

    @patch("ingot.workflow.review.print_success")
    @patch("ingot.workflow.review.print_warning")
    @patch("ingot.workflow.review.print_step")
    @patch("ingot.workflow.review.get_smart_diff")
    @patch("ingot.workflow.autofix.run_auto_fix")
    def test_partial_fix_success_when_autofix_fails_but_reviewer_passes(
        self, mock_autofix, mock_diff, _step, _warn, _success
    ):
        from ingot.workflow.review import _run_review_fix_loop

        state = MagicMock()
        state.diff_baseline_ref = None
        state.max_review_fix_attempts = 3
        state.subagent_names = {"reviewer": "ingot-reviewer"}

        mock_backend = MagicMock()
        # Autofix reports failure, but reviewer still passes
        mock_autofix.return_value = False
        mock_diff.return_value = ("diff content", False, False)
        mock_backend.run_with_callback.return_value = (True, "**Status**: PASS")

        result = _run_review_fix_loop(state, "initial feedback", MagicMock(), "final", mock_backend)

        assert result.passed is True
        assert result.exit_reason == ExitReason.PASSED
        assert result.fix_attempts == 1


class TestWorkflowStateValidation:
    def test_max_review_fix_attempts_rejects_negative(self):
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-1", title="t", description="d", platform=Platform.JIRA, url=""
        )
        with pytest.raises(ValueError, match="max_review_fix_attempts must be 0-10"):
            WorkflowState(ticket=ticket, max_review_fix_attempts=-1)

    def test_max_review_fix_attempts_rejects_over_10(self):
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-1", title="t", description="d", platform=Platform.JIRA, url=""
        )
        with pytest.raises(ValueError, match="max_review_fix_attempts must be 0-10"):
            WorkflowState(ticket=ticket, max_review_fix_attempts=11)

    def test_max_review_fix_attempts_accepts_valid_range(self):
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-1", title="t", description="d", platform=Platform.JIRA, url=""
        )
        for val in (0, 5, 10):
            state = WorkflowState(ticket=ticket, max_review_fix_attempts=val)
            assert state.max_review_fix_attempts == val

    def test_max_self_corrections_rejects_negative(self):
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-1", title="t", description="d", platform=Platform.JIRA, url=""
        )
        with pytest.raises(ValueError, match="max_self_corrections must be 0-10"):
            WorkflowState(ticket=ticket, max_self_corrections=-1)

    def test_max_self_corrections_rejects_over_10(self):
        from ingot.integrations.providers import GenericTicket, Platform
        from ingot.workflow.state import WorkflowState

        ticket = GenericTicket(
            id="TEST-1", title="t", description="d", platform=Platform.JIRA, url=""
        )
        with pytest.raises(ValueError, match="max_self_corrections must be 0-10"):
            WorkflowState(ticket=ticket, max_self_corrections=11)
