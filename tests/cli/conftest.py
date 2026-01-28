"""Scoped conftest for CLI integration tests.

This conftest imports CLI-specific fixtures from tests.fixtures.cli_integration,
making them available only to tests in the tests/cli/ directory.
"""

# Import CLI integration fixtures for all tests in this directory
pytest_plugins = ["tests.fixtures.cli_integration"]
