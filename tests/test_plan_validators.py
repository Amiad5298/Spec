"""Tests for ingot.validation.plan_validators module."""

from unittest.mock import patch

from ingot.validation.base import (
    ValidationContext,
    ValidationFinding,
    ValidationReport,
    ValidationSeverity,
    Validator,
    ValidatorRegistry,
)
from ingot.validation.plan_validators import (
    DiscoveryCoverageValidator,
    FileExistsValidator,
    PatternSourceValidator,
    RequiredSectionsValidator,
    UnresolvedMarkersValidator,
    create_plan_validator_registry,
)

# =============================================================================
# Helpers
# =============================================================================

COMPLETE_PLAN = """\
# Implementation Plan: TEST-123

## Summary
Brief summary of what will be implemented.

## Technical Approach
Architecture decisions and patterns.

## Implementation Steps
1. Step one
2. Step two

## Testing Strategy
- Unit tests for new functionality

## Potential Risks or Considerations
- Risk one

## Out of Scope
- Not included
"""


# =============================================================================
# TestRequiredSectionsValidator
# =============================================================================


class TestRequiredSectionsValidator:
    def test_plan_with_all_sections_no_findings(self):
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(COMPLETE_PLAN, ctx)
        assert findings == []

    def test_plan_missing_testing_strategy(self):
        plan = COMPLETE_PLAN.replace("## Testing Strategy", "## Something Else")
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.ERROR
        assert "Testing Strategy" in findings[0].message

    def test_plan_missing_multiple_sections(self):
        plan = "# Plan\n\n## Summary\nJust a summary.\n"
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        # Missing: Technical Approach, Implementation Steps, Testing Strategy,
        # Potential Risks, Out of Scope
        assert len(findings) == 5
        assert all(f.severity == ValidationSeverity.ERROR for f in findings)

    def test_variant_name_still_passes(self):
        plan = COMPLETE_PLAN.replace(
            "## Potential Risks or Considerations",
            "### Potential Risks and Edge Cases",
        )
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_case_insensitive_matching(self):
        plan = COMPLETE_PLAN.replace("## Summary", "## SUMMARY")
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# TestFileExistsValidator
# =============================================================================


class TestFileExistsValidator:
    def test_existing_paths_no_findings(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# code")
        plan = "Modify `src/main.py` to add the feature."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_nonexistent_path_error(self, tmp_path):
        plan = "Modify `src/nonexistent.py` to add the feature."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.ERROR
        assert "src/nonexistent.py" in findings[0].message

    def test_unverified_markers_skipped(self, tmp_path):
        plan = "<!-- UNVERIFIED: not sure about this --> `src/unknown.py` is referenced."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_templated_paths_skipped(self, tmp_path):
        plan = "Create `src/{module}/handler.py` for each module."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_placeholder_path_skipped(self, tmp_path):
        plan = "See `path/to/file.java` for reference."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_punctuation_inside_backticks_stripped(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# code")
        plan = "Check `src/main.py,` for the implementation."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_path_with_line_number_extracted(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# code")
        plan = "See `src/main.py:42` for the function."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_path_with_line_range_extracted(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# code")
        plan = "See `src/main.py:42-58` for the function."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_multiple_paths_in_one_line(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text("# a")
        plan = "Modify `src/a.py` and `src/b.py` together."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        # a.py exists, b.py doesn't
        assert len(findings) == 1
        assert "src/b.py" in findings[0].message

    def test_repo_root_none_skips_all(self):
        plan = "Modify `src/nonexistent.py` to add the feature."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=None)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_parentheses_quotes_stripped(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# code")
        plan = 'Check `("src/main.py")` for details.'
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# TestPatternSourceValidator
# =============================================================================


class TestPatternSourceValidator:
    def test_code_block_with_source_before_no_findings(self):
        plan = """\
Pattern source: `src/main.py:10-20`
```python
def example():
    a = 1
    b = 2
    return a + b
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_code_block_with_source_after_no_findings(self):
        plan = """\
```python
def example():
    a = 1
    b = 2
    return a + b
```
Pattern source: `src/main.py:10-20`
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_code_block_with_no_existing_pattern_marker(self):
        plan = """\
<!-- NO_EXISTING_PATTERN: new utility function -->
```python
def new_util():
    a = 1
    b = 2
    return a + b
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_ungrounded_code_block_warning(self):
        plan = """\
Some text here.

```python
def example():
    a = 1
    b = 2
    return a + b
```

More text.
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING
        assert "Pattern source" in findings[0].message

    def test_short_code_block_skipped(self):
        plan = """\
```python
x = 1
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        # < 3 content lines, should be skipped
        assert findings == []

    def test_two_line_block_skipped(self):
        plan = """\
```python
x = 1
y = 2
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# TestUnresolvedMarkersValidator
# =============================================================================


class TestUnresolvedMarkersValidator:
    def test_no_markers_no_findings(self):
        validator = UnresolvedMarkersValidator()
        ctx = ValidationContext()
        findings = validator.validate("# Plan\n\nNo markers here.", ctx)
        assert findings == []

    def test_unverified_marker_info(self):
        plan = "Some text <!-- UNVERIFIED: file path guessed --> more text."
        validator = UnresolvedMarkersValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.INFO
        assert "UNVERIFIED" in findings[0].message

    def test_no_existing_pattern_marker_info(self):
        plan = "Some text <!-- NO_EXISTING_PATTERN: new approach --> more text."
        validator = UnresolvedMarkersValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.INFO
        assert "NO_EXISTING_PATTERN" in findings[0].message

    def test_multiple_markers(self):
        plan = (
            "<!-- UNVERIFIED: first -->\n"
            "<!-- NO_EXISTING_PATTERN: second -->\n"
            "<!-- UNVERIFIED: third -->"
        )
        validator = UnresolvedMarkersValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 3
        assert all(f.severity == ValidationSeverity.INFO for f in findings)


# =============================================================================
# TestDiscoveryCoverageValidator
# =============================================================================


class TestDiscoveryCoverageValidator:
    def test_no_researcher_output_no_findings(self):
        validator = DiscoveryCoverageValidator(researcher_output="")
        ctx = ValidationContext()
        findings = validator.validate("# Plan\nSome content.", ctx)
        assert findings == []

    def test_interface_mentioned_in_plan_no_finding(self):
        researcher = """\
### Interface & Class Hierarchy
#### `MyInterface`
- Implemented by: `ConcreteClass` (`src/concrete.py:10`)
"""
        plan = "## Implementation Steps\nModify MyInterface to add new method."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_interface_missing_from_plan_warning(self):
        researcher = """\
### Interface & Class Hierarchy
#### `MyInterface`
- Implemented by: `ConcreteClass` (`src/concrete.py:10`)
"""
        plan = "## Implementation Steps\nDo something else entirely."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING
        assert "MyInterface" in findings[0].message

    def test_interface_in_out_of_scope_no_finding(self):
        researcher = """\
### Interface & Class Hierarchy
#### `MyInterface`
- Implemented by: `ConcreteClass` (`src/concrete.py:10`)
"""
        plan = "## Out of Scope\nMyInterface changes are not needed."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_method_from_call_sites_missing_warning(self):
        researcher = """\
### Call Sites
#### `processOrder()`
- Called from: `OrderService.handle()` (`src/order.py:42`)
"""
        plan = "## Implementation Steps\nOnly update the database layer."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "processOrder" in findings[0].message

    def test_method_with_parentheses_stripped(self):
        researcher = """\
### Call Sites
#### `doWork()`
- Called from: `Worker.run()` (`src/worker.py:10`)
"""
        plan = "## Implementation Steps\nUpdate doWork to handle errors."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# TestValidatorRegistry
# =============================================================================


class TestValidatorRegistry:
    def test_empty_registry_empty_report(self):
        registry = ValidatorRegistry()
        ctx = ValidationContext()
        report = registry.validate_all("# Plan", ctx)
        assert report.findings == []
        assert not report.has_errors
        assert not report.has_warnings

    def test_multiple_validators_aggregated(self):
        registry = ValidatorRegistry()
        registry.register(RequiredSectionsValidator())
        registry.register(UnresolvedMarkersValidator())
        ctx = ValidationContext()
        # Missing sections + no markers = only section errors
        report = registry.validate_all("# Just a heading", ctx)
        assert report.has_errors
        assert report.error_count > 0

    def test_factory_returns_all_validators(self):
        registry = create_plan_validator_registry()
        assert len(registry.validators) == 5

    def test_factory_passes_researcher_output(self):
        researcher = "### Interface & Class Hierarchy\n#### `Foo`\n"
        registry = create_plan_validator_registry(researcher_output=researcher)
        # Find the DiscoveryCoverageValidator
        discovery_validators = [
            v for v in registry.validators if isinstance(v, DiscoveryCoverageValidator)
        ]
        assert len(discovery_validators) == 1
        assert discovery_validators[0]._researcher_output == researcher

    def test_report_properties(self):
        report = ValidationReport()
        assert not report.has_errors
        assert not report.has_warnings
        assert report.error_count == 0
        assert report.warning_count == 0

        report.findings.append(
            ValidationFinding(
                validator_name="test",
                severity=ValidationSeverity.ERROR,
                message="error",
            )
        )
        report.findings.append(
            ValidationFinding(
                validator_name="test",
                severity=ValidationSeverity.WARNING,
                message="warning",
            )
        )
        assert report.has_errors
        assert report.has_warnings
        assert report.error_count == 1
        assert report.warning_count == 1


# =============================================================================
# TestValidatorRegistryCrashIsolation
# =============================================================================


class TestValidatorRegistryCrashIsolation:
    """Ensure a crashing validator doesn't skip others."""

    def test_crash_does_not_skip_remaining_validators(self):
        class CrashingValidator(Validator):
            @property
            def name(self) -> str:
                return "Crasher"

            def validate(self, content, context):
                raise RuntimeError("boom")

        registry = ValidatorRegistry()
        registry.register(CrashingValidator())
        registry.register(UnresolvedMarkersValidator())

        plan = "<!-- UNVERIFIED: test -->"
        ctx = ValidationContext()
        report = registry.validate_all(plan, ctx)

        # Should have one ERROR from crash + one INFO from marker
        names = [f.validator_name for f in report.findings]
        assert "Crasher" in names
        assert "Unresolved Markers" in names
        crash_finding = [f for f in report.findings if f.validator_name == "Crasher"][0]
        assert crash_finding.severity == ValidationSeverity.ERROR
        assert "Validator crashed" in crash_finding.message


# =============================================================================
# TestFileExistsValidatorEdgeCases
# =============================================================================


class TestFileExistsValidatorEdgeCases:
    def test_duplicate_paths_deduplicated(self, tmp_path):
        plan = "Modify `src/foo.py` and also `src/foo.py` again."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        # Should report the missing file only once despite two references
        assert len(findings) == 1

    def test_path_traversal_ignored(self, tmp_path):
        # Create a file outside repo root to prove traversal is blocked
        plan = "Modify `../../etc/passwd.txt` for the feature."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        # Path traversal should be silently skipped (no error reported)
        assert findings == []

    def test_url_paths_skipped(self, tmp_path):
        """URLs should not be treated as file paths."""
        plan = (
            "See `https://example.com/docs/guide.html` and "
            "`http://api.example.com/v1/resource.json` for details."
        )
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# TestPatternSourceValidatorEdgeCases
# =============================================================================


class TestPatternSourceValidatorEdgeCases:
    def test_exactly_three_line_block_checked(self):
        """A code block with exactly 3 content lines should be validated."""
        plan = """\
```python
a = 1
b = 2
c = 3
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert findings[0].severity == ValidationSeverity.WARNING


# =============================================================================
# TestDiscoveryCoverageValidatorEdgeCases
# =============================================================================


class TestDiscoveryCoverageValidatorEdgeCases:
    def test_short_name_no_false_match(self):
        """Word-boundary fix: 'get' should NOT match 'getUser'."""
        researcher = """\
### Call Sites
#### `get()`
- Called from: `Service.fetch()` (`src/service.py:10`)
"""
        plan = "## Implementation Steps\nUpdate getUser to handle errors."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "get" in findings[0].message

    def test_multiple_missing_items_all_reported(self):
        researcher = """\
### Interface & Class Hierarchy
#### `Alpha`
- Implemented by: `AlphaImpl` (`src/alpha.py:1`)
#### `Beta`
- Implemented by: `BetaImpl` (`src/beta.py:1`)
### Call Sites
#### `gamma()`
- Called from: `Runner.go()` (`src/run.py:1`)
"""
        plan = "## Implementation Steps\nDo something unrelated entirely."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        missing_names = {f.message.split("'")[1] for f in findings}
        assert missing_names == {"Alpha", "Beta", "gamma"}


# =============================================================================
# TestValidationReport
# =============================================================================


class TestValidationReport:
    def test_info_count_property(self):
        report = ValidationReport()
        assert report.info_count == 0

        report.findings.append(
            ValidationFinding(
                validator_name="test",
                severity=ValidationSeverity.INFO,
                message="info 1",
            )
        )
        report.findings.append(
            ValidationFinding(
                validator_name="test",
                severity=ValidationSeverity.WARNING,
                message="warning",
            )
        )
        report.findings.append(
            ValidationFinding(
                validator_name="test",
                severity=ValidationSeverity.INFO,
                message="info 2",
            )
        )
        assert report.info_count == 2


# =============================================================================
# A3: TestRequiredSectionsValidatorCodeBlocks
# =============================================================================


class TestRequiredSectionsValidatorCodeBlocks:
    def test_heading_inside_code_block_not_matched(self):
        """A heading inside a fenced code block should NOT satisfy the section requirement."""
        plan = """\
# Implementation Plan

## Summary
Brief summary.

## Technical Approach
Approach.

```markdown
## Testing Strategy
This is inside a code block, not a real section.
```

## Implementation Steps
1. Step one

## Potential Risks
- Risk one

## Out of Scope
- Not included
"""
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        # "Testing Strategy" is only inside a code block — should be reported missing
        assert len(findings) == 1
        assert "Testing Strategy" in findings[0].message

    def test_heading_outside_code_block_still_matched(self):
        """A real heading outside code blocks should still pass."""
        plan = COMPLETE_PLAN
        validator = RequiredSectionsValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# A4: TestFileExistsValidatorRootFiles
# =============================================================================


class TestFileExistsValidatorRootFiles:
    def test_root_file_with_extension_found(self, tmp_path):
        (tmp_path / "setup.py").write_text("# setup")
        plan = "Check `setup.py` for configuration."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_root_file_with_extension_missing(self, tmp_path):
        plan = "Check `setup.py` for configuration."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "setup.py" in findings[0].message

    def test_known_extensionless_found(self, tmp_path):
        (tmp_path / "Makefile").write_text("all:")
        plan = "See `Makefile` for build instructions."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_known_extensionless_missing(self, tmp_path):
        plan = "See `Dockerfile` for container setup."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "Dockerfile" in findings[0].message

    def test_random_word_not_matched_as_file(self, tmp_path):
        """Words like `os.path` or `re.compile` should NOT be matched as root files."""
        plan = "Use `os.path` and `re.compile` for processing."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        # These should not be treated as files (no common extension)
        assert findings == []


# =============================================================================
# B12: TestFileExistsValidatorURLSchemes
# =============================================================================


class TestFileExistsValidatorURLSchemes:
    def test_s3_url_skipped(self, tmp_path):
        plan = "Download from `s3://my-bucket/data/file.csv` for the dataset."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_ssh_url_skipped(self, tmp_path):
        plan = "Clone from `ssh://git@github.com/org/repo.git` for source."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_file_url_skipped(self, tmp_path):
        plan = "Open `file:///usr/local/config.json` for reference."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_git_url_skipped(self, tmp_path):
        plan = "Fetch from `git://github.com/org/repo.git` for source."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_gs_url_skipped(self, tmp_path):
        plan = "Download from `gs://bucket/path/data.parquet` for data."
        validator = FileExistsValidator()
        ctx = ValidationContext(repo_root=tmp_path)
        findings = validator.validate(plan, ctx)
        assert findings == []


# =============================================================================
# A6: TestPatternSourceValidatorUnbalancedFences
# =============================================================================


class TestPatternSourceValidatorUnbalancedFences:
    def test_single_unbalanced_fence_warning(self):
        """A single opening ``` without a close should emit a warning."""
        plan = """\
Some text before.

```python
def orphan():
    pass
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert any("Unbalanced code fence" in f.message for f in findings)

    def test_odd_fences_handled(self):
        """Three fences: first two pair up, third is unbalanced."""
        plan = """\
```python
a = 1
```

```python
def orphan():
    pass
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        # Should have an unbalanced fence warning
        assert any("Unbalanced code fence" in f.message for f in findings)

    def test_balanced_fences_no_unbalanced_warning(self):
        """Balanced fences should NOT produce an unbalanced warning."""
        plan = """\
```python
a = 1
```
"""
        validator = PatternSourceValidator()
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert not any("Unbalanced" in f.message for f in findings)


# =============================================================================
# A7: TestDiscoveryCoverageValidatorSectionAware
# =============================================================================


class TestDiscoveryCoverageValidatorSectionAware:
    def test_name_in_summary_only_still_warns(self):
        """A name mentioned only in Summary (not a target section) should warn."""
        researcher = """\
### Interface & Class Hierarchy
#### `MyService`
- Implemented by: `MyServiceImpl` (`src/service.py:10`)
"""
        plan = """\
## Summary
MyService needs changes.

## Technical Approach
Use the adapter pattern.

## Implementation Steps
1. Modify the adapter.

## Testing Strategy
- Unit tests

## Potential Risks
- None

## Out of Scope
- Nothing
"""
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "MyService" in findings[0].message

    def test_name_in_implementation_steps_passes(self):
        """A name mentioned in Implementation Steps should not warn."""
        researcher = """\
### Interface & Class Hierarchy
#### `MyService`
- Implemented by: `MyServiceImpl` (`src/service.py:10`)
"""
        plan = """\
## Summary
Summary.

## Technical Approach
Approach.

## Implementation Steps
1. Modify MyService to add new method.

## Testing Strategy
- Unit tests

## Potential Risks
- None

## Out of Scope
- Nothing
"""
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert findings == []

    def test_name_in_code_block_inside_target_section_not_matched(self):
        """A name inside a code block in a target section should NOT satisfy coverage."""
        researcher = """\
### Interface & Class Hierarchy
#### `MyService`
- Implemented by: `MyServiceImpl` (`src/service.py:10`)
"""
        plan = """\
## Summary
Summary.

## Technical Approach
Approach.

## Implementation Steps
1. Do something else.

```python
# MyService is here but inside a code block
class MyService:
    pass
```

## Testing Strategy
- Unit tests

## Potential Risks
- None

## Out of Scope
- Nothing
"""
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        assert len(findings) == 1
        assert "MyService" in findings[0].message

    def test_fallback_to_full_content_when_no_target_sections(self):
        """When no target sections exist, fallback to searching full content."""
        researcher = """\
### Interface & Class Hierarchy
#### `MyService`
- Implemented by: `MyServiceImpl` (`src/service.py:10`)
"""
        # Malformed plan with no matching target sections
        plan = "# Plan\n\nMyService is mentioned here."
        validator = DiscoveryCoverageValidator(researcher_output=researcher)
        ctx = ValidationContext()
        findings = validator.validate(plan, ctx)
        # Fallback: full content is searched, so MyService is found
        assert findings == []


# =============================================================================
# A8: TestValidatorRegistryCrashLogging
# =============================================================================


class TestValidatorRegistryCrashLogging:
    def test_crash_logs_stack_trace(self):
        """Verify log_message is called with traceback content on crash."""

        class CrashingValidator(Validator):
            @property
            def name(self) -> str:
                return "Crasher"

            def validate(self, content, context):
                raise RuntimeError("test crash boom")

        registry = ValidatorRegistry()
        registry.register(CrashingValidator())
        ctx = ValidationContext()

        with patch("ingot.validation.base.log_message") as mock_log:
            report = registry.validate_all("# Plan", ctx)

            # log_message should have been called with traceback content
            mock_log.assert_called_once()
            log_call_arg = mock_log.call_args[0][0]
            assert "Crasher" in log_call_arg
            assert "test crash boom" in log_call_arg
            assert "Traceback" in log_call_arg

        # Finding should still be present
        assert len(report.findings) == 1
        assert report.findings[0].severity == ValidationSeverity.ERROR
        assert "Validator crashed" in report.findings[0].message
