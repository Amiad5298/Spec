"""Tests for ingot.discovery.test_mapper module."""

from pathlib import PurePosixPath
from unittest.mock import MagicMock

from ingot.discovery.test_mapper import TestMapper


def _make_mapper(stem_map: dict[str, list[str]]) -> TestMapper:
    """Create a TestMapper with a mocked FileIndex.

    Args:
        stem_map: Maps lowercase stem to list of relative path strings
                  that find_by_stem should return.
    """
    file_index = MagicMock()
    file_index.find_by_stem.side_effect = lambda stem: [
        PurePosixPath(p) for p in stem_map.get(stem.lower(), [])
    ]
    return TestMapper(file_index)


# ------------------------------------------------------------------
# Java conventions
# ------------------------------------------------------------------


class TestJavaConventions:
    """Java: FooService.java -> FooServiceTest.java, FooServiceTests.java, FooServiceSpec.java."""

    def test_finds_test_suffix(self):
        mapper = _make_mapper(
            {
                "fooservicetest": ["src/test/java/FooServiceTest.java"],
            }
        )
        results = mapper.find_tests("src/main/java/FooService.java")
        assert PurePosixPath("src/test/java/FooServiceTest.java") in results

    def test_finds_tests_suffix(self):
        mapper = _make_mapper(
            {
                "fooservicetests": ["src/test/java/FooServiceTests.java"],
            }
        )
        results = mapper.find_tests("src/main/java/FooService.java")
        assert PurePosixPath("src/test/java/FooServiceTests.java") in results

    def test_finds_spec_suffix(self):
        mapper = _make_mapper(
            {
                "fooservicespec": ["src/test/java/FooServiceSpec.java"],
            }
        )
        results = mapper.find_tests("src/main/java/FooService.java")
        assert PurePosixPath("src/test/java/FooServiceSpec.java") in results

    def test_multiple_java_test_files(self):
        mapper = _make_mapper(
            {
                "fooservicetest": ["src/test/java/FooServiceTest.java"],
                "fooservicetests": ["src/test/java/FooServiceTests.java"],
                "fooservicespec": ["src/test/java/FooServiceSpec.java"],
            }
        )
        results = mapper.find_tests("src/main/java/FooService.java")
        assert len(results) == 3


# ------------------------------------------------------------------
# Python conventions
# ------------------------------------------------------------------


class TestPythonConventions:
    """Python: foo.py -> test_foo.py, foo_test.py."""

    def test_finds_test_prefix(self):
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.py"],
            }
        )
        results = mapper.find_tests("src/foo.py")
        assert PurePosixPath("tests/test_foo.py") in results

    def test_finds_test_suffix(self):
        mapper = _make_mapper(
            {
                "foo_test": ["tests/foo_test.py"],
            }
        )
        results = mapper.find_tests("src/foo.py")
        assert PurePosixPath("tests/foo_test.py") in results

    def test_both_python_conventions(self):
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.py"],
                "foo_test": ["tests/foo_test.py"],
            }
        )
        results = mapper.find_tests("src/foo.py")
        assert len(results) == 2


# ------------------------------------------------------------------
# TypeScript conventions
# ------------------------------------------------------------------


class TestTypeScriptConventions:
    """TypeScript: foo.ts -> foo.spec.ts, foo.test.ts."""

    def test_finds_spec_file(self):
        mapper = _make_mapper(
            {
                "foo.spec": ["src/__tests__/foo.spec.ts"],
            }
        )
        results = mapper.find_tests("src/foo.ts")
        assert PurePosixPath("src/__tests__/foo.spec.ts") in results

    def test_finds_test_file(self):
        mapper = _make_mapper(
            {
                "foo.test": ["src/__tests__/foo.test.ts"],
            }
        )
        results = mapper.find_tests("src/foo.ts")
        assert PurePosixPath("src/__tests__/foo.test.ts") in results

    def test_tsx_source_finds_ts_test(self):
        """A .tsx source file should match a .ts test file (extension compatibility)."""
        mapper = _make_mapper(
            {
                "component.spec": ["tests/component.spec.ts"],
            }
        )
        results = mapper.find_tests("src/Component.tsx")
        # .tsx and .ts are in the same extension group
        assert PurePosixPath("tests/component.spec.ts") in results

    def test_tsx_source_finds_tsx_test(self):
        """A .tsx source file should also match a .tsx test file."""
        mapper = _make_mapper(
            {
                "component.test": ["tests/component.test.tsx"],
            }
        )
        results = mapper.find_tests("src/Component.tsx")
        assert PurePosixPath("tests/component.test.tsx") in results


# ------------------------------------------------------------------
# Go conventions
# ------------------------------------------------------------------


class TestGoConventions:
    """Go: foo.go -> foo_test.go."""

    def test_finds_go_test_file(self):
        mapper = _make_mapper(
            {
                "handler_test": ["pkg/handler_test.go"],
            }
        )
        results = mapper.find_tests("pkg/handler.go")
        assert PurePosixPath("pkg/handler_test.go") in results


# ------------------------------------------------------------------
# Ruby conventions
# ------------------------------------------------------------------


class TestRubyConventions:
    """Ruby: foo.rb -> foo_spec.rb, foo_test.rb, test_foo.rb."""

    def test_finds_spec_file(self):
        mapper = _make_mapper(
            {
                "user_spec": ["spec/user_spec.rb"],
            }
        )
        results = mapper.find_tests("lib/user.rb")
        assert PurePosixPath("spec/user_spec.rb") in results

    def test_finds_test_prefix(self):
        mapper = _make_mapper(
            {
                "test_user": ["test/test_user.rb"],
            }
        )
        results = mapper.find_tests("lib/user.rb")
        assert PurePosixPath("test/test_user.rb") in results


# ------------------------------------------------------------------
# Kotlin conventions
# ------------------------------------------------------------------


class TestKotlinConventions:
    """Kotlin: Foo.kt -> FooTest.kt."""

    def test_finds_kotlin_test(self):
        mapper = _make_mapper(
            {
                "footest": ["src/test/kotlin/FooTest.kt"],
            }
        )
        results = mapper.find_tests("src/main/kotlin/Foo.kt")
        assert PurePosixPath("src/test/kotlin/FooTest.kt") in results


# ------------------------------------------------------------------
# Rust conventions
# ------------------------------------------------------------------


class TestRustConventions:
    """Rust: foo.rs -> foo_test.rs."""

    def test_finds_rust_test(self):
        mapper = _make_mapper(
            {
                "foo_test": ["tests/foo_test.rs"],
            }
        )
        results = mapper.find_tests("src/foo.rs")
        assert PurePosixPath("tests/foo_test.rs") in results


# ------------------------------------------------------------------
# C# conventions
# ------------------------------------------------------------------


class TestCSharpConventions:
    """C#: Foo.cs -> FooTests.cs."""

    def test_finds_csharp_tests(self):
        mapper = _make_mapper(
            {
                "footests": ["Tests/FooTests.cs"],
            }
        )
        results = mapper.find_tests("src/Foo.cs")
        assert PurePosixPath("Tests/FooTests.cs") in results


# ------------------------------------------------------------------
# Swift conventions
# ------------------------------------------------------------------


class TestSwiftConventions:
    """Swift: Foo.swift -> FooTests.swift."""

    def test_finds_swift_tests(self):
        mapper = _make_mapper(
            {
                "footests": ["Tests/FooTests.swift"],
            }
        )
        results = mapper.find_tests("src/Foo.swift")
        assert PurePosixPath("Tests/FooTests.swift") in results


# ------------------------------------------------------------------
# JavaScript conventions
# ------------------------------------------------------------------


class TestJavaScriptConventions:
    """JavaScript: foo.js -> foo.spec.js."""

    def test_finds_js_spec(self):
        mapper = _make_mapper(
            {
                "foo.spec": ["tests/foo.spec.js"],
            }
        )
        results = mapper.find_tests("src/foo.js")
        assert PurePosixPath("tests/foo.spec.js") in results


# ------------------------------------------------------------------
# Edge cases
# ------------------------------------------------------------------


class TestTestDirectoryPreference:
    """Test that files in test directories are ranked higher."""

    def test_test_directory_preferred_over_non_test(self):
        """File in tests/ should be ranked before same-name file in docs/examples/."""
        mapper = _make_mapper(
            {
                "test_foo": [
                    "docs/examples/test_foo.py",
                    "tests/test_foo.py",
                ],
            }
        )
        results = mapper.find_tests("src/foo.py")
        assert len(results) == 2
        # The file in tests/ should come first
        assert results[0] == PurePosixPath("tests/test_foo.py")
        assert results[1] == PurePosixPath("docs/examples/test_foo.py")

    def test_multiple_test_dirs_all_preferred(self):
        """Files in __tests__ and spec/ should both rank above non-test dirs."""
        mapper = _make_mapper(
            {
                "foo.spec": [
                    "src/utils/foo.spec.ts",
                    "src/__tests__/foo.spec.ts",
                ],
            }
        )
        results = mapper.find_tests("src/foo.ts")
        assert len(results) == 2
        assert results[0] == PurePosixPath("src/__tests__/foo.spec.ts")


class TestEdgeCases:
    """No test found, unknown extension, dedup."""

    def test_no_test_for_unknown_extension(self):
        """Files with unsupported extensions return empty results."""
        mapper = _make_mapper({})
        results = mapper.find_tests("docs/readme.txt")
        assert results == []

    def test_no_test_found_returns_empty(self):
        """When no matching test files exist, return empty list."""
        mapper = _make_mapper(
            {
                "test_missing": [],
                "missing_test": [],
            }
        )
        results = mapper.find_tests("src/missing.py")
        assert results == []

    def test_deduplicates_results(self):
        """Same path returned by multiple conventions should appear only once."""
        # Both test_foo and foo_test resolve to same path (unlikely but guard against)
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.py"],
                "foo_test": ["tests/test_foo.py"],  # Same path from different convention
            }
        )
        results = mapper.find_tests("src/foo.py")
        # Should appear only once (deduplicated)
        assert results.count(PurePosixPath("tests/test_foo.py")) == 1

    def test_incompatible_extension_filtered(self):
        """A .java test file should not match a .py source file."""
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.java"],  # Wrong extension
            }
        )
        results = mapper.find_tests("src/foo.py")
        assert results == []


# ------------------------------------------------------------------
# map_all
# ------------------------------------------------------------------


class TestMapAll:
    """Test the map_all batch mapping method."""

    def test_maps_multiple_sources(self):
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.py"],
                "test_bar": ["tests/test_bar.py"],
            }
        )
        result = mapper.map_all(["src/foo.py", "src/bar.py"])
        assert "src/foo.py" in result
        assert "src/bar.py" in result
        assert PurePosixPath("tests/test_foo.py") in result["src/foo.py"]

    def test_excludes_sources_with_no_tests(self):
        mapper = _make_mapper(
            {
                "test_foo": ["tests/test_foo.py"],
            }
        )
        result = mapper.map_all(["src/foo.py", "src/bar.py"])
        assert "src/foo.py" in result
        assert "src/bar.py" not in result

    def test_empty_sources_returns_empty(self):
        mapper = _make_mapper({})
        result = mapper.map_all([])
        assert result == {}

    def test_accepts_purepath_input(self):
        mapper = _make_mapper(
            {
                "handler_test": ["pkg/handler_test.go"],
            }
        )
        result = mapper.map_all([PurePosixPath("pkg/handler.go")])
        assert "pkg/handler.go" in result
