#!/usr/bin/env bash
# Guard script to prevent re-introduction of legacy naming patterns.
# Used by both CI and pre-commit. See AMI-66.

set -euo pipefail

EXIT_CODE=0

echo "Checking for forbidden AGENT_PLATFORM pattern in ingot/ and tests/..."
if grep -r -i -n "agent_platform" --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy AGENT_PLATFORM naming. Use AI_BACKEND instead. See AMI-66."
  EXIT_CODE=1
fi

echo "Checking for legacy SPECFLOW pattern in ingot/ and tests/..."
if grep -r -n "SPECFLOW" --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy SPECFLOW naming. Use INGOT instead."
  EXIT_CODE=1
fi

echo "Checking for legacy 'from spec.' imports in ingot/ and tests/..."
if grep -r -n "from spec\." --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy 'from spec.' imports. Use 'from ingot.' instead."
  EXIT_CODE=1
fi

echo "Checking for legacy .spec-config references in ingot/ and tests/..."
if grep -r -n "\.spec-config" --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy .spec-config references. Use .ingot-config instead."
  EXIT_CODE=1
fi

echo "Checking for legacy SPEC_LOG references in ingot/ and tests/..."
if grep -r -n "SPEC_LOG" --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy SPEC_LOG references. Use INGOT_LOG instead."
  EXIT_CODE=1
fi

echo "Checking for legacy SpecError references in ingot/ and tests/..."
if grep -r -n "SpecError" --include="*.py" ingot/ tests/ 2>/dev/null; then
  echo ""
  echo "ERROR: Found legacy SpecError references. Use IngotError instead."
  EXIT_CODE=1
fi

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "No legacy naming patterns found."
fi

exit $EXIT_CODE
