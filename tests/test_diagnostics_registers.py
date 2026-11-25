"""Test the raw register values in the Airfi diagnostics."""

from types import SimpleNamespace

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant
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
    assert len(sample["input_registers"]) == 42
    assert len(sample["holding_registers"]) == 59
