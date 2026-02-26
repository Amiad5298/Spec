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

from ingot.discovery.citation_utils import IDENTIFIER_RE, safe_resolve_path
from ingot.utils.logging import log_message

# Matches citations like: Source: `path/to/file.py:10-20`
# or Source: path/to/file.py:10-20  (with or without backticks)
_CITATION_RE = re.compile(
    r"Source:\s*`?([^`\n]+?\.\w{1,8}):(\d+)(?:-(\d+))?`?",
    re.IGNORECASE,
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
        abs_path = safe_resolve_path(self._repo_root, file_path)
        if abs_path is None:
            return CitationCheck(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                is_verified=False,
                expected_ids=frozenset(snippet_ids),
                found_ids=frozenset(),
                reason="path traversal blocked",
            )

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

            try:
                file_size = abs_path.stat().st_size
            except OSError as exc:
                return CitationCheck(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    is_verified=False,
                    expected_ids=frozenset(snippet_ids),
                    found_ids=frozenset(),
                    reason=f"cannot stat file: {exc}",
                )
            if file_size > 10 * 1024 * 1024:  # 10 MB
                return CitationCheck(
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    is_verified=False,
                    expected_ids=frozenset(snippet_ids),
                    found_ids=frozenset(),
                    reason=f"file too large ({file_size // 1024 // 1024} MB)",
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
            found_ids = set(IDENTIFIER_RE.findall(cited_text))

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

        Looks for the nearest fenced code block within 3 lines of the
        citation line (before or after). This supports both layouts:
        - Source before code block
        - Source after code block
        """
        code_blocks: list[tuple[int, int]] = []
        open_line: int | None = None
        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if open_line is None:
                    open_line = i
                else:
                    code_blocks.append((open_line, i))
                    open_line = None

        best_block: tuple[int, int] | None = None
        best_distance = float("inf")
        for block_open, block_close in code_blocks:
            if block_open <= citation_idx <= block_close:
                distance = 0
            elif citation_idx < block_open:
                distance = block_open - citation_idx
            else:
                distance = citation_idx - block_close

            if distance <= 3 and distance < best_distance:
                best_distance = distance
                best_block = (block_open, block_close)

        if best_block is None:
            return set()

        snippet_text = "\n".join(lines[best_block[0] + 1 : best_block[1]])
        return set(IDENTIFIER_RE.findall(snippet_text))


__all__ = ["CitationCheck", "CitationVerifier"]
