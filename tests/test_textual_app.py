"""Tests for the base Textual application shell."""

from ingot.ui.textual_app import IngotApp


def test_app_instantiation() -> None:
    """IngotApp can be created without errors."""
    app = IngotApp()
    assert app.title == "INGOT"


async def test_app_runs_headless() -> None:
    """App boots and shuts down cleanly in headless mode."""
    app = IngotApp()
    async with app.run_test() as pilot:
        assert app.is_running
        await pilot.exit(None)


async def test_quit_binding() -> None:
    """Pressing 'q' triggers quit."""
    app = IngotApp()
    async with app.run_test() as pilot:
        await pilot.press("q")
    assert not app.is_running
