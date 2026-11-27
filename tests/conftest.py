"""Shared fixtures for Airfi tests."""

from collections.abc import Callable, Generator
import logging
import socket
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.api import AirfiApiClient
from custom_components.airfi_home.const import (
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DISCOVERY_DEVICE_PORT,
    DISCOVERY_MULTICAST_PORT,
    DOMAIN,
)
from custom_components.airfi_home.utils.discovery import DATA_DISCOVERY_LISTENER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

# A unit on firmware 3.1.0 with Modbus register map 2.7.0, which supports every feature.
LOOKUP_REGISTERS = [100, 310, 270]
INPUT_REGISTER_COUNT = 42
HOLDING_REGISTER_COUNT = 59


@pytest.fixture(autouse=True)
def fail_on_deprecation_report(caplog: pytest.LogCaptureFixture) -> Generator[None]:
    """Fail a test when Home Assistant logs a deprecation this integration caused."""
    yield
    reports = [
        message
        for when in ("setup", "call", "teardown")
        for record in caplog.get_records(when)
        if record.levelno >= logging.WARNING
        and DOMAIN in (message := record.getMessage())
        and message.startswith(("Detected that custom integration", "The deprecated"))
    ]
    assert not reports, "\n".join(reports)


def _unconnected_socket() -> socket.socket:
    """Return a socket that never receives anything."""
    sock, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM)
    peer.close()
    sock.setblocking(False)
    return sock


@pytest.fixture(autouse=True)
def discovery_socket() -> Generator[MagicMock]:
    """Keep the discovery listener and the scans off the network; `announce` feeds the listener instead."""
    with patch(
        "custom_components.airfi_home.utils.discovery.create_discovery_socket",
        side_effect=_unconnected_socket,
    ) as create:
        yield create


@pytest.fixture
def announce(hass: HomeAssistant) -> Callable[..., None]:
    """
    Hand the running discovery listener an announcement, as the network would deliver it.

    Returns:
        A function taking the announced IP address, the serial number and the model ID.

    """

    def _announce(host: str, serial: int, model_id: int = 1) -> None:
        packet = socket.inet_aton(host)[::-1] + struct.pack("<HI", DISCOVERY_DEVICE_PORT, serial) + bytes([0, model_id])
        hass.data[DATA_DISCOVERY_LISTENER].datagram_received(packet, (host, DISCOVERY_MULTICAST_PORT))

    return _announce


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock config entry for Airfi."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_SERIAL_NUMBER: "12345678",
            CONF_MODEL_NAME: "Model 60 L",
        },
        unique_id="12345678",
        title="Airfi Model 60 L",
    )


@pytest.fixture
def mock_api() -> Generator[SimpleNamespace]:
    """Patch the client with a unit that answers with every register and accepts every write."""
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
        patch.object(AirfiApiClient, "async_write_holding_register", AsyncMock()) as write_holding_register,
    ):
        yield SimpleNamespace(
            get_lookup_registers=get_lookup_registers,
            get_data=get_data,
            write_holding_register=write_holding_register,
        )


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
