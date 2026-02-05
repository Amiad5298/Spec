"""Unit tests for create_ticket_service_from_config() DI helper.

Tests the dependency injection helper at spec/cli.py:224-267 which
centralizes backend resolution, factory creation, and auth wiring.

Mocking boundaries:
- spec.config.backend_resolver.resolve_backend_platform (lazy import)
- spec.integrations.backends.factory.BackendFactory (lazy import)
- spec.cli.AuthenticationManager (module-level import)
- spec.cli.create_ticket_service (module-level import)

Patch paths follow the convention established in tests/test_cli.py:
lazy imports are patched at their origin module.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spec.config.fetch_config import AgentPlatform
from spec.integrations.backends.errors import (
    BackendNotConfiguredError,
    BackendNotInstalledError,
)
from spec.integrations.ticket_service import TicketService


class TestCreateTicketServiceFromConfig:
    """Unit tests for create_ticket_service_from_config()."""

    @pytest.mark.asyncio
    async def test_resolves_backend_from_config(self):
        """Verifies resolve_backend_platform called with (config_manager, None)."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE
        mock_backend = MagicMock()
        mock_service = MagicMock(spec=TicketService)

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ) as mock_resolve,
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
            patch(
                "spec.cli.AuthenticationManager",
                return_value=MagicMock(),
            ),
            patch(
                "spec.cli.create_ticket_service",
                new_callable=AsyncMock,
                return_value=mock_service,
            ),
        ):
            mock_factory_class.create.return_value = mock_backend

            await create_ticket_service_from_config(config_manager=mock_config)

            mock_resolve.assert_called_once_with(mock_config, None)

    @pytest.mark.asyncio
    async def test_resolves_backend_from_cli_override(self):
        """Verifies CLI override 'auggie' passed to resolver."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE
        mock_backend = MagicMock()
        mock_service = MagicMock(spec=TicketService)

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ) as mock_resolve,
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
            patch(
                "spec.cli.AuthenticationManager",
                return_value=MagicMock(),
            ),
            patch(
                "spec.cli.create_ticket_service",
                new_callable=AsyncMock,
                return_value=mock_service,
            ),
        ):
            mock_factory_class.create.return_value = mock_backend

            await create_ticket_service_from_config(
                config_manager=mock_config,
                cli_backend_override="auggie",
            )

            mock_resolve.assert_called_once_with(mock_config, "auggie")

    @pytest.mark.asyncio
    async def test_creates_auth_manager_when_not_provided(self):
        """Verifies AuthenticationManager(config_manager) created when auth_manager is None."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE
        mock_backend = MagicMock()
        mock_service = MagicMock(spec=TicketService)
        mock_auth = MagicMock()

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ),
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
            patch(
                "spec.cli.AuthenticationManager",
                return_value=mock_auth,
            ) as mock_auth_class,
            patch(
                "spec.cli.create_ticket_service",
                new_callable=AsyncMock,
                return_value=mock_service,
            ),
        ):
            mock_factory_class.create.return_value = mock_backend

            await create_ticket_service_from_config(config_manager=mock_config)

            mock_auth_class.assert_called_once_with(mock_config)

    @pytest.mark.asyncio
    async def test_uses_provided_auth_manager(self):
        """Verifies provided auth_manager passed through, AuthenticationManager not called."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE
        mock_backend = MagicMock()
        mock_service = MagicMock(spec=TicketService)
        provided_auth = MagicMock()

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ),
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
            patch(
                "spec.cli.AuthenticationManager",
            ) as mock_auth_class,
            patch(
                "spec.cli.create_ticket_service",
                new_callable=AsyncMock,
                return_value=mock_service,
            ) as mock_create,
        ):
            mock_factory_class.create.return_value = mock_backend

            await create_ticket_service_from_config(
                config_manager=mock_config,
                auth_manager=provided_auth,
            )

            mock_auth_class.assert_not_called()
            # Verify the provided auth_manager was passed to create_ticket_service
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["auth_manager"] is provided_auth

    @pytest.mark.asyncio
    async def test_returns_service_and_backend_tuple(self):
        """Verifies return type is (TicketService, AIBackend)."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE
        mock_backend = MagicMock()
        mock_service = MagicMock(spec=TicketService)

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ),
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
            patch(
                "spec.cli.AuthenticationManager",
                return_value=MagicMock(),
            ),
            patch(
                "spec.cli.create_ticket_service",
                new_callable=AsyncMock,
                return_value=mock_service,
            ),
        ):
            mock_factory_class.create.return_value = mock_backend

            result = await create_ticket_service_from_config(
                config_manager=mock_config,
            )

            assert isinstance(result, tuple)
            assert len(result) == 2
            service, backend = result
            assert service is mock_service
            assert backend is mock_backend

    @pytest.mark.asyncio
    async def test_raises_backend_not_configured_error(self):
        """resolve_backend_platform raises BackendNotConfiguredError → propagates."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()

        with patch(
            "spec.config.backend_resolver.resolve_backend_platform",
            side_effect=BackendNotConfiguredError("No AI backend configured. Run 'spec init'."),
        ):
            with pytest.raises(BackendNotConfiguredError, match="spec init"):
                await create_ticket_service_from_config(config_manager=mock_config)

    @pytest.mark.asyncio
    async def test_raises_backend_not_installed_error(self):
        """BackendFactory.create raises BackendNotInstalledError → propagates."""
        from spec.cli import create_ticket_service_from_config

        mock_config = MagicMock()
        mock_platform = AgentPlatform.AUGGIE

        with (
            patch(
                "spec.config.backend_resolver.resolve_backend_platform",
                return_value=mock_platform,
            ),
            patch(
                "spec.integrations.backends.factory.BackendFactory",
            ) as mock_factory_class,
        ):
            mock_factory_class.create.side_effect = BackendNotInstalledError(
                "Auggie CLI is not installed"
            )

            with pytest.raises(BackendNotInstalledError, match="not installed"):
                await create_ticket_service_from_config(config_manager=mock_config)
