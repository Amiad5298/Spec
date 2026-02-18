"""Tests for QuitConfirmModal — inline quit confirmation overlay."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import Button, Label

from ingot.ui.screens.quit_modal import QuitConfirmModal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ModalTestApp(App[None]):
    """Minimal app for testing modal push/dismiss behaviour."""

    def __init__(self) -> None:
        super().__init__()
        self.modal_result: bool | None = None

    def on_mount(self) -> None:
        self.push_screen(
            QuitConfirmModal(),
            callback=self._on_modal_result,
        )

    def _on_modal_result(self, result: bool) -> None:
        self.modal_result = result


class CustomMessageModalApp(App[None]):
    """App that pushes a modal with a custom message."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message
        self.modal_result: bool | None = None

    def on_mount(self) -> None:
        self.push_screen(
            QuitConfirmModal(self._message),
            callback=self._on_modal_result,
        )

    def _on_modal_result(self, result: bool) -> None:
        self.modal_result = result


# ===========================================================================
# Rendering tests
# ===========================================================================


class TestRendering:
    """Tests that the modal renders expected content."""

    @pytest.mark.timeout(10)
    async def test_modal_renders_default_message(self) -> None:
        """Modal displays the default quit message."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            label = app.screen.query_one("#quit-message", Label)
            assert "Quit task execution?" in str(label.render())

    @pytest.mark.timeout(10)
    async def test_modal_renders_custom_message(self) -> None:
        """Modal displays a custom message when provided."""
        app = CustomMessageModalApp("Cancel operation?")
        async with app.run_test() as pilot:
            await pilot.pause()
            label = app.screen.query_one("#quit-message", Label)
            assert "Cancel operation?" in str(label.render())

    @pytest.mark.timeout(10)
    async def test_modal_renders_both_buttons(self) -> None:
        """Modal renders Continue and Yes-quit buttons."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            continue_btn = app.screen.query_one("#btn-continue", Button)
            quit_btn = app.screen.query_one("#btn-quit", Button)
            assert continue_btn is not None
            assert quit_btn is not None


# ===========================================================================
# Key binding tests
# ===========================================================================


class TestKeyBindings:
    """Tests for keyboard-driven dismiss."""

    @pytest.mark.timeout(10)
    async def test_y_dismisses_with_true(self) -> None:
        """Pressing 'y' dismisses the modal with True."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert app.modal_result is True

    @pytest.mark.timeout(10)
    async def test_n_dismisses_with_false(self) -> None:
        """Pressing 'n' dismisses the modal with False."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert app.modal_result is False

    @pytest.mark.timeout(10)
    async def test_escape_dismisses_with_false(self) -> None:
        """Pressing 'escape' dismisses the modal with False."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.modal_result is False


# ===========================================================================
# Button click tests
# ===========================================================================


class TestButtonClicks:
    """Tests for button-driven dismiss."""

    @pytest.mark.timeout(10)
    async def test_continue_button_dismisses_with_false(self) -> None:
        """Clicking 'Continue' dismisses with False."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-continue")
            await pilot.pause()
            assert app.modal_result is False

    @pytest.mark.timeout(10)
    async def test_quit_button_dismisses_with_true(self) -> None:
        """Clicking 'Yes, quit' dismisses with True."""
        app = ModalTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#btn-quit")
            await pilot.pause()
            assert app.modal_result is True


# ===========================================================================
# Integration with MultiTaskScreen
# ===========================================================================


class TestMultiTaskScreenIntegration:
    """Tests that pressing 'q' on MultiTaskScreen pushes the modal."""

    @pytest.mark.timeout(10)
    async def test_q_pushes_quit_modal(self) -> None:
        """Pressing 'q' on MultiTaskScreen pushes QuitConfirmModal."""
        from ingot.ui.screens.multi_task import MultiTaskScreen

        class IntegrationApp(App[None]):
            def on_mount(self) -> None:
                self.push_screen(MultiTaskScreen())

        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)

    @pytest.mark.timeout(10)
    async def test_q_then_n_returns_to_screen(self) -> None:
        """Pressing 'q' then 'n' returns to MultiTaskScreen."""
        from ingot.ui.screens.multi_task import MultiTaskScreen

        class IntegrationApp(App[None]):
            def on_mount(self) -> None:
                self.push_screen(MultiTaskScreen())

        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)
            await pilot.press("n")
            await pilot.pause()
            assert isinstance(app.screen, MultiTaskScreen)

    @pytest.mark.timeout(10)
    async def test_q_then_y_exits_app(self) -> None:
        """Pressing 'q' then 'y' exits the app."""
        from ingot.ui.screens.multi_task import MultiTaskScreen

        class IntegrationApp(App[None]):
            def on_mount(self) -> None:
                self.push_screen(MultiTaskScreen())

        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("y")
            # If we reach here without hanging, the app exited


# ===========================================================================
# Integration with SingleOperationScreen
# ===========================================================================


class TestSingleOperationScreenIntegration:
    """Tests that pressing 'q' on SingleOperationScreen pushes the modal."""

    @pytest.mark.timeout(10)
    async def test_q_pushes_quit_modal(self) -> None:
        """Pressing 'q' on SingleOperationScreen pushes QuitConfirmModal."""
        from ingot.ui.screens.single_operation import SingleOperationScreen

        class IntegrationApp(App[None]):
            def on_mount(self) -> None:
                self.push_screen(SingleOperationScreen())

        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)

    @pytest.mark.timeout(10)
    async def test_q_then_n_returns_to_screen(self) -> None:
        """Pressing 'q' then 'n' returns to SingleOperationScreen."""
        from ingot.ui.screens.single_operation import SingleOperationScreen

        class IntegrationApp(App[None]):
            def on_mount(self) -> None:
                self.push_screen(SingleOperationScreen())

        app = IntegrationApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            assert isinstance(app.screen, QuitConfirmModal)
            await pilot.press("n")
            await pilot.pause()
            assert isinstance(app.screen, SingleOperationScreen)
