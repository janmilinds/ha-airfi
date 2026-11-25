"""Shared fixtures for Airfi tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi.api import AirfiApiClient
from custom_components.airfi.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

# A unit on firmware 3.1.0 with Modbus register map 2.7.0, which supports every feature.
LOOKUP_REGISTERS = [100, 310, 270]
INPUT_REGISTER_COUNT = 42
HOLDING_REGISTER_COUNT = 59


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry for Airfi."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_SERIAL_NUMBER: "AIRFI-12345",
        },
        unique_id="airfi-12345",
        title="Airfi AIRFI-12345",
    )


@pytest.fixture
def mock_api() -> Generator[SimpleNamespace]:
    """Patch the client's reads with a unit that answers with every register."""
    data = {
        "firmware_version": "3.1.0",
        "modbus_register_version": "2.7.0",
        "input_registers": [*LOOKUP_REGISTERS, *[0] * (INPUT_REGISTER_COUNT - len(LOOKUP_REGISTERS))],
        "holding_registers": [0] * HOLDING_REGISTER_COUNT,
        "lookup_registers": [],
        "model": "Airfi",
    }
    with (
        patch.object(
            AirfiApiClient, "async_get_lookup_registers", AsyncMock(return_value=LOOKUP_REGISTERS)
        ) as get_lookup_registers,
        patch.object(AirfiApiClient, "async_get_data", AsyncMock(return_value=data)) as get_data,
    ):
        yield SimpleNamespace(get_lookup_registers=get_lookup_registers, get_data=get_data)


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """
    Set up the integration from a config entry.

    Returns:
        The config entry, now loaded.

    """
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_integration() -> MagicMock:
    """Create a mock integration object for runtime data."""
    return MagicMock()
