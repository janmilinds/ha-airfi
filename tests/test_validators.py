"""Test connection validators for Airfi config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.airfi_home.api import AirfiApiClientConnectionError
from custom_components.airfi_home.config_flow_handler.validators.connection import validate_connection
from custom_components.airfi_home.coordinator.feature_manager import InvalidDeviceDataError, UnsupportedFirmwareError


@pytest.mark.unit
async def test_validate_connection_success(hass) -> None:
    """Test that validate_connection passes when device is reachable."""
    with patch(
        "custom_components.airfi_home.config_flow_handler.validators.connection.AirfiApiClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_lookup_registers = AsyncMock(return_value=[100, 310, 270])

        await validate_connection(hass, host="192.168.1.10")

    mock_client.async_get_lookup_registers.assert_awaited_once()


@pytest.mark.unit
async def test_validate_connection_raises_on_failure(hass) -> None:
    """Test that validate_connection raises when device is unreachable."""
    with patch(
        "custom_components.airfi_home.config_flow_handler.validators.connection.AirfiApiClient"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_lookup_registers = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))

        with pytest.raises(AirfiApiClientConnectionError):
            await validate_connection(hass, host="192.168.1.10")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("lookup", "error"),
    [
        pytest.param([100, 381, 150], UnsupportedFirmwareError, id="register-map-1.5"),
        pytest.param([100, 320, 300], UnsupportedFirmwareError, id="blocklisted-firmware"),
        pytest.param([100, 381], InvalidDeviceDataError, id="incomplete-version-registers"),
        pytest.param([0, 0, 0], InvalidDeviceDataError, id="no-version-at-all"),
        pytest.param([0, 38, 15], UnsupportedFirmwareError, id="two-digit-map-1.5"),
    ],
)
async def test_validate_connection_refuses_a_unit_it_cannot_support(
    hass, lookup: list[int], error: type[Exception]
) -> None:
    """A unit that answers but whose software is not supported, or reports no versions, is refused."""
    with patch(
        "custom_components.airfi_home.config_flow_handler.validators.connection.AirfiApiClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_get_lookup_registers = AsyncMock(return_value=lookup)

        with pytest.raises(error):
            await validate_connection(hass, host="192.168.1.10")


@pytest.mark.unit
async def test_validate_connection_asks_once_with_the_given_modbus_id(hass) -> None:
    """The check is sent once, to the ID asked for, so a unit that ignores it is reported within one timeout."""
    with patch(
        "custom_components.airfi_home.config_flow_handler.validators.connection.AirfiApiClient"
    ) as mock_client_cls:
        mock_client_cls.return_value.async_get_lookup_registers = AsyncMock(return_value=[100, 310, 270])

        await validate_connection(hass, host="192.168.1.10", unit_id=5)

    mock_client_cls.assert_called_once_with(host="192.168.1.10", port=502, unit_id=5, retries=0)
