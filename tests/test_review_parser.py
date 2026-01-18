"""Tests for review status parser in step3_execute module."""

import pytest

from spec.workflow.step3_execute import _parse_review_status


class TestParseReviewStatus:
    """Tests for _parse_review_status function."""

    def test_parse_pass_with_bold_markers(self):
        """Parses PASS with bold markers."""
        output = """## Task Review: Example Task

**Status**: PASS

**Summary**: Everything looks good!
"""
        assert _parse_review_status(output) == "PASS"

    def test_parse_pass_without_bold_markers(self):
        """Parses PASS without bold markers."""
        output = """## Task Review: Example Task

Status: PASS

Summary: Everything looks good!
"""
        assert _parse_review_status(output) == "PASS"

    def test_parse_needs_attention_with_bold_markers(self):
        """Parses NEEDS_ATTENTION with bold markers."""
        output = """## Task Review: Example Task

**Status**: NEEDS_ATTENTION

**Issues**:
- Missing error handling
- Incomplete tests
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_parse_needs_attention_without_bold_markers(self):
        """Parses NEEDS_ATTENTION without bold markers."""
        output = """## Task Review: Example Task

Status: NEEDS_ATTENTION

Issues:
- Missing error handling
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_ignores_pass_in_normal_text(self):
        """Ignores PASS appearing in normal text."""
        output = """## Task Review: Example Task

The implementation will PASS all tests once complete.

**Status**: NEEDS_ATTENTION

**Issues**:
- Tests not yet written
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_uses_last_status_marker(self):
        """Uses the last status marker as final verdict."""
        output = """## Initial Review

**Status**: NEEDS_ATTENTION

Issues found.

## After Fix

**Status**: PASS

All issues resolved!
"""
        assert _parse_review_status(output) == "PASS"

    def test_case_insensitive_matching(self):
        """Handles case variations."""
        output = "**Status**: pass\n\nLooks good!"
        assert _parse_review_status(output) == "PASS"

    def test_whitespace_variations(self):
        """Handles whitespace variations."""
        output = "**Status**:    PASS   \n\nLooks good!"
        assert _parse_review_status(output) == "PASS"

    def test_empty_output_returns_needs_attention(self):
        """Empty output returns NEEDS_ATTENTION (fail-safe)."""
        assert _parse_review_status("") == "NEEDS_ATTENTION"
        assert _parse_review_status("   ") == "NEEDS_ATTENTION"

    def test_no_status_marker_returns_needs_attention(self):
        """No status marker returns NEEDS_ATTENTION (fail-safe)."""
        output = """## Task Review

Some review text without a clear status marker.
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_standalone_pass_at_end(self):
        """Detects standalone PASS marker at end."""
        output = """## Task Review

Everything looks good.

**PASS**
"""
        assert _parse_review_status(output) == "PASS"

    def test_standalone_needs_attention_at_end(self):
        """Detects standalone NEEDS_ATTENTION marker at end."""
        output = """## Task Review

Found some issues.

NEEDS_ATTENTION
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_both_markers_present_uses_last(self):
        """When both markers present, uses the last one."""
        output = """**Status**: PASS

Wait, actually found an issue.

**Status**: NEEDS_ATTENTION
"""
        assert _parse_review_status(output) == "NEEDS_ATTENTION"

    def test_mixed_bold_and_plain_markers(self):
        """Handles mixed bold and plain markers."""
        output = """Status: NEEDS_ATTENTION

After review:

**Status**: PASS
"""
        assert _parse_review_status(output) == "PASS"

