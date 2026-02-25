"""Python-native regex search across indexed repository files.

Provides deterministic, local grep capabilities without external
dependencies (no ripgrep/grep subprocess). Uses the :class:`FileIndex`
as its file list source.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ingot.utils.logging import log_message


@dataclass(frozen=True)
class GrepMatch:
    """A single search match result."""

    file: PurePosixPath
    line_num: int
    line_content: str
    context_before: tuple[str, ...] = ()
    context_after: tuple[str, ...] = ()


# Default limits
_DEFAULT_MAX_MATCHES_PER_FILE = 50
_DEFAULT_MAX_MATCHES_TOTAL = 500
_DEFAULT_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
_DEFAULT_SEARCH_TIMEOUT = 30.0  # seconds


class GrepEngine:
    """Python-native regex search across a set of repository files.

    Args:
        repo_root: Absolute path to the repository root.
        file_paths: List of relative paths to search (typically from FileIndex).
        context_lines: Number of context lines before/after each match.
        max_matches_per_file: Stop searching a file after this many matches.
        max_matches_total: Stop searching entirely after this many matches.
        max_file_size: Skip files larger than this (bytes).
    """

    def __init__(
        self,
        repo_root: Path,
        file_paths: list[PurePosixPath],
        *,
        context_lines: int = 0,
        max_matches_per_file: int = _DEFAULT_MAX_MATCHES_PER_FILE,
        max_matches_total: int = _DEFAULT_MAX_MATCHES_TOTAL,
        max_file_size: int = _DEFAULT_MAX_FILE_SIZE,
        search_timeout: float = _DEFAULT_SEARCH_TIMEOUT,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._file_paths = file_paths
        self._context_lines = context_lines
        self._max_per_file = max_matches_per_file
        self._max_total = max_matches_total
        self._max_file_size = max_file_size
        self._search_timeout = search_timeout
        # Pattern-keyed result cache (session-scoped)
        self._cache: dict[str, list[GrepMatch]] = {}

    def search(self, pattern: str, *, ignore_case: bool = False) -> list[GrepMatch]:
        """Search all indexed files for a single regex pattern.

        Results are cached by ``(pattern, ignore_case)`` key for the
        lifetime of this engine instance.

        Args:
            pattern: Regular expression to search for.
            ignore_case: If True, perform case-insensitive matching.

        Returns:
            List of :class:`GrepMatch` results.
        """
        cache_key = f"{pattern}::{ignore_case}"
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            log_message(f"GrepEngine: invalid regex {pattern!r}: {exc}")
            return []

        results = self._search_files([compiled])
        self._cache[cache_key] = results
        return results

    def search_batch(
        self,
        patterns: list[str],
        *,
        ignore_case: bool = False,
    ) -> dict[str, list[GrepMatch]]:
        """Search all indexed files for multiple patterns in one pass.

        Each file is read once and all patterns are tested against each line.

        Args:
            patterns: List of regex patterns.
            ignore_case: If True, perform case-insensitive matching.

        Returns:
            Dict mapping each pattern string to its list of matches.
        """
        flags = re.IGNORECASE if ignore_case else 0
        compiled: list[re.Pattern[str]] = []
        for p in patterns:
            try:
                compiled.append(re.compile(p, flags))
            except re.error as exc:
                log_message(f"GrepEngine: skipping invalid regex {p!r}: {exc}")
                compiled.append(re.compile(r"(?!x)x"))  # Never-matching placeholder

        # Initialize result dict
        results: dict[str, list[GrepMatch]] = {p: [] for p in patterns}
        total_count = 0
        deadline = time.monotonic() + self._search_timeout

        for rel_path in self._file_paths:
            if total_count >= self._max_total:
                break
            if time.monotonic() > deadline:
                log_message(
                    f"GrepEngine: batch search timeout ({self._search_timeout}s) reached "
                    f"after {total_count} matches"
                )
                break

            abs_path = self._repo_root / str(rel_path)
            lines = self._read_file_lines(abs_path)
            if lines is None:
                continue

            file_counts: dict[int, int] = {}  # pattern_index -> count

            for line_idx, line in enumerate(lines):
                if total_count >= self._max_total:
                    break

                for pat_idx, regex in enumerate(compiled):
                    if file_counts.get(pat_idx, 0) >= self._max_per_file:
                        continue
                    if regex.search(line):
                        match = GrepMatch(
                            file=rel_path,
                            line_num=line_idx + 1,
                            line_content=line,
                            context_before=self._get_context(lines, line_idx, before=True),
                            context_after=self._get_context(lines, line_idx, before=False),
                        )
                        results[patterns[pat_idx]].append(match)
                        file_counts[pat_idx] = file_counts.get(pat_idx, 0) + 1
                        total_count += 1

        # Populate per-pattern cache so subsequent single-pattern searches hit cache
        for pat in patterns:
            cache_key = f"{pat}::{ignore_case}"
            if cache_key not in self._cache:
                self._cache[cache_key] = results[pat]

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _search_files(self, compiled_patterns: list[re.Pattern[str]]) -> list[GrepMatch]:
        """Search files for compiled patterns."""
        matches: list[GrepMatch] = []
        deadline = time.monotonic() + self._search_timeout

        for rel_path in self._file_paths:
            if len(matches) >= self._max_total:
                break
            if time.monotonic() > deadline:
                log_message(
                    f"GrepEngine: search timeout ({self._search_timeout}s) reached "
                    f"after {len(matches)} matches"
                )
                break

            abs_path = self._repo_root / str(rel_path)
            lines = self._read_file_lines(abs_path)
            if lines is None:
                continue

            file_match_count = 0
            for line_idx, line in enumerate(lines):
                if file_match_count >= self._max_per_file:
                    break
                if len(matches) >= self._max_total:
                    break

                for regex in compiled_patterns:
                    if regex.search(line):
                        match = GrepMatch(
                            file=rel_path,
                            line_num=line_idx + 1,
                            line_content=line,
                            context_before=self._get_context(lines, line_idx, before=True),
                            context_after=self._get_context(lines, line_idx, before=False),
                        )
                        matches.append(match)
                        file_match_count += 1
                        break  # One match per line per search call

        return matches

    def _read_file_lines(self, abs_path: Path) -> list[str] | None:
        """Read a file into lines, or return None if unreadable/binary/too large."""
        try:
            # Check file size via stat() BEFORE reading to avoid loading
            # multi-GB files into memory just to reject them.
            if abs_path.stat().st_size > self._max_file_size:
                return None
            raw = abs_path.read_bytes()
            if b"\x00" in raw[:8192]:
                return None
            return raw.decode("utf-8", errors="replace").splitlines()
        except OSError:
            return None

    def _get_context(self, lines: list[str], line_idx: int, *, before: bool) -> tuple[str, ...]:
        """Extract context lines before or after a match."""
        if self._context_lines <= 0:
            return ()
        if before:
            start = max(0, line_idx - self._context_lines)
            return tuple(lines[start:line_idx])
        else:
            end = min(len(lines), line_idx + 1 + self._context_lines)
            return tuple(lines[line_idx + 1 : end])


__all__ = ["GrepEngine", "GrepMatch"]
