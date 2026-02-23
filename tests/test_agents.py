"""Tests for ingot.integrations.agents module."""

from ingot.integrations.agents import (
    _REQUIRED_AGENTS,
    AGENT_BODIES,
    AGENT_METADATA,
    get_agents_dir,
    verify_agents_available,
)
from ingot.workflow.constants import (
    INGOT_AGENT_RESEARCHER,
    RESEARCHER_SECTION_HEADINGS,
)


class TestVerifyAgentsAvailable:
    """Only required agents from AGENT_METADATA are checked."""

    def test_only_required_agents_checked_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # No agents dir — only required agents should be missing
        all_ok, missing = verify_agents_available()
        assert not all_ok
        expected_names = {
            meta["name"] for key, meta in AGENT_METADATA.items() if key in _REQUIRED_AGENTS
        }
        assert set(missing) == expected_names

    def test_optional_agents_not_reported(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        all_ok, missing = verify_agents_available()
        # Optional agents should NOT appear in missing list
        assert "ingot-reviewer" not in missing
        assert "ingot-researcher" not in missing
        assert "ingot-tasklist-refiner" not in missing

    def test_all_required_present_returns_true(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        agents_dir = get_agents_dir()
        agents_dir.mkdir(parents=True, exist_ok=True)
        # Only create required agents
        for key, meta in AGENT_METADATA.items():
            if key in _REQUIRED_AGENTS:
                (agents_dir / f"{meta['name']}.md").write_text("# agent")

        all_ok, missing = verify_agents_available()
        assert all_ok
        assert missing == []


class TestResearcherSectionHeadingsSync:
    """Assert all RESEARCHER_SECTION_HEADINGS appear in researcher prompt body."""

    def test_all_headings_in_researcher_body(self):
        researcher_body = AGENT_BODIES[INGOT_AGENT_RESEARCHER]
        for heading in RESEARCHER_SECTION_HEADINGS:
            # Strip the leading "### " to match the heading text in the prompt
            heading_text = heading.lstrip("# ")
            assert (
                heading_text in researcher_body
            ), f"Heading '{heading}' not found in researcher prompt body"
