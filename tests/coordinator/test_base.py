"""Test the airfi coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.api.client import AirfiApiClientConnectionError, AirfiApiClientModbusError
from custom_components.airfi.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
    ISSUE_DEVICE_UNREACHABLE,
    RECOVERY_ISSUE_SECONDS,
    RECOVERY_TRIGGER_SECONDS,
)
from custom_components.airfi.coordinator import AirfiDataUpdateCoordinator
from custom_components.airfi.coordinator.base import RecoveryState
from custom_components.airfi.data import AirfiData
from custom_components.airfi.utils.discovery import AirfiDiscoveredDevice
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(
    hass, config_entry, mock_integration, *, client: MagicMock | None = None
) -> tuple[AirfiDataUpdateCoordinator, MagicMock]:
    """Construct a coordinator with an attached mock client."""
    if client is None:
        client = MagicMock()
        client.async_get_data = AsyncMock()
        client.async_get_lookup_registers = AsyncMock()
        client.async_write_holding_register = AsyncMock()
        client.update_host = MagicMock()
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
    return coordinator, client


async def _call_setup(coordinator: AirfiDataUpdateCoordinator) -> None:
    """Call the coordinator's _async_setup directly."""
    setup = AirfiDataUpdateCoordinator.__dict__["_async_setup"].__get__(coordinator, AirfiDataUpdateCoordinator)
    await setup()


async def _call_update(coordinator: AirfiDataUpdateCoordinator):
    """Call the coordinator's _async_update_data directly."""
    update = AirfiDataUpdateCoordinator.__dict__["_async_update_data"].__get__(coordinator, AirfiDataUpdateCoordinator)
    return await update()


# ---------------------------------------------------------------------------
# _async_setup — error paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_setup_raises_config_entry_not_ready_on_api_error(hass, config_entry, mock_integration) -> None:
    """Test that _async_setup raises ConfigEntryNotReady when lookup fails and rediscovery fails."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_lookup_registers = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[]),
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await _call_setup(coordinator)


@pytest.mark.unit
async def test_async_setup_rediscovers_on_connection_error(hass, config_entry, mock_integration) -> None:
    """Test that _async_setup tries rediscovery on connection error and retries lookup."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    # First call fails, second succeeds after rediscovery
    client.async_get_lookup_registers = AsyncMock(side_effect=[AirfiApiClientConnectionError("timeout"), [0, 381, 300]])

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=12345, model_id=1)

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered]),
        ),
        patch.object(hass.config_entries, "async_update_entry"),
        patch.object(coordinator.feature_manager, "initialize"),
        patch.object(coordinator.feature_manager, "get_register_lengths", return_value=(42, 59)),
    ):
        coordinator.feature_manager.firmware_version = "3.8.1"
        coordinator.feature_manager.modbus_map_version = "3.0.0"
        await _call_setup(coordinator)

    assert client.async_get_lookup_registers.await_count == 2


@pytest.mark.unit
async def test_async_setup_rediscovery_succeeds_but_retry_fails(hass, config_entry, mock_integration) -> None:
    """Test that _async_setup raises ConfigEntryNotReady when retry after rediscovery also fails."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_lookup_registers = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=12345, model_id=1)

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered]),
        ),
        patch.object(hass.config_entries, "async_update_entry"),
        pytest.raises(ConfigEntryNotReady),
    ):
        await _call_setup(coordinator)


@pytest.mark.unit
async def test_async_setup_feature_manager_validation_error(hass, config_entry, mock_integration) -> None:
    """Test that _async_setup raises ConfigEntryNotReady on feature validation failure."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_lookup_registers = AsyncMock(return_value=[0, 381, 300])

    with (
        patch.object(coordinator.feature_manager, "initialize", side_effect=ValueError("bad firmware")),
        pytest.raises(ConfigEntryNotReady, match="bad firmware"),
    ):
        await _call_setup(coordinator)


@pytest.mark.unit
async def test_async_setup_modbus_error_does_not_trigger_rediscovery(hass, config_entry, mock_integration) -> None:
    """Test that a Modbus protocol error in setup does not attempt rediscovery."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_lookup_registers = AsyncMock(side_effect=AirfiApiClientModbusError("bad response"))

    with pytest.raises(ConfigEntryNotReady):
        await _call_setup(coordinator)


# ---------------------------------------------------------------------------
# _async_update_data — recovery retry failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_update_data_recovery_retry_fails_with_connection_error(
    hass, config_entry, mock_integration
) -> None:
    """Test UpdateFailed is raised with rediscovery key when post-recovery fetch fails."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_data = AsyncMock(side_effect=AirfiApiClientConnectionError("timeout"))

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=12345, model_id=1)
    coordinator._connection_lost_at = asyncio.get_running_loop().time() - RECOVERY_TRIGGER_SECONDS - 1  # noqa: SLF001

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered]),
        ),
        patch.object(hass.config_entries, "async_update_entry"),
        pytest.raises(UpdateFailed),
    ):
        await _call_update(coordinator)


@pytest.mark.unit
async def test_async_update_data_recovery_retry_fails_with_modbus_error(hass, config_entry, mock_integration) -> None:
    """Test UpdateFailed when post-recovery fetch returns Modbus error."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_data = AsyncMock(
        side_effect=[
            AirfiApiClientConnectionError("timeout"),
            AirfiApiClientModbusError("bad register"),
        ]
    )

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=12345, model_id=1)
    coordinator._connection_lost_at = asyncio.get_running_loop().time() - RECOVERY_TRIGGER_SECONDS - 1  # noqa: SLF001

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered]),
        ),
        patch.object(hass.config_entries, "async_update_entry"),
        pytest.raises(UpdateFailed),
    ):
        await _call_update(coordinator)


@pytest.mark.unit
async def test_async_update_data_success_restores_connection(hass, config_entry, mock_integration) -> None:
    """Test that a successful data fetch resets recovery state."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    client.async_get_data = AsyncMock(
        return_value={
            "firmware_version": "3.8.1",
            "modbus_map_version": "3.0.0",
            "holding_registers": [],
            "input_registers": [],
            "lookup_registers": [],
            "model": "Airfi",
        }
    )

    coordinator._connection_lost_at = asyncio.get_running_loop().time() - 100  # noqa: SLF001
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    result = await _call_update(coordinator)
    assert result["firmware_version"] == "3.8.1"
    assert coordinator._connection_lost_at is None  # noqa: SLF001
    assert coordinator._recovery_state == RecoveryState.IDLE  # noqa: SLF001


# ---------------------------------------------------------------------------
# _async_on_connection_lost — thresholds
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_connection_lost_triggers_recovery_after_threshold(hass, config_entry, mock_integration) -> None:
    """Test that recovery mode activates after RECOVERY_TRIGGER_SECONDS."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    loop = asyncio.get_running_loop()
    coordinator._connection_lost_at = loop.time() - RECOVERY_TRIGGER_SECONDS - 1  # noqa: SLF001

    coordinator._async_on_connection_lost()  # noqa: SLF001

    assert coordinator._recovery_state == RecoveryState.RECOVERING  # noqa: SLF001


@pytest.mark.unit
async def test_connection_lost_raises_issue_after_issue_threshold(hass, config_entry, mock_integration) -> None:
    """Test that a repair issue is created after RECOVERY_ISSUE_SECONDS."""
    config_entry.add_to_hass(hass)
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    loop = asyncio.get_running_loop()
    coordinator._connection_lost_at = loop.time() - RECOVERY_ISSUE_SECONDS - 1  # noqa: SLF001
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    coordinator._async_on_connection_lost()  # noqa: SLF001

    assert coordinator._issue_raised is True  # noqa: SLF001
    issue_reg = ir.async_get(hass)
    expected_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"
    issue = issue_reg.async_get_issue(DOMAIN, expected_id)
    assert issue is not None


# ---------------------------------------------------------------------------
# _async_on_connection_restored
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_connection_restored_resets_state(hass, config_entry, mock_integration) -> None:
    """Test that connection restored resets all recovery fields."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._connection_lost_at = asyncio.get_running_loop().time() - 100  # noqa: SLF001
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    coordinator._async_on_connection_restored()  # noqa: SLF001

    assert coordinator._connection_lost_at is None  # noqa: SLF001
    assert coordinator._recovery_state == RecoveryState.IDLE  # noqa: SLF001


@pytest.mark.unit
async def test_connection_restored_deletes_issue(hass, config_entry, mock_integration) -> None:
    """Test that connection restored deletes the repair issue."""
    config_entry.add_to_hass(hass)
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._connection_lost_at = asyncio.get_running_loop().time() - 100  # noqa: SLF001
    coordinator._issue_raised = True  # noqa: SLF001

    issue_id = f"{ISSUE_DEVICE_UNREACHABLE}_{config_entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DEVICE_UNREACHABLE,
    )

    coordinator._async_on_connection_restored()  # noqa: SLF001

    assert coordinator._issue_raised is False  # noqa: SLF001
    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.unit
async def test_connection_restored_noop_when_idle(hass, config_entry, mock_integration) -> None:
    """Test that connection restored is a no-op when already idle."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)

    coordinator._async_on_connection_restored()  # noqa: SLF001

    assert coordinator._connection_lost_at is None  # noqa: SLF001
    assert coordinator._recovery_state == RecoveryState.IDLE  # noqa: SLF001


# ---------------------------------------------------------------------------
# _async_try_recover_host — edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_recover_host_returns_false_when_not_recovering(hass, config_entry, mock_integration) -> None:
    """Test that recover_host is a no-op when not in recovery state."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    assert coordinator._recovery_state == RecoveryState.IDLE  # noqa: SLF001

    result = await coordinator._async_try_recover_host()  # noqa: SLF001
    assert result is False


@pytest.mark.unit
async def test_recover_host_returns_false_when_no_serial(hass, config_entry, mock_integration) -> None:
    """Test that recover_host returns False when serial is not in config."""
    config_entry.add_to_hass(hass)
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    hass.config_entries.async_update_entry(config_entry, data={CONF_HOST: "192.168.1.10"})

    result = await coordinator._async_try_recover_host()  # noqa: SLF001
    assert result is False


@pytest.mark.unit
async def test_recover_host_respects_cooldown(hass, config_entry, mock_integration) -> None:
    """Test that recover_host skips when cooldown has not elapsed."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001
    coordinator._last_rediscovery_attempt = asyncio.get_running_loop().time()  # noqa: SLF001

    result = await coordinator._async_try_recover_host()  # noqa: SLF001
    assert result is False


@pytest.mark.unit
async def test_recover_host_returns_false_same_ip(hass, config_entry, mock_integration) -> None:
    """Test that recover_host returns False when discovered IP matches current."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    discovered = AirfiDiscoveredDevice(host="192.168.1.10", serial=12345, model_id=1)

    with patch(
        "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
        new=AsyncMock(return_value=[discovered]),
    ):
        result = await coordinator._async_try_recover_host()  # noqa: SLF001

    assert result is False


@pytest.mark.unit
async def test_recover_host_returns_false_no_match(hass, config_entry, mock_integration) -> None:
    """Test that recover_host returns False when no matching serial found."""
    coordinator, _ = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=99999, model_id=1)

    with patch(
        "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
        new=AsyncMock(return_value=[discovered]),
    ):
        result = await coordinator._async_try_recover_host()  # noqa: SLF001

    assert result is False


@pytest.mark.unit
async def test_recover_host_matches_numeric_serial(hass, config_entry, mock_integration) -> None:
    """Test that recover_host matches numeric serial digits from 'AIRFI-12345'."""
    coordinator, client = _make_coordinator(hass, config_entry, mock_integration)
    coordinator._recovery_state = RecoveryState.RECOVERING  # noqa: SLF001

    discovered = AirfiDiscoveredDevice(host="192.168.1.99", serial=12345, model_id=1)

    with (
        patch(
            "custom_components.airfi.coordinator.base.AirfiDiscoveryService.async_scan",
            new=AsyncMock(return_value=[discovered]),
        ),
        patch.object(hass.config_entries, "async_update_entry"),
    ):
        result = await coordinator._async_try_recover_host()  # noqa: SLF001

    assert result is True
    client.update_host.assert_called_once_with("192.168.1.99")
