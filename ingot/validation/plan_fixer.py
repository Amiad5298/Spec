"""Deterministic post-processor that auto-corrects plan validation errors.

PlanFixer resolves FileExistsValidator errors by injecting the correct
markers (<!-- UNVERIFIED -->) into the plan text, eliminating false-positive
errors that would otherwise trigger retries or user prompts.
"""

import re

from ingot.validation.base import ValidationReport, ValidationSeverity

# Match the error message format from FileExistsValidator
_FILE_NOT_FOUND_RE = re.compile(r"^File not found: `(.+)`$")


class PlanFixer:
    """Deterministic post-processor that auto-corrects plan validation errors.

    Only fixes ``FileExistsValidator`` errors — these are the common
    false positives when the AI planner omits ``<!-- NEW_FILE -->`` or
    ``<!-- UNVERIFIED -->`` markers. Other validators (e.g.
    ``RequiredSectionsValidator``) produce real issues that require AI retry.
    """

    def fix(self, content: str, report: ValidationReport) -> tuple[str, list[str]]:
        """Apply deterministic fixes to plan content.

        Args:
            content: Raw plan text.
            report: Validation report with findings to fix.

        Returns:
            Tuple of (fixed_content, list_of_fix_descriptions).
            If no fixes are applied, ``content`` is returned unchanged.
        """
        lines = content.split("\n")
        fixes: list[str] = []

        for finding in report.findings:
            if finding.severity != ValidationSeverity.ERROR:
                continue
            if finding.validator_name != "File Exists":
                continue
            if finding.line_number is None:
                continue

            path_match = _FILE_NOT_FOUND_RE.match(finding.message)
            if not path_match:
                continue

            idx = finding.line_number - 1  # 0-based
            if idx < 0 or idx >= len(lines):
                continue

            line = lines[idx]

            # Idempotent: skip if already marked
            if "<!-- UNVERIFIED" in line or "<!-- NEW_FILE" in line:
                continue

            # Inject UNVERIFIED marker at end of line
            lines[idx] = f"{line} <!-- UNVERIFIED: auto-flagged, file not in repo -->"
            fixes.append(
                f"Marked `{path_match.group(1)}` as UNVERIFIED (line {finding.line_number})"
            )

        if not fixes:
            return content, fixes
        return "\n".join(lines), fixes


__all__ = ["PlanFixer"]
