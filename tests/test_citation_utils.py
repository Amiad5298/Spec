"""Tests for ingot.discovery.citation_utils module."""

from ingot.discovery.citation_utils import (
    extract_identifiers,
    safe_resolve_path,
)

# ------------------------------------------------------------------
# safe_resolve_path
# ------------------------------------------------------------------


class TestSafeResolvePath:
    """Tests for safe_resolve_path."""

    def test_normal_path_resolves(self, tmp_path):
        """A valid relative path inside the repo resolves correctly."""
        (tmp_path / "src").mkdir()
        target = tmp_path / "src" / "Foo.java"
        target.write_text("class Foo {}")

        result = safe_resolve_path(tmp_path, "src/Foo.java")
        assert result is not None
        assert result == target.resolve()

    def test_traversal_returns_none(self, tmp_path):
        """Path traversal with ../../ is rejected."""
        result = safe_resolve_path(tmp_path, "../../../etc/passwd")
        assert result is None

    def test_absolute_returns_none(self, tmp_path):
        """Absolute paths are rejected."""
        result = safe_resolve_path(tmp_path, "/etc/passwd")
        assert result is None

    def test_backslash_absolute_returns_none(self, tmp_path):
        """Backslash-prefixed paths are rejected."""
        result = safe_resolve_path(tmp_path, "\\etc\\passwd")
        assert result is None

    def test_empty_string_returns_none(self, tmp_path):
        """Empty file_path is rejected."""
        result = safe_resolve_path(tmp_path, "")
        assert result is None

    def test_null_byte_returns_none(self, tmp_path):
        """Paths with null bytes are rejected."""
        result = safe_resolve_path(tmp_path, "src/foo\x00.py")
        assert result is None

    def test_symlink_escape_returns_none(self, tmp_path):
        """Symlink pointing outside repo root is rejected."""
        link = tmp_path / "escape_link"
        link.symlink_to("/tmp")
        result = safe_resolve_path(tmp_path, "escape_link/something")
        assert result is None

    def test_nested_path_resolves(self, tmp_path):
        """Deeply nested relative path inside repo resolves correctly."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        target = nested / "file.txt"
        target.write_text("content")

        result = safe_resolve_path(tmp_path, "a/b/c/file.txt")
        assert result is not None
        assert result == target.resolve()


# ------------------------------------------------------------------
# extract_identifiers
# ------------------------------------------------------------------


class TestExtractIdentifiers:
    """Tests for extract_identifiers and IDENTIFIER_RE."""

    def test_annotations(self):
        """@Component and similar annotations are extracted."""
        ids = extract_identifiers("@Component\n@Service\npublic class Foo {}")
        assert "@Component" in ids
        assert "@Service" in ids

    def test_pascal_case(self):
        """PascalCase identifiers (3+ chars) are extracted."""
        ids = extract_identifiers("DistributionSummary summary = new DistributionSummary();")
        assert "DistributionSummary" in ids

    def test_dotted_method(self):
        """Dotted method calls are extracted WITHOUT the trailing '('."""
        ids = extract_identifiers("builder.register(registry)")
        assert "builder.register" in ids
        # The paren should NOT be included
        assert "builder.register(" not in ids

    def test_function_call(self):
        """Plain function calls are extracted."""
        ids = extract_identifiers("register_metric(name, value)")
        assert "register_metric" in ids

    def test_empty_text(self):
        """Empty text returns empty set."""
        assert extract_identifiers("") == set()

    def test_short_pascal_case_excluded(self):
        """Two-char PascalCase words (like 'Ok') are excluded (need 3+ chars)."""
        ids = extract_identifiers("Ok value = process();")
        assert "Ok" not in ids
