"""Shared fixtures for Airfi tests."""

from collections.abc import Callable, Coroutine, Generator
import logging
import socket
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from pymodbus.exceptions import ModbusIOException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.api import AirfiApiClient
from custom_components.airfi_home.const import (
    CONF_MODBUS_ID,
    CONF_MODEL_NAME,
    CONF_SERIAL_NUMBER,
    DEFAULT_MODBUS_ID,
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
INPUT_REGISTERS = [*LOOKUP_REGISTERS, *[0] * (INPUT_REGISTER_COUNT - len(LOOKUP_REGISTERS))]
HOLDING_REGISTERS = [0] * HOLDING_REGISTER_COUNT
MAP_2_9_INPUT_REGISTER_COUNT = 47
MAP_2_9_HOLDING_REGISTER_COUNT = 65


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
            CONF_MODBUS_ID: DEFAULT_MODBUS_ID,
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
        "input_registers": list(INPUT_REGISTERS),
        "holding_registers": list(HOLDING_REGISTERS),
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


async def _async_set_up(hass: HomeAssistant, config_entry: MockConfigEntry) -> MockConfigEntry:
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def modbus_unit() -> Generator[SimpleNamespace]:
    """
    Patch the Modbus connection with a supported unit that answers only to its own Modbus ID.

    Like a real unit, it stays silent towards any other ID. Set `modbus_id` to change the ID it answers to;
    `connection` is the patched pymodbus client, for asserting which ID a request used.
    """
    unit = SimpleNamespace(modbus_id=DEFAULT_MODBUS_ID, connection=MagicMock())

    def _reader(registers: list[int]) -> Callable[..., MagicMock]:
        def _read(address: int, *, count: int, device_id: int) -> MagicMock:
            if device_id != unit.modbus_id:
                raise ModbusIOException("No response received after 0 retries")
            return MagicMock(
                isError=MagicMock(return_value=False), registers=registers[address - 1 : address - 1 + count]
            )

        return _read

    unit.connection.connect.return_value = True
    unit.connection.read_input_registers.side_effect = _reader(INPUT_REGISTERS)
    unit.connection.read_holding_registers.side_effect = _reader(HOLDING_REGISTERS)
    with patch("custom_components.airfi_home.api.client.ModbusTcpClient", return_value=unit.connection):
        yield unit


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
    return await _async_set_up(hass, config_entry)


@pytest.fixture
def map_2_9_api(mock_api: SimpleNamespace) -> SimpleNamespace:
    """Turn the patched unit into one on register map 2.9, the first with the boost registers."""
    lookup_registers = [100, 381, 290]
    mock_api.get_lookup_registers.return_value = lookup_registers
    data = mock_api.get_data.return_value
    data["modbus_register_version"] = "2.9.0"
    data["input_registers"] = [*lookup_registers, *[0] * (MAP_2_9_INPUT_REGISTER_COUNT - len(lookup_registers))]
    data["holding_registers"] = [0] * MAP_2_9_HOLDING_REGISTER_COUNT
    return mock_api


@pytest.fixture
async def init_map_2_9_integration(
    hass: HomeAssistant,
    map_2_9_api: SimpleNamespace,
    config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """
    Set up the integration for a unit on register map 2.9.

    Returns:
        The config entry, now loaded.

    """
    return await _async_set_up(hass, config_entry)


@pytest.fixture
def report_holding_register(
    hass: HomeAssistant,
    map_2_9_api: SimpleNamespace,
    init_map_2_9_integration: MockConfigEntry,
) -> Callable[[int, int], Coroutine[None, None, None]]:
    """
    Let the register map 2.9 unit report a new holding register value, and poll it.

    Returns:
        A coroutine function taking the register address and its new value.

    """

    async def _report(address: int, value: int) -> None:
        map_2_9_api.get_data.return_value["holding_registers"][address - 1] = value
        await init_map_2_9_integration.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()

    return _report


@pytest.fixture
def mock_integration() -> MagicMock:
    """Create a mock integration object for runtime data."""
    return MagicMock()
