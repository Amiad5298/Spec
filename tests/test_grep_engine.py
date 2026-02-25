"""Tests for ingot.discovery.grep_engine module."""

from pathlib import PurePosixPath

import pytest

from ingot.discovery.grep_engine import GrepEngine


@pytest.fixture()
def sample_repo(tmp_path):
    """Create a sample repository with searchable files."""
    (tmp_path / "src").mkdir()

    (tmp_path / "src" / "foo.py").write_text(
        "import os\n\nclass FooService:\n    def process(self):\n        return 42\n"
    )

    (tmp_path / "src" / "bar.py").write_text(
        "from foo import FooService\n"
        "\n"
        "class BarHelper:\n"
        "    def __init__(self):\n"
        "        self.foo = FooService()\n"
        "\n"
        "    def run(self):\n"
        "        return self.foo.process()\n"
    )

    (tmp_path / "src" / "config.yml").write_text("server:\n  port: 8080\n  name: my-service\n")

    # Binary file
    (tmp_path / "src" / "image.bin").write_bytes(b"\x00\x01\x02\x03")

    file_paths = [
        PurePosixPath("src/foo.py"),
        PurePosixPath("src/bar.py"),
        PurePosixPath("src/config.yml"),
        PurePosixPath("src/image.bin"),
    ]

    return tmp_path, file_paths


class TestGrepEngineBasic:
    """Test basic GrepEngine search functionality."""

    def test_simple_match(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("FooService")
        assert len(matches) >= 2
        assert any(m.file == PurePosixPath("src/foo.py") for m in matches)
        assert any(m.file == PurePosixPath("src/bar.py") for m in matches)

    def test_regex_match(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search(r"class \w+:")
        assert len(matches) == 2
        assert any("FooService" in m.line_content for m in matches)
        assert any("BarHelper" in m.line_content for m in matches)

    def test_no_match(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("NonExistentPattern")
        assert matches == []

    def test_case_insensitive(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("fooservice", ignore_case=True)
        assert len(matches) >= 2

    def test_case_sensitive_default(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("fooservice")
        assert matches == []

    def test_invalid_regex_returns_empty(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("[invalid")
        assert matches == []

    def test_binary_file_skipped(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search(".*")
        # Binary file should be skipped
        assert not any(m.file == PurePosixPath("src/image.bin") for m in matches)


class TestGrepEngineContext:
    """Test context lines functionality."""

    def test_context_lines(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths, context_lines=1)
        matches = engine.search("class FooService:")
        assert len(matches) == 1
        match = matches[0]
        assert len(match.context_before) <= 1
        assert len(match.context_after) <= 1

    def test_no_context_by_default(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("class FooService:")
        assert len(matches) == 1
        assert matches[0].context_before == ()
        assert matches[0].context_after == ()


class TestGrepEngineLimits:
    """Test max match limits."""

    def test_max_matches_per_file(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths, max_matches_per_file=1)
        # "self" appears in both foo.py and bar.py, multiple times per file
        matches = engine.search(r"self\.")
        file_counts: dict[PurePosixPath, int] = {}
        for m in matches:
            file_counts[m.file] = file_counts.get(m.file, 0) + 1
        for count in file_counts.values():
            assert count <= 1

    def test_max_matches_total(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths, max_matches_total=2)
        matches = engine.search(r"\w+")
        assert len(matches) <= 2


class TestGrepEngineBatch:
    """Test batch search functionality."""

    def test_batch_search_multiple_patterns(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        results = engine.search_batch(["FooService", "BarHelper"])
        assert "FooService" in results
        assert "BarHelper" in results
        assert len(results["FooService"]) >= 2
        assert len(results["BarHelper"]) >= 1

    def test_batch_search_invalid_pattern_skipped(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        results = engine.search_batch(["FooService", "[invalid"])
        assert len(results["FooService"]) >= 2
        assert results["[invalid"] == []

    def test_batch_search_empty_patterns(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        results = engine.search_batch([])
        assert results == {}


class TestGrepMatchDataclass:
    """Test GrepMatch properties."""

    def test_match_fields(self, sample_repo):
        tmp_path, file_paths = sample_repo
        engine = GrepEngine(tmp_path, file_paths)
        matches = engine.search("class FooService:")
        assert len(matches) == 1
        match = matches[0]
        assert match.file == PurePosixPath("src/foo.py")
        assert match.line_num == 3
        assert "class FooService:" in match.line_content
