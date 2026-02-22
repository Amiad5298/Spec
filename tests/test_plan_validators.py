"""Tests for ingot.validation.plan_validators module."""

from ingot.validation.base import (
    ValidationContext,
    ValidationFinding,
    ValidationReport,
    ValidationSeverity,
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

PLAN_WITH_CODE_BLOCKS = """\
# Plan

## Summary
Summary here.

## Technical Approach
Approach here.

## Implementation Steps

Pattern source: `src/main.py:10-20`
```python
def example():
    a = 1
    b = 2
    return a + b
```

## Testing Strategy
Tests here.

## Potential Risks
Risks here.

## Out of Scope
Nothing.
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
