"""Deterministic citation verification for researcher output.

Reads ``Source: file:line-line`` citations from researcher markdown,
loads the actual file content from disk, extracts key identifiers from
the adjacent code snippet, and checks whether they appear in the cited
range. Annotates mismatches so the planner knows which patterns are
unreliable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ingot.utils.logging import log_message

# Matches citations like: Source: `path/to/file.py:10-20`
# or Source: path/to/file.py:10-20  (with or without backticks)
_CITATION_RE = re.compile(
    r"Source:\s*`?([^`\n]+?\.\w{1,8}):(\d+)(?:-(\d+))?`?",
    re.IGNORECASE,
)

# Extracts identifiers: PascalCase words, dotted method calls, import names.
# Matches: ClassName, method_name, package.method(, @Annotation
_IDENTIFIER_RE = re.compile(
    r"(?:"
    r"@[A-Z]\w+"  # Annotations: @Component, @Bean
    r"|[A-Z][a-zA-Z0-9]{2,}"  # PascalCase: Foo, Bar, URL, DistributionSummary (3+ chars)
    r"|\w+\.\w+(?=\()"  # Method calls: builder.register( — lookahead excludes '('
    r"|[a-z_]\w{2,}(?=\()"  # Function calls: register_metric(
    r")"
)

# Marker templates
_VERIFIED_MARKER = "<!-- CITATION_VERIFIED -->"
_MISMATCH_MARKER = (
    "<!-- CITATION_MISMATCH: expected [{expected}] at {file}:{lines} but found [{found}] -->"
)
_UNREADABLE_MARKER = "<!-- CITATION_UNREADABLE: {reason} -->"


@dataclass(frozen=True)
class CitationCheck:
    """Result of verifying a single citation."""

    file_path: str
    start_line: int
    end_line: int
    is_verified: bool
    expected_ids: frozenset[str]  # Identifiers from the snippet
    found_ids: frozenset[str]  # Identifiers from the actual file lines
    reason: str = ""  # Explanation if not verified


class CitationVerifier:
    """Verify researcher citations against actual file content.

    Args:
        repo_root: Absolute path to the repository root.
        overlap_threshold: Minimum fraction of snippet identifiers that
            must appear in the cited file range (default 0.5 = 50%).
    """

    def __init__(self, repo_root: Path, *, overlap_threshold: float = 0.5) -> None:
        self._repo_root = repo_root.resolve()
        self._threshold = overlap_threshold

    def verify_citations(self, researcher_output: str) -> tuple[str, list[CitationCheck]]:
        """Verify all citations in researcher output and annotate results.

        Args:
            researcher_output: Raw markdown from the researcher agent.

        Returns:
            Tuple of (annotated_output, list_of_checks).
        """
        checks: list[CitationCheck] = []
        lines = researcher_output.splitlines()
        annotated_lines = list(lines)

        # Find all citations and their associated code blocks
        i = 0
        while i < len(lines):
            line = lines[i]
            citation_match = _CITATION_RE.search(line)
            if not citation_match:
                i += 1
                continue

            file_path = citation_match.group(1).strip()
            start_line = int(citation_match.group(2))
            end_line = int(citation_match.group(3)) if citation_match.group(3) else start_line

            # Look for adjacent code block (within 3 lines after citation)
            snippet_ids = self._extract_snippet_identifiers(lines, i)

            if not snippet_ids:
                # No code block found near citation — can't verify
                i += 1
                continue

            check = self._verify_single(file_path, start_line, end_line, snippet_ids)
            checks.append(check)

            # Annotate the citation line
            if check.is_verified:
                annotated_lines[i] = f"{lines[i]} {_VERIFIED_MARKER}"
            elif check.reason:
                marker = _UNREADABLE_MARKER.format(reason=check.reason)
                annotated_lines[i] = f"{lines[i]} {marker}"
            else:
                marker = _MISMATCH_MARKER.format(
                    expected=", ".join(sorted(check.expected_ids)[:5]),
                    file=file_path,
                    lines=f"{start_line}-{end_line}" if end_line != start_line else str(start_line),
                    found=", ".join(sorted(check.found_ids)[:5]),
                )
                annotated_lines[i] = f"{lines[i]} {marker}"

            i += 1

        annotated_output = "\n".join(annotated_lines)
        verified = sum(1 for c in checks if c.is_verified)
        total = len(checks)
        if total > 0:
            log_message(f"CitationVerifier: {verified}/{total} citations verified")

        return annotated_output, checks

    def _verify_single(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        snippet_ids: set[str],
    ) -> CitationCheck:
        """Verify a single citation against disk."""
        abs_path = self._repo_root / file_path

        try:
            if not abs_path.is_file():
                return CitationCheck(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    is_verified=False,
                    expected_ids=frozenset(snippet_ids),
                    found_ids=frozenset(),
                    reason=f"file not found: {file_path}",
                )

            all_lines = abs_path.read_text(errors="replace").splitlines()

            # Extract cited range (1-based → 0-based)
            range_start = max(0, start_line - 1)
            range_end = min(len(all_lines), end_line)
            if range_start >= len(all_lines):
                return CitationCheck(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    is_verified=False,
                    expected_ids=frozenset(snippet_ids),
                    found_ids=frozenset(),
                    reason=f"line range {start_line}-{end_line} out of bounds (file has {len(all_lines)} lines)",
                )

            cited_text = "\n".join(all_lines[range_start:range_end])
            found_ids = set(_IDENTIFIER_RE.findall(cited_text))

        except OSError as exc:
            return CitationCheck(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                is_verified=False,
                expected_ids=frozenset(snippet_ids),
                found_ids=frozenset(),
                reason=str(exc),
            )

        # Calculate overlap
        if not snippet_ids:
            # No identifiers to check — treat as verified
            return CitationCheck(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                is_verified=True,
                expected_ids=frozenset(snippet_ids),
                found_ids=frozenset(found_ids),
            )

        overlap = snippet_ids & found_ids
        ratio = len(overlap) / len(snippet_ids)

        return CitationCheck(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            is_verified=ratio >= self._threshold,
            expected_ids=frozenset(snippet_ids),
            found_ids=frozenset(found_ids),
        )

    def _extract_snippet_identifiers(self, lines: list[str], citation_idx: int) -> set[str]:
        """Extract identifiers from the code block near a citation.

        Looks for a fenced code block within 3 lines after the citation.
        """
        search_range = min(len(lines), citation_idx + 4)
        block_start = None
        block_end = None

        for j in range(citation_idx + 1, search_range):
            if lines[j].strip().startswith("```"):
                block_start = j + 1
                break

        if block_start is None:
            return set()

        for j in range(block_start, len(lines)):
            if lines[j].strip().startswith("```"):
                block_end = j
                break

        if block_end is None:
            return set()

        snippet_text = "\n".join(lines[block_start:block_end])
        return set(_IDENTIFIER_RE.findall(snippet_text))


__all__ = ["CitationCheck", "CitationVerifier"]
