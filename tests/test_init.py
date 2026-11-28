"""Tests for the Airfi integration __init__.py."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.airfi_home import async_reload_entry, async_setup, async_setup_entry, async_unload_entry

# Force coverage of re-export shim
import custom_components.airfi_home.config_flow  # noqa: F401
from custom_components.airfi_home.const import CONF_MODBUS_ID, CONF_SERIAL_NUMBER, DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.fixture
def entry(hass) -> MockConfigEntry:
    """Create and register a config entry for setUp tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_SERIAL_NUMBER: "AIRFI-12345",
        },
        unique_id="airfi-12345",
        title="Airfi AIRFI-12345",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.mark.unit
async def test_async_setup_returns_true(hass) -> None:
    """Test that async_setup returns True (config-entry-only integration)."""
    result = await async_setup(hass, {})
    assert result is True


@pytest.mark.unit
async def test_async_setup_entry_creates_runtime_data(hass, entry) -> None:
    """Test that async_setup_entry initialises client, coordinator and platforms."""
    with (
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_initial_setup",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch("custom_components.airfi_home.async_get_loaded_integration", return_value=MagicMock()),
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()) as fwd,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None
    assert entry.runtime_data.client is not None
    assert entry.runtime_data.coordinator is not None
    fwd.assert_awaited_once()


@pytest.mark.unit
async def test_async_unload_entry_unloads_platforms(hass, entry) -> None:
    """Test that async_unload_entry delegates to async_unload_platforms."""
    with (
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_initial_setup",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch("custom_components.airfi_home.async_get_loaded_integration", return_value=MagicMock()),
        patch.object(hass.config_entries, "async_forward_entry_setups", new=AsyncMock()),
    ):
        await async_setup_entry(hass, entry)

    with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)) as unload_mock:
        result = await async_unload_entry(hass, entry)

    assert result is True
    unload_mock.assert_awaited_once()


@pytest.mark.unit
async def test_async_reload_entry_calls_reload(hass, entry) -> None:
    """Test that async_reload_entry delegates to config_entries.async_reload."""
    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload_mock:
        await async_reload_entry(hass, entry)

    reload_mock.assert_awaited_once_with(entry.entry_id)


@pytest.mark.unit
async def test_async_setup_entry_raises_on_first_refresh_failure(hass, entry) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady when first refresh fails."""
    with (
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_initial_setup",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.airfi_home.AirfiDataUpdateCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(side_effect=ConfigEntryNotReady()),
        ),
        patch("custom_components.airfi_home.async_get_loaded_integration", return_value=MagicMock()),
        pytest.raises(ConfigEntryNotReady) as exc,
    ):
        await async_setup_entry(hass, entry)

    assert getattr(exc.value, "translation_key", None) == "first_refresh_failed"


@pytest.mark.integration
async def test_unit_is_polled_at_the_fixed_interval(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api: SimpleNamespace,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The unit is read again each time the fixed update interval has passed."""
    reads = mock_api.get_data.await_count

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_api.get_data.await_count == reads + 1


@pytest.mark.unit
async def test_entry_has_no_options(init_integration: MockConfigEntry) -> None:
    """The entry offers no options dialog, since the update interval is fixed."""
    assert not init_integration.supports_options


@pytest.mark.integration
async def test_unit_is_read_with_the_stored_modbus_id(
    hass: HomeAssistant, modbus_unit: SimpleNamespace, config_entry: MockConfigEntry
) -> None:
    """An entry that stores a Modbus ID sends every request to it."""
    modbus_unit.modbus_id = 5
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(config_entry, data={**config_entry.data, CONF_MODBUS_ID: 5})
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert {call.kwargs["device_id"] for call in modbus_unit.connection.read_input_registers.call_args_list} == {5}
