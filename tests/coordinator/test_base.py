"""Test the Airfi coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.const import DOMAIN
from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator
from custom_components.airfi.data import AirfiData


@pytest.mark.unit
async def test_async_setup_uses_serial_number_and_caches_profile(hass, config_entry, mock_integration) -> None:
    """Test that coordinator setup uses serial_number and caches register lengths."""
    client = MagicMock()
    client.async_get_lookup_registers = AsyncMock(return_value=[0, 381, 300])
    client.async_get_data = AsyncMock(return_value={"input_registers": [], "holding_registers": []})
    client.set_register_profile = MagicMock()

    coordinator = AirfiDataUpdateCoordinator(
        hass=hass,
        logger=MagicMock(),
        name=DOMAIN,
        config_entry=config_entry,
        update_interval=None,
        always_update=False,
    )
    config_entry.runtime_data = AirfiData(
        client=client,
        coordinator=coordinator,
        integration=mock_integration,
    )

    with (
        patch.object(coordinator.feature_manager, "initialize") as initialize_mock,
        patch.object(coordinator.feature_manager, "get_register_lengths", return_value=(42, 59)),
    ):
        coordinator.feature_manager.firmware_version = "3.8.1"
        coordinator.feature_manager.modbus_map_version = "3.0.0"
        setup_method = AirfiDataUpdateCoordinator.__dict__["_async_setup"].__get__(
            coordinator,
            AirfiDataUpdateCoordinator,
        )
        await setup_method()

    initialize_mock.assert_called_once_with("Airfi AIRFI-12345", [0, 381, 300])
    client.set_register_profile.assert_called_once_with(
        firmware_version="3.8.1",
        modbus_map_version="3.0.0",
        input_register_length=42,
        holding_register_length=59,
    )
