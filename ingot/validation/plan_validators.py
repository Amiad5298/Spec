"""Concrete plan validators for the INGOT workflow.

Each validator is a small, focused class that checks one aspect of
a generated plan. The factory function at the bottom creates the
default registry with all standard validators.
"""

import bisect
import re

from ingot.validation.base import (
    ValidationContext,
    ValidationFinding,
    ValidationSeverity,
    Validator,
    ValidatorRegistry,
)

# =============================================================================
# Shared Utility Functions
# =============================================================================

_FENCED_CODE_BLOCK_RE = re.compile(
    r"^```[^\n]*\n.*?^```\s*$",
    re.MULTILINE | re.DOTALL,
)

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _strip_fenced_code_blocks(content: str) -> str:
    """Remove fenced code blocks from content.

    Used to prevent headings or names inside ``` blocks from matching
    as real sections or coverage references.
    """
    return _FENCED_CODE_BLOCK_RE.sub("", content)


def _build_line_index(content: str) -> list[int]:
    """Build a sorted list of newline character offsets for O(log N) lookups.

    Returns a list of positions where '\\n' occurs in *content*.
    """
    return [i for i, ch in enumerate(content) if ch == "\n"]


def _line_number_at(line_index: list[int], offset: int) -> int:
    """Return the 1-based line number for a character *offset*.

    Uses ``bisect.bisect_right`` for O(log N) lookup against the
    pre-built *line_index*.
    """
    return bisect.bisect_right(line_index, offset) + 1


def _extract_plan_sections(content: str, section_names: list[str]) -> str:
    """Extract text from specific plan sections.

    Scans for ``#{1,3}`` headings (not ``####``+) and checks whether the
    heading text matches any target *section_names* (case-insensitive
    partial match).  Returns the concatenated text from matched sections.
    """
    matches = list(_HEADING_RE.finditer(content))

    if not matches:
        return ""

    parts: list[str] = []
    for idx, m in enumerate(matches):
        heading_text = m.group(2).strip()
        # Check case-insensitive partial match against any target section
        if not any(name.lower() in heading_text.lower() for name in section_names):
            continue
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        parts.append(content[start:end])

    return "\n".join(parts)


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
        # Strip fenced code blocks so headings inside ``` don't count
        stripped = _strip_fenced_code_blocks(content)
        for section in self.REQUIRED:
            # Case-insensitive, allows partial match
            # e.g. "Potential Risks or Considerations" matches "Potential Risks"
            pattern = re.compile(
                r"^#{1,3}\s+.*" + re.escape(section),
                re.IGNORECASE | re.MULTILINE,
            )
            if not pattern.search(stripped):
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

    # Match backtick-quoted root files (no slash) with common extensions
    _ROOT_FILE_RE = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_.-]*\.\w{1,8})`")

    # Common file extensions to filter root-file matches (avoid false positives)
    _COMMON_FILE_EXTENSIONS: frozenset[str] = frozenset(
        {
            "py",
            "js",
            "ts",
            "tsx",
            "jsx",
            "md",
            "json",
            "toml",
            "yaml",
            "yml",
            "cfg",
            "ini",
            "txt",
            "rst",
            "html",
            "css",
            "scss",
            "less",
            "xml",
            "sh",
            "bash",
            "zsh",
            "fish",
            "bat",
            "ps1",
            "rb",
            "go",
            "rs",
            "java",
            "kt",
            "c",
            "cpp",
            "h",
            "hpp",
            "cs",
            "swift",
            "m",
            "lock",
            "sql",
            "graphql",
            "proto",
            "tf",
            "hcl",
        }
    )

    # Known extensionless filenames that should be treated as files
    # Sorted tuple for deterministic regex construction.
    _KNOWN_EXTENSIONLESS: tuple[str, ...] = (
        "Brewfile",
        "Containerfile",
        "Dockerfile",
        "Gemfile",
        "Justfile",
        "Makefile",
        "Procfile",
        "Rakefile",
        "Taskfile",
        "Vagrantfile",
    )
    _EXTENSIONLESS_RE = re.compile(
        r"`(" + "|".join(re.escape(f) for f in _KNOWN_EXTENSIONLESS) + r")`"
    )

    # Characters to strip from extracted paths
    _STRIP_CHARS = ".,;:()\"' "

    # Paths to skip (not real file references)
    _SKIP_PATTERNS = [
        re.compile(r"[{}<>*]"),  # Templated or glob
        re.compile(r"^path/to/"),  # Placeholder
        re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://"),  # URLs (http, s3, ssh, file, git, gs, etc.)
        re.compile(r"^(?:data|mailto):"),  # Schemes without //
    ]

    # Detect UNVERIFIED markers
    _UNVERIFIED_RE = re.compile(r"<!--\s*UNVERIFIED:.*?-->", re.DOTALL)

    @property
    def name(self) -> str:
        return "File Exists"

    def _extract_paths(self, content: str) -> list[tuple[str, int]]:
        """Extract (normalized_path, line_number) pairs from plan content."""
        line_index = _build_line_index(content)

        # Find line numbers that contain UNVERIFIED markers
        unverified_lines: set[int] = set()
        for m in self._UNVERIFIED_RE.finditer(content):
            unverified_lines.add(_line_number_at(line_index, m.start()))

        # Collect all matches from all regexes, deduplicating by offset
        seen_offsets: set[int] = set()
        raw_matches: list[tuple[str, int, int]] = []  # (raw_text, offset, line_num)

        for match in self._PATH_RE.finditer(content):
            if match.start() not in seen_offsets:
                seen_offsets.add(match.start())
                line_num = _line_number_at(line_index, match.start())
                raw_matches.append((match.group(1), match.start(), line_num))

        for match in self._ROOT_FILE_RE.finditer(content):
            if match.start() not in seen_offsets:
                raw = match.group(1)
                # Only accept if extension is common
                ext = raw.rsplit(".", 1)[-1].lower() if "." in raw else ""
                if ext in self._COMMON_FILE_EXTENSIONS:
                    seen_offsets.add(match.start())
                    line_num = _line_number_at(line_index, match.start())
                    raw_matches.append((raw, match.start(), line_num))

        for match in self._EXTENSIONLESS_RE.finditer(content):
            if match.start() not in seen_offsets:
                seen_offsets.add(match.start())
                line_num = _line_number_at(line_index, match.start())
                raw_matches.append((match.group(1), match.start(), line_num))

        results: list[tuple[str, int]] = []
        for raw_text, _offset, line_num in raw_matches:
            if line_num in unverified_lines:
                continue

            raw_path = raw_text.strip(self._STRIP_CHARS)

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

            results.append((raw_path, line_num))

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

        # Stateful fence parsing: track open/close pairs via state machine
        code_blocks: list[tuple[int, int]] = []  # (open_line, close_line)
        in_code_block = False
        open_line = 0

        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if not in_code_block:
                    in_code_block = True
                    open_line = i
                else:
                    in_code_block = False
                    code_blocks.append((open_line, i))

        # Warn about unbalanced fence
        if in_code_block:
            findings.append(
                ValidationFinding(
                    validator_name=self.name,
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"Unbalanced code fence at line {open_line + 1}: "
                        f"opening ``` without matching close."
                    ),
                    line_number=open_line + 1,
                    suggestion="Add a closing ``` to balance the code block.",
                )
            )

        # Check each code block for pattern source citation
        for block_open, block_close in code_blocks:
            # Skip trivially short blocks (< 3 lines of content)
            content_lines = block_close - block_open - 1
            if content_lines < 3:
                continue

            # Extract window before and after the code block
            window_start = max(0, block_open - self._WINDOW_LINES)
            window_end = min(len(lines), block_close + self._WINDOW_LINES + 1)
            window_text = "\n".join(lines[window_start:window_end])

            has_source = self._PATTERN_SOURCE_RE.search(window_text)
            has_no_pattern = self._NO_PATTERN_MARKER_RE.search(window_text)

            if not has_source and not has_no_pattern:
                findings.append(
                    ValidationFinding(
                        validator_name=self.name,
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"Code block at line {block_open + 1} has no "
                            f"'Pattern source:' citation or NO_EXISTING_PATTERN marker."
                        ),
                        line_number=block_open + 1,
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
        line_index = _build_line_index(content)

        for match in self._UNVERIFIED_RE.finditer(content):
            line_number = _line_number_at(line_index, match.start())
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
            line_number = _line_number_at(line_index, match.start())
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

    # Target sections for coverage checking
    _TARGET_SECTIONS = ["Implementation Steps", "Testing Strategy", "Out of Scope"]

    def validate(self, content: str, context: ValidationContext) -> list[ValidationFinding]:
        if not self._researcher_output:
            return []

        findings: list[ValidationFinding] = []

        # Extract text from target sections only
        restricted_text = _extract_plan_sections(content, self._TARGET_SECTIONS)
        if restricted_text:
            # Strip code blocks from restricted text
            search_text = _strip_fenced_code_blocks(restricted_text)
        else:
            # Fallback: if no target sections found (malformed plan), search full content
            search_text = _strip_fenced_code_blocks(content)

        # Extract names from Interface & Class Hierarchy
        interface_names = self._extract_names_from_section("Interface & Class Hierarchy")
        # Extract names from Call Sites
        method_names = self._extract_names_from_section("Call Sites")

        all_names = interface_names + method_names

        for name in all_names:
            pattern = re.compile(r"\b" + re.escape(name) + r"\b")
            if not pattern.search(search_text):
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
