"""Tests for SingleOperationScreen — single-operation full-screen layout."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Footer

from ingot.ui.screens.single_operation import SingleOperationScreen
from ingot.ui.widgets.single_operation import SingleOperationWidget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SingleOperationTestApp(App[None]):
    """Minimal app that pushes a SingleOperationScreen on mount."""

    def __init__(
        self,
        ticket_id: str = "",
        log_path: str = "",
    ) -> None:
        super().__init__()
        self._ticket_id = ticket_id
        self._log_path = log_path

    def on_mount(self) -> None:
        screen = SingleOperationScreen(
            ticket_id=self._ticket_id,
            log_path=self._log_path,
        )
        self.push_screen(screen)


def _get_screen(app: SingleOperationTestApp) -> SingleOperationScreen:
    """Get the active SingleOperationScreen from the app."""
    screen = app.screen
    assert isinstance(screen, SingleOperationScreen)
    return screen


# ===========================================================================
# Composition tests
# ===========================================================================


class TestComposition:
    """Tests that the screen composes the expected widgets."""

    @pytest.mark.timeout(10)
    async def test_contains_single_operation_widget(self) -> None:
        """Screen contains a SingleOperationWidget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.query_one("#single-op", SingleOperationWidget)

    @pytest.mark.timeout(10)
    async def test_contains_footer(self) -> None:
        """Screen contains a Footer widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.query_one(Footer)

    @pytest.mark.timeout(10)
    async def test_ticket_id_passed_through(self) -> None:
        """ticket_id is passed to the SingleOperationWidget."""
        app = SingleOperationTestApp(ticket_id="AMI-117")
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.ticket_id == "AMI-117"

    @pytest.mark.timeout(10)
    async def test_log_path_passed_through(self) -> None:
        """log_path is passed to the SingleOperationWidget."""
        app = SingleOperationTestApp(log_path="/tmp/test.log")
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.log_path == "/tmp/test.log"


# ===========================================================================
# Verbose mode tests
# ===========================================================================


class TestVerboseMode:
    """Tests for the verbose mode toggle."""

    @pytest.mark.timeout(10)
    async def test_v_toggles_verbose_mode(self) -> None:
        """Pressing 'v' toggles verbose_mode on the widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.verbose_mode is False

            await pilot.press("v")
            assert widget.verbose_mode is True

            await pilot.press("v")
            assert widget.verbose_mode is False


# ===========================================================================
# Quit tests
# ===========================================================================


class TestQuit:
    """Tests for the quit action."""

    @pytest.mark.timeout(10)
    async def test_q_pushes_quit_modal(self) -> None:
        """Pressing 'q' pushes the QuitConfirmModal instead of exiting."""
        from ingot.ui.screens.quit_modal import QuitConfirmModal

        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)

    @pytest.mark.timeout(10)
    async def test_q_then_y_sets_quit_requested_and_exits(self) -> None:
        """Pressing 'q' then 'y' sets quit_requested and exits."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.quit_requested is False
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert screen.quit_requested is True

    @pytest.mark.timeout(10)
    async def test_q_then_n_returns_to_screen(self) -> None:
        """Pressing 'q' then 'n' returns to SingleOperationScreen."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.quit_requested is False
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.quit_requested is False


# ===========================================================================
# Property delegation tests
# ===========================================================================


class TestPropertyDelegation:
    """Tests for property delegation to SingleOperationWidget."""

    @pytest.mark.timeout(10)
    async def test_status_message_getter(self) -> None:
        """status_message getter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            widget = screen.query_one("#single-op", SingleOperationWidget)
            widget.status_message = "Generating plan..."
            assert screen.status_message == "Generating plan..."

    @pytest.mark.timeout(10)
    async def test_status_message_setter(self) -> None:
        """status_message setter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.status_message = "Running tests..."
            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.status_message == "Running tests..."

    @pytest.mark.timeout(10)
    async def test_ticket_id_setter(self) -> None:
        """ticket_id setter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.ticket_id = "AMI-200"
            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.ticket_id == "AMI-200"

    @pytest.mark.timeout(10)
    async def test_verbose_mode_getter(self) -> None:
        """verbose_mode getter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            widget = screen.query_one("#single-op", SingleOperationWidget)
            widget.verbose_mode = True
            assert screen.verbose_mode is True

    @pytest.mark.timeout(10)
    async def test_verbose_mode_setter(self) -> None:
        """verbose_mode setter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.verbose_mode = True
            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.verbose_mode is True

    @pytest.mark.timeout(10)
    async def test_log_path_getter(self) -> None:
        """log_path getter delegates to widget."""
        app = SingleOperationTestApp(log_path="/tmp/orig.log")
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            assert screen.log_path == "/tmp/orig.log"

    @pytest.mark.timeout(10)
    async def test_log_path_setter(self) -> None:
        """log_path setter delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            screen.log_path = "/tmp/new.log"
            widget = screen.query_one("#single-op", SingleOperationWidget)
            assert widget.log_path == "/tmp/new.log"


# ===========================================================================
# Method delegation tests
# ===========================================================================


class TestMethodDelegation:
    """Tests for method delegation to SingleOperationWidget."""

    @pytest.mark.timeout(10)
    async def test_update_liveness_delegates(self) -> None:
        """update_liveness() delegates to widget."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            widget = screen.query_one("#single-op", SingleOperationWidget)
            screen.update_liveness("compiling module X")
            assert widget.latest_liveness_line == "compiling module X"

    @pytest.mark.timeout(10)
    async def test_write_log_line_delegates(self) -> None:
        """write_log_line() delegates to widget's RichLog."""
        app = SingleOperationTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = _get_screen(app)
            # Should not raise — line is written to the internal RichLog
            screen.write_log_line("some verbose output")
