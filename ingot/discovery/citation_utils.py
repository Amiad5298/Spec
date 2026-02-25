"""Shared utilities for citation verification across discovery and validation.

Provides path-safety checks and a canonical identifier regex used by
both :class:`CitationVerifier` and :class:`CitationContentValidator`.
"""

from __future__ import annotations

import re
from pathlib import Path

# Canonical identifier regex shared between CitationVerifier and
# CitationContentValidator.  Uses lookahead for method calls so the
# extracted text does NOT include the trailing '('.
IDENTIFIER_RE = re.compile(
    r"(?:"
    r"@[A-Z]\w+"  # Annotations: @Component, @Bean
    r"|[A-Z][a-zA-Z0-9]{2,}"  # PascalCase: Foo, DistributionSummary (3+ chars)
    r"|\w+\.\w+(?=\()"  # Method calls: builder.register( — lookahead excludes '('
    r"|[a-z_]\w{2,}(?=\()"  # Function calls: register_metric(
    r")"
)


def extract_identifiers(text: str) -> set[str]:
    """Extract code identifiers from *text* using :data:`IDENTIFIER_RE`."""
    return set(IDENTIFIER_RE.findall(text))


def safe_resolve_path(repo_root: Path, file_path: str) -> Path | None:
    """Safely resolve *file_path* relative to *repo_root*.

    Returns ``None`` (and therefore blocks the read) when:
    - *file_path* is absolute,
    - the resolved result escapes *repo_root* (e.g. ``../../etc/passwd``),
    - the path contains a null byte.

    Symlinks are resolved before the containment check.

    Note: there is an inherent TOCTOU race between ``resolve()`` and the
    caller's subsequent read — a symlink target could change in between.
    This is acceptable for plan-validation purposes.
    """
    if not file_path or "\x00" in file_path:
        return None

    # Reject absolute paths outright
    if file_path.startswith("/") or file_path.startswith("\\"):
        return None

    try:
        resolved_root = repo_root.resolve()
        candidate = (resolved_root / file_path).resolve()
        if not candidate.is_relative_to(resolved_root):
            return None
        return candidate
    except (OSError, ValueError):
        return None


__all__ = ["IDENTIFIER_RE", "extract_identifiers", "safe_resolve_path"]
