"""Concrete plan validators for the INGOT workflow.

Each validator is a small, focused class that checks one aspect of
a generated plan. The factory function at the bottom creates the
default registry with all standard validators.
"""

import re

from ingot.validation.base import (
    ValidationContext,
    ValidationFinding,
    ValidationSeverity,
    Validator,
    ValidatorRegistry,
)


class RequiredSectionsValidator(Validator):
    """Check that all required plan sections are present."""

    REQUIRED = [
        "Summary",
        "Technical Approach",
        "Implementation Steps",
        "Testing Strategy",
        "Potential Risks",
        "Out of Scope",
    ]

    @property
    def name(self) -> str:
        return "Required Sections"

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        for section in self.REQUIRED:
            # Case-insensitive, allows partial match
            # e.g. "Potential Risks or Considerations" matches "Potential Risks"
            pattern = re.compile(
                r"^#{1,3}\s+.*" + re.escape(section),
                re.IGNORECASE | re.MULTILINE,
            )
            if not pattern.search(content):
                findings.append(
                    ValidationFinding(
                        validator_name=self.name,
                        severity=ValidationSeverity.ERROR,
                        message=f"Missing required section: '{section}'",
                        suggestion=f"Add a '## {section}' section to the plan.",
                    )
                )
        return findings


class FileExistsValidator(Validator):
    """Check that file paths referenced in the plan exist on the filesystem."""

    # Match backtick-quoted strings containing at least one / and a file extension
    _PATH_RE = re.compile(r"`([^`]*?(?:/[^`]*?\.\w{1,8})[^`]*?)`")

    # Characters to strip from extracted paths
    _STRIP_CHARS = ".,;:()\"' "

    # Paths to skip (not real file references)
    _SKIP_PATTERNS = [
        re.compile(r"[{}<>*]"),  # Templated or glob
        re.compile(r"^path/to/"),  # Placeholder
    ]

    # Detect UNVERIFIED markers
    _UNVERIFIED_RE = re.compile(r"<!--\s*UNVERIFIED:.*?-->", re.DOTALL)

    @property
    def name(self) -> str:
        return "File Exists"

    def _extract_paths(self, content: str) -> list[tuple[str, int]]:
        """Extract (normalized_path, line_number) pairs from plan content."""
        # Find line numbers that contain UNVERIFIED markers
        unverified_lines: set[int] = set()
        for m in self._UNVERIFIED_RE.finditer(content):
            line_num = content[: m.start()].count("\n")
            unverified_lines.add(line_num)

        results: list[tuple[str, int]] = []
        for match in self._PATH_RE.finditer(content):
            # Skip paths on lines with UNVERIFIED markers
            line_num = content[: match.start()].count("\n")
            if line_num in unverified_lines:
                continue

            raw_path = match.group(1).strip(self._STRIP_CHARS)

            # Split off :line_number suffix
            if ":" in raw_path:
                parts = raw_path.rsplit(":", 1)
                # Only split if the part after : looks like a line number
                if parts[1].replace("-", "").isdigit():
                    raw_path = parts[0]

            # Skip templated/glob/placeholder paths
            skip = False
            for skip_pattern in self._SKIP_PATTERNS:
                if skip_pattern.search(raw_path):
                    skip = True
                    break
            if skip:
                continue

            results.append((raw_path, line_num + 1))

        return results

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        if context.repo_root is None:
            return []

        findings: list[ValidationFinding] = []
        paths = self._extract_paths(content)
        seen: set[str] = set()

        for path_str, line_number in paths:
            if path_str in seen:
                continue
            seen.add(path_str)

            full_path = context.repo_root / path_str
            try:
                resolved = full_path.resolve()
                if not resolved.is_relative_to(context.repo_root.resolve()):
                    continue
            except (ValueError, OSError):
                continue
            if not resolved.exists():
                findings.append(
                    ValidationFinding(
                        validator_name=self.name,
                        severity=ValidationSeverity.ERROR,
                        message=f"File not found: `{path_str}`",
                        line_number=line_number,
                        suggestion=(
                            "Verify the file path exists in the repository, "
                            "or flag it with <!-- UNVERIFIED: reason -->."
                        ),
                    )
                )

        return findings


class PatternSourceValidator(Validator):
    """Check that code snippets cite a Pattern source reference."""

    _PATTERN_SOURCE_RE = re.compile(
        r"Pattern\s+source:\s*`?([^`\n]+\.\w{1,8}:\d+(?:-\d+)?)`?",
        re.IGNORECASE,
    )
    _NO_PATTERN_MARKER_RE = re.compile(r"<!--\s*NO_EXISTING_PATTERN:", re.IGNORECASE)

    _WINDOW_LINES = 5  # Lines before/after code block to search for citation

    @property
    def name(self) -> str:
        return "Pattern Source"

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        lines = content.splitlines()

        # Find all fenced code block pairs
        fence_positions: list[int] = []
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                fence_positions.append(i)

        # Process pairs (opening, closing)
        for idx in range(0, len(fence_positions) - 1, 2):
            open_line = fence_positions[idx]
            close_line = fence_positions[idx + 1]

            # Skip trivially short blocks (< 3 lines of content)
            content_lines = close_line - open_line - 1
            if content_lines < 3:
                continue

            # Extract window before and after the opening fence
            window_start = max(0, open_line - self._WINDOW_LINES)
            window_end = min(len(lines), close_line + self._WINDOW_LINES + 1)
            window_text = "\n".join(lines[window_start:window_end])

            has_source = self._PATTERN_SOURCE_RE.search(window_text)
            has_no_pattern = self._NO_PATTERN_MARKER_RE.search(window_text)

            if not has_source and not has_no_pattern:
                findings.append(
                    ValidationFinding(
                        validator_name=self.name,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Code block at line {open_line + 1} has no "
                            f"'Pattern source:' citation or NO_EXISTING_PATTERN marker."
                        ),
                        line_number=open_line + 1,
                        suggestion=(
                            "Add 'Pattern source: path/to/file:line-line' before the "
                            "code block, or '<!-- NO_EXISTING_PATTERN: description -->'."
                        ),
                    )
                )

        return findings


class UnresolvedMarkersValidator(Validator):
    """Detect and report UNVERIFIED or NO_EXISTING_PATTERN markers."""

    _UNVERIFIED_RE = re.compile(
        r"<!--\s*UNVERIFIED:\s*(.*?)\s*-->",
        re.IGNORECASE,
    )
    _NO_PATTERN_RE = re.compile(
        r"<!--\s*NO_EXISTING_PATTERN:\s*(.*?)\s*-->",
        re.IGNORECASE,
    )

    @property
    def name(self) -> str:
        return "Unresolved Markers"

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []

        for match in self._UNVERIFIED_RE.finditer(content):
            line_number = content[: match.start()].count("\n") + 1
            reason = match.group(1).strip()
            findings.append(
                ValidationFinding(
                    validator_name=self.name,
                    severity=ValidationSeverity.INFO,
                    message=f"UNVERIFIED marker: {reason}",
                    line_number=line_number,
                )
            )

        for match in self._NO_PATTERN_RE.finditer(content):
            line_number = content[: match.start()].count("\n") + 1
            desc = match.group(1).strip()
            findings.append(
                ValidationFinding(
                    validator_name=self.name,
                    severity=ValidationSeverity.INFO,
                    message=f"NO_EXISTING_PATTERN marker: {desc}",
                    line_number=line_number,
                )
            )

        return findings


class DiscoveryCoverageValidator(Validator):
    """Check that items from researcher discovery are referenced in the plan.

    Ensures entries from Interface & Class Hierarchy and Call Sites sections
    of the researcher output are either mentioned in Implementation Steps
    or explicitly listed in Out of Scope.

    Lightweight: uses string/path matching (not semantic analysis).
    """

    def __init__(self, researcher_output: str = "") -> None:
        self._researcher_output = researcher_output

    @property
    def name(self) -> str:
        return "Discovery Coverage"

    def _extract_names_from_section(self, section_header: str) -> list[str]:
        """Extract interface/class/method names from a researcher output section."""
        if not self._researcher_output:
            return []

        names: list[str] = []
        lines = self._researcher_output.splitlines()
        in_section = False

        for line in lines:
            stripped = line.strip()

            # Match section-level headings: exactly "### " (not "#### ")
            is_section_heading = stripped.startswith("### ") and not stripped.startswith("#### ")

            # Check if we're entering the target section
            if is_section_heading and section_header.lower() in stripped.lower():
                in_section = True
                continue

            # Check if we've left the section (hit next ### section)
            if in_section and is_section_heading:
                break

            if not in_section:
                continue

            # Extract names from #### headers (e.g., "#### `InterfaceName`")
            if stripped.startswith("#### "):
                # Extract name from backticks or plain text after ####
                name_match = re.search(r"`([^`]+)`", stripped)
                if name_match:
                    name = name_match.group(1)
                    # Strip parentheses for method names
                    name = name.removesuffix("()")
                    names.append(name)
                else:
                    # Plain text name
                    name = stripped.lstrip("#").strip()
                    if name:
                        names.append(name)

        return names

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        if not self._researcher_output:
            return []

        findings: list[ValidationFinding] = []

        # Extract names from Interface & Class Hierarchy
        interface_names = self._extract_names_from_section("Interface & Class Hierarchy")
        # Extract names from Call Sites
        method_names = self._extract_names_from_section("Call Sites")

        all_names = interface_names + method_names

        for name in all_names:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            if not pattern.search(content):
                findings.append(
                    ValidationFinding(
                        validator_name=self.name,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Researcher discovered '{name}' but it is not referenced "
                            f"in the plan (Implementation Steps, Testing Strategy, or Out of Scope)."
                        ),
                        suggestion=(
                            f"Ensure '{name}' is addressed in the plan or "
                            f"explicitly listed in Out of Scope."
                        ),
                    )
                )

        return findings


def create_plan_validator_registry(
    researcher_output: str = "",
) -> ValidatorRegistry:
    """Create the default plan validator registry with all standard gates.

    Args:
        researcher_output: Raw researcher output, passed to DiscoveryCoverageValidator.
    """
    registry = ValidatorRegistry()
    registry.register(RequiredSectionsValidator())
    registry.register(FileExistsValidator())
    registry.register(PatternSourceValidator())
    registry.register(UnresolvedMarkersValidator())
    registry.register(DiscoveryCoverageValidator(researcher_output))
    return registry


__all__ = [
    "RequiredSectionsValidator",
    "FileExistsValidator",
    "PatternSourceValidator",
    "UnresolvedMarkersValidator",
    "DiscoveryCoverageValidator",
    "create_plan_validator_registry",
]
