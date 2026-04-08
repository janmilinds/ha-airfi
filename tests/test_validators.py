"""Test connection validators for Airfi config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.airfi.api import AirfiApiClientConnectionError
from custom_components.airfi.config_flow_handler.validators.connection import validate_connection


@pytest.mark.unit
async def test_validate_connection_success(hass) -> None:
    """Test that validate_connection passes when device is reachable."""
    with patch("custom_components.airfi.config_flow_handler.validators.connection.AirfiApiClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_test_connection = AsyncMock(return_value=None)

        await validate_connection(hass, host="192.168.1.10")

    mock_client.async_test_connection.assert_awaited_once()


@pytest.mark.unit
async def test_validate_connection_raises_on_failure(hass) -> None:
    """Test that validate_connection raises when device is unreachable."""
    with patch("custom_components.airfi.config_flow_handler.validators.connection.AirfiApiClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_test_connection = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))

        with pytest.raises(AirfiApiClientConnectionError):
            await validate_connection(hass, host="192.168.1.10")
