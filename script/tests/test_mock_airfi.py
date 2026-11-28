"""Tests for the mock Airfi unit in script/mock-airfi.py."""

import argparse
import asyncio
from collections.abc import Callable
import importlib.util
from pathlib import Path
import struct
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

MOCK_PATH = Path(__file__).parents[1] / "mock-airfi.py"


def _load_mock() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mock_airfi", MOCK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mock_airfi = _load_mock()
# Importable only once the mock has put the repository root on the path.
discovery = importlib.import_module("custom_components.airfi_home.utils.discovery")


def _request(function: int, address: int, value: int, *, unit_id: int = 1, transaction: int = 7) -> bytes:
    return struct.pack(">HHHBBHH", transaction, 0, 6, unit_id, function, address, value)


def _unit(
    *,
    firmware: tuple[int, int, int] = (3, 8, 1),
    map_version: tuple[int, int, int] = (3, 0, 0),
    unit_id: int = 1,
    clock: Callable[[], float] = lambda: 0.0,
) -> Any:
    return mock_airfi.MockAirfiUnit.for_versions(
        firmware=firmware, map_version=map_version, unit_id=unit_id, clock=clock
    )


def _values(response: bytes) -> list[int]:
    count = response[8] // 2
    return list(struct.unpack(f">{count}H", response[9 : 9 + 2 * count]))


def test_reads_the_version_registers() -> None:
    """Input registers 1-3 hold hardware, firmware and register map versions."""
    response = _unit().handle(_request(4, 1, 3))

    assert isinstance(response, bytes)
    assert response[:8] == struct.pack(">HHHBB", 7, 0, 9, 1, 4)
    assert _values(response) == [160, 381, 300]


def test_reads_holding_registers() -> None:
    """Holding register 1 is the fan speed and 5 the supply air setpoint."""
    response = _unit().handle(_request(3, 1, 5))

    assert isinstance(response, bytes)
    assert _values(response) == [3, 0, 0, 0, 200]


def test_write_stores_the_value_and_echoes_it() -> None:
    """A single register write is stored and echoed back."""
    unit = _unit()

    response = unit.handle(_request(6, 1, 5))

    assert isinstance(response, bytes)
    assert response[7:] == struct.pack(">BHH", 6, 1, 5)
    assert unit.holding_registers[0] == 5


@pytest.mark.parametrize(
    ("function", "address", "value"),
    [
        pytest.param(4, 0, 1, id="input address 0"),
        pytest.param(4, 42, 2, id="input past the end"),
        pytest.param(3, 59, 2, id="holding past the end"),
        pytest.param(3, 1, 0, id="zero registers"),
        pytest.param(6, 60, 1, id="write past the end"),
    ],
)
def test_out_of_range_is_an_illegal_address(function: int, address: int, value: int) -> None:
    """Registers the map version lacks answer with exception 2."""
    response = _unit().handle(_request(function, address, value))

    assert isinstance(response, bytes)
    assert response[7:] == bytes([function | 0x80, 2])


def test_short_request_is_an_illegal_data_value() -> None:
    """A read without its address and count answers with exception 3."""
    response = _unit().handle(struct.pack(">HHHBB", 7, 0, 2, 1, 4))

    assert isinstance(response, bytes)
    assert response[7:] == bytes([4 | 0x80, 3])


def test_unknown_function_is_an_illegal_function() -> None:
    """A function the unit lacks answers with exception 1."""
    response = _unit().handle(_request(16, 1, 1))

    assert isinstance(response, bytes)
    assert response[7:] == bytes([16 | 0x80, 1])


@pytest.mark.parametrize(
    ("unit_id", "answered"),
    [
        pytest.param(5, True, id="own ID"),
        pytest.param(0, True, id="broadcast ID"),
        pytest.param(1, False, id="ID 1"),
        pytest.param(247, False, id="ID 247"),
    ],
)
def test_answers_only_its_own_and_the_broadcast_id(unit_id: int, *, answered: bool) -> None:
    """The unit answers its Modbus ID and 0, and stays silent for any other."""
    response = _unit(unit_id=5).handle(_request(4, 1, 1, unit_id=unit_id))

    assert isinstance(response, bytes) is answered


def test_every_other_request_for_another_id_closes_the_connection_later() -> None:
    """The unit keeps the connection after one unanswered request for another ID, and closes it after the next."""
    unit = _unit()

    silences = [unit.handle(_request(4, 1, 1, unit_id=2)) for _ in range(4)]

    assert silences == [mock_airfi.Silence.KEEP_OPEN, mock_airfi.Silence.CLOSE_LATER] * 2


def test_short_frame_gets_no_answer() -> None:
    """A frame without a function code is ignored, and the connection stays open."""
    assert _unit().handle(struct.pack(">HHHB", 1, 0, 1, 1)) is mock_airfi.Silence.KEEP_OPEN


@pytest.mark.parametrize(
    ("address", "count", "fails"),
    [
        pytest.param(1, 3, False, id="before"),
        pytest.param(8, 5, True, id="across"),
        pytest.param(10, 1, True, id="only register 10"),
        pytest.param(11, 2, False, id="after"),
    ],
)
def test_firmware_320_hides_input_register_10(address: int, count: int, *, fails: bool) -> None:
    """On firmware 3.2.0 every input read covering register 10 fails."""
    response = _unit(firmware=(3, 2, 0), map_version=(2, 7, 0)).handle(_request(4, address, count))

    assert isinstance(response, bytes)
    assert (response[7] == 4 | 0x80) is fails


@pytest.mark.parametrize(
    ("map_version", "counts"),
    [
        pytest.param((3, 0, 0), (42, 59), id="3.0 reads 2.7"),
        pytest.param((2, 7, 0), (42, 59), id="2.7"),
        pytest.param((2, 6, 0), (40, 58), id="2.6 reads 2.5"),
        pytest.param((2, 0, 0), (40, 34), id="2.0"),
        pytest.param((1, 5, 0), (31, 12), id="1.5"),
        pytest.param((1, 0, 0), (31, 12), id="below every map"),
    ],
)
def test_register_counts_follow_the_highest_known_map(
    map_version: tuple[int, int, int], counts: tuple[int, int]
) -> None:
    """A map between two known ones gets the lower one's counts; below every known map, the lowest."""
    assert mock_airfi.register_counts(map_version) == counts


def test_short_maps_leave_out_registers_they_lack() -> None:
    """Map 1.5 has 12 holding registers, so the minimum temperature (50) is not set."""
    assert mock_airfi.build_holding_registers(map_version=(1, 5, 0)) == [3, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0]


@pytest.mark.parametrize(
    "text", [pytest.param(t, id=t) for t in ("3.1", "3.1.x", "a.b.c", "2.10.0", "0.2.0", "10.0.0")]
)
def test_invalid_version_is_refused(text: str) -> None:
    """Versions need three numeric parts."""
    with pytest.raises(argparse.ArgumentTypeError, match="invalid version"):
        mock_airfi.parse_version(text)


@pytest.mark.parametrize("text", [pytest.param(t, id=t) for t in ("-1", "4294967296", "x")])
def test_invalid_serial_is_refused(text: str) -> None:
    """Serial numbers must fit the announcement's 32 bits."""
    with pytest.raises(argparse.ArgumentTypeError, match="invalid serial"):
        mock_airfi.parse_serial(text)


@pytest.mark.parametrize("text", [pytest.param(t, id=t) for t in ("localhost", "127.0.0", "::1")])
def test_invalid_ip_is_refused(text: str) -> None:
    """The announcement carries an IPv4 address."""
    with pytest.raises(argparse.ArgumentTypeError, match="invalid IPv4"):
        mock_airfi.parse_ipv4(text)


def test_sensor_values_drift_only_after_the_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Temperatures move by up to 2 and humidity by up to 1 per drift, no sooner than every 5 s."""
    monkeypatch.setattr(mock_airfi.random, "randint", lambda _low, high: high)
    now = [0.0]
    unit = _unit(clock=lambda: now[0])
    before = list(unit.input_registers)
    humidity = mock_airfi.INPUT_REGISTER_RELATIVE_HUMIDITY - 1

    unit.handle(_request(4, 1, 30))
    assert unit.input_registers == before

    now[0] = 5.0
    unit.handle(_request(4, 1, 30))
    assert all(unit.input_registers[r - 1] == before[r - 1] + 2 for r in mock_airfi.TEMPERATURE_REGISTERS)
    assert unit.input_registers[humidity] == before[humidity] + 1


def test_announcement_is_read_by_the_integration() -> None:
    """The integration's own parser reads the mock's announcement."""
    packet = mock_airfi.build_discovery_packet(ip="192.168.1.20", serial=12345678, model_id=3)

    assert discovery.parse_announcement(packet, "192.168.1.20") == discovery.AirfiDiscoveredDevice(
        host="192.168.1.20", serial=12345678, model_id=3
    )


def _writer() -> MagicMock:
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return writer


async def test_connection_answers_each_request_until_closed() -> None:
    """Several requests on one connection each get their answer; silence for another Modbus ID."""
    reader = asyncio.StreamReader()
    reader.feed_data(_request(4, 1, 3, transaction=1) + _request(4, 1, 3, unit_id=5) + _request(3, 1, 1, transaction=2))
    reader.feed_eof()
    writer = _writer()

    await mock_airfi.serve_client(_unit(), reader, writer)

    responses = [call.args[0] for call in writer.write.call_args_list]
    assert [struct.unpack_from(">H", response)[0] for response in responses] == [1, 2]
    writer.close.assert_called_once()


async def test_connection_with_a_bad_length_is_closed() -> None:
    """A frame claiming an impossible length closes the connection without an answer."""
    reader = asyncio.StreamReader()
    reader.feed_data(struct.pack(">HHHB", 1, 0, 1000, 1))
    writer = _writer()

    await mock_airfi.serve_client(_unit(), reader, writer)

    writer.write.assert_not_called()
    writer.close.assert_called_once()


async def test_connection_closes_after_the_second_request_for_another_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """After the second unanswered request for another ID, the unit closes the connection and reads no further."""
    monkeypatch.setattr(mock_airfi, "WRONG_UNIT_ID_CLOSE_SECONDS", 0)
    reader = asyncio.StreamReader()
    reader.feed_data(_request(4, 1, 3, unit_id=5) + _request(4, 1, 3, unit_id=5) + _request(4, 1, 3))
    writer = _writer()

    await mock_airfi.serve_client(_unit(), reader, writer)

    writer.write.assert_not_called()
    writer.close.assert_called_once()


def test_unit_id_option_sets_the_id_the_unit_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """--unit-id takes 1-247 and defaults to 1."""
    monkeypatch.setattr(mock_airfi.sys, "argv", ["mock-airfi.py"])
    assert mock_airfi.parse_args().unit_id == 1

    monkeypatch.setattr(mock_airfi.sys, "argv", ["mock-airfi.py", "--unit-id=5"])
    assert mock_airfi.parse_args().unit_id == 5

    monkeypatch.setattr(mock_airfi.sys, "argv", ["mock-airfi.py", "--unit-id=0"])
    with pytest.raises(SystemExit):
        mock_airfi.parse_args()
