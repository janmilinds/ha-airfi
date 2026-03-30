"""Test the airfi coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.api.client import AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.const import CONF_SERIAL_NUMBER, DOMAIN, RECOVERY_TRIGGER_SECONDS
from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator
from custom_components.airfi.data import AirfiData
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice
from homeassistant.const import CONF_HOST
from homeassistant.helpers.update_coordinator import UpdateFailed


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


def _build_coordinator(hass, config_entry, mock_integration) -> tuple[AirfiDataUpdateCoordinator, MagicMock]:
    """Build a coordinator and its client mock for write bridge tests."""
    client = MagicMock()
    client.async_write_holding_register = AsyncMock()
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
    return coordinator, client


@pytest.mark.unit
async def test_async_set_holding_register_delegates_to_client(hass, config_entry, mock_integration) -> None:
    """Test that write bridge calls the API client with the correct arguments."""
    coordinator, client = _build_coordinator(hass, config_entry, mock_integration)

    await coordinator.async_set_holding_register(address=1, value=3)

    client.async_write_holding_register.assert_awaited_once_with(1, 3)


@pytest.mark.unit
async def test_async_set_holding_register_re_raises_connection_error(hass, config_entry, mock_integration) -> None:
    """Test that write bridge re-raises TCP connection errors."""
    coordinator, client = _build_coordinator(hass, config_entry, mock_integration)
    client.async_write_holding_register.side_effect = AirfiApiClientConnectionError("timeout")

    with pytest.raises(AirfiApiClientConnectionError):
        await coordinator.async_set_holding_register(address=1, value=3)


@pytest.mark.unit
async def test_async_set_holding_register_re_raises_modbus_error(hass, config_entry, mock_integration) -> None:
    """Test that write bridge re-raises Modbus protocol errors.

    This covers cases such as writing an invalid value or targeting a
    register address that does not support writes.
    """
    coordinator, client = _build_coordinator(hass, config_entry, mock_integration)
    client.async_write_holding_register.side_effect = AirfiApiClientModbusError("illegal data value")

    with pytest.raises(AirfiApiClientModbusError):
        await coordinator.async_set_holding_register(address=1, value=3)


@pytest.mark.unit
async def test_async_update_data_does_not_rediscover_before_recovery_threshold(
    hass, config_entry, mock_integration
) -> None:
    """Test that the first connection failure only starts the outage timer."""
    client = MagicMock()
    client.async_get_data = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))
    client.update_host = MagicMock()

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

    with patch(
        "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
        new=AsyncMock(return_value=[]),
    ) as scan_mock:
        update_method = AirfiDataUpdateCoordinator.__dict__["_async_update_data"].__get__(
            coordinator,
            AirfiDataUpdateCoordinator,
        )
        with pytest.raises(UpdateFailed):
            await update_method()

    scan_mock.assert_not_awaited()
    client.update_host.assert_not_called()
    assert coordinator._connection_lost_at is not None  # noqa: SLF001 - Verify outage timer starts on first failure


@pytest.mark.unit
async def test_async_update_data_recovers_after_device_ip_change_once_recovery_threshold_is_exceeded(
    hass, config_entry, mock_integration
) -> None:
    """Test automatic rediscovery and host update after recovery threshold is exceeded."""
    client = MagicMock()
    client.async_get_data = AsyncMock(
        side_effect=[
            AirfiApiClientConnectionError("timeout"),
            {
                "firmware_version": "3.8.1",
                "modbus_map_version": "3.0.0",
                "holding_registers": [],
                "input_registers": [],
                "lookup_registers": [],
                "model": "Airfi",
            },
        ]
    )
    client.update_host = MagicMock()

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

    discovered_device = AirfiDiscoveredDevice(
        host="192.168.1.99",
        serial=int(config_entry.data[CONF_SERIAL_NUMBER].split("-")[-1]),
        model_id=1,
    )
    coordinator._connection_lost_at = asyncio.get_running_loop().time() - RECOVERY_TRIGGER_SECONDS - 1  # noqa: SLF001 - Seed outage timer past recovery threshold

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered_device]),
        ),
        patch.object(hass.config_entries, "async_update_entry") as update_entry_mock,
    ):
        update_method = AirfiDataUpdateCoordinator.__dict__["_async_update_data"].__get__(
            coordinator,
            AirfiDataUpdateCoordinator,
        )
        result = await update_method()

    client.update_host.assert_called_once_with("192.168.1.99")
    update_entry_mock.assert_called_once_with(
        config_entry,
        data={**config_entry.data, CONF_HOST: "192.168.1.99"},
    )
    assert result["firmware_version"] == "3.8.1"


@pytest.mark.unit
async def test_async_update_data_does_not_rediscover_on_modbus_error(hass, config_entry, mock_integration) -> None:
    """Test that Modbus protocol errors do not trigger rediscovery.

    Rediscovery is only warranted when the device is unreachable at the
    TCP level. A Modbus error means the device is reachable but the
    protocol exchange failed.
    """
    client = MagicMock()
    client.async_get_data = AsyncMock(side_effect=AirfiApiClientModbusError("bad response"))

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
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[]),
        ) as scan_mock,
        patch(
            "custom_components.airfi.coordinator.base.should_try_rediscovery",
            return_value=False,
        ),
    ):
        update_method = AirfiDataUpdateCoordinator.__dict__["_async_update_data"].__get__(
            coordinator,
            AirfiDataUpdateCoordinator,
        )
        with pytest.raises(UpdateFailed):
            await update_method()

    scan_mock.assert_not_awaited()
