"""Tests for GenericTicket.has_verified_content property."""

from ingot.integrations.providers import GenericTicket, Platform


class TestHasVerifiedContent:
    def _make_ticket(self, title=None, description=None):
        return GenericTicket(
            id="TEST-1",
            platform=Platform.JIRA,
            url="https://example.com/TEST-1",
            title=title,
            description=description,
        )

    def test_title_and_description_returns_true(self):
        ticket = self._make_ticket(title="My Title", description="My Desc")
        assert ticket.has_verified_content is True

    def test_title_only_returns_true(self):
        ticket = self._make_ticket(title="My Title", description=None)
        assert ticket.has_verified_content is True

    def test_description_only_returns_true(self):
        ticket = self._make_ticket(title=None, description="My Desc")
        assert ticket.has_verified_content is True

    def test_neither_returns_false(self):
        ticket = self._make_ticket(title=None, description=None)
        assert ticket.has_verified_content is False

    def test_empty_strings_returns_false(self):
        ticket = self._make_ticket(title="", description="")
        assert ticket.has_verified_content is False

    def test_whitespace_only_returns_false(self):
        ticket = self._make_ticket(title="   ", description="  \n\t  ")
        assert ticket.has_verified_content is False

    def test_whitespace_title_with_real_description(self):
        ticket = self._make_ticket(title="   ", description="Real desc")
        assert ticket.has_verified_content is True

    def test_real_title_with_whitespace_description(self):
        ticket = self._make_ticket(title="Real title", description="  ")
        assert ticket.has_verified_content is True
