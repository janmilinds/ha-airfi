"""Test diagnostics for Airfi."""

import json
from types import SimpleNamespace

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from custom_components.airfi.api import AirfiApiClientModbusError
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN, SERVICE_UPDATE_ENTITY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


@pytest.mark.integration
async def test_diagnostics_key_each_register_by_its_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> None:
    """Each raw register value appears under its own Modbus address, counted from 1."""
    data = mock_api.get_data.return_value
    data["input_registers"] = list(range(101, 101 + len(data["input_registers"])))
    data["holding_registers"] = list(range(201, 201 + len(data["holding_registers"])))
    assert await async_setup_component(hass, "diagnostics", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    sample = result["data_sample"]
    assert sample["input_registers"]["3x00001"] == 101
    assert sample["input_registers"]["3x00042"] == 142
    assert sample["holding_registers"]["4x00001"] == 201
    assert sample["holding_registers"]["4x00059"] == 259


@pytest.mark.integration
async def test_diagnostics_never_show_the_host(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """The unit's address appears nowhere in the integration's diagnostics, not only under the entry data."""
    assert await async_setup_component(hass, "diagnostics", {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert init_integration.data[CONF_HOST] not in json.dumps(result)


@pytest.mark.integration
async def test_diagnostics_report_the_last_failed_poll(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_api: SimpleNamespace,
    init_integration: MockConfigEntry,
) -> None:
    """After a poll fails, the download names the error that stopped it."""
    assert await async_setup_component(hass, "diagnostics", {})
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    mock_api.get_data.side_effect = AirfiApiClientModbusError("illegal")
    entity_id = next(
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
        if not entity.disabled
    )

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result["coordinator"]["last_update_success"] is False
    assert result["error"]["last_exception_type"] == "UpdateFailed"
    assert result["error"]["last_exception"] == "Failed to update data from the device"


@pytest.mark.integration
async def test_diagnostics_while_setup_retries(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> None:
    """Before the first poll succeeds, the download still opens and holds no data sample."""
    mock_api.get_data.side_effect = AirfiApiClientModbusError("illegal")
    assert await async_setup_component(hass, "diagnostics", {})
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result["data_sample"] == {}
    assert result["coordinator"]["data_keys"] is None
    assert result["error"]["last_exception_type"] == "UpdateFailed"


@pytest.mark.integration
async def test_diagnostics_download(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """The downloaded diagnostics stay as recorded, so any new field shows up in review."""
    assert await async_setup_component(hass, "diagnostics", {})

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert result == snapshot(exclude=paths("entry.entry_id", "devices.0.id", "integration.version"))
