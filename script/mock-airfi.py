#!/usr/bin/env python3
"""Mock Airfi air handling unit for local development.

Runs a small Modbus TCP server that answers like an Airfi unit, plus the
unit's UDP multicast announcements so Home Assistant can discover it.
Run it with the Home Assistant venv's Python; it takes register numbers,
ports and model names from the integration. `--help` lists the options.

Usage
-----
Basic (single unit, like firmware 3.8.1 on register map 3.0):
    python3 script/mock-airfi.py --serial=12345678

Older unit:
    python3 script/mock-airfi.py --serial=12345678 --firmware=3.1.0 --modbus=2.5.0 --model=3

Fixed IP in announcements (useful for rediscovery testing):
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.2

Rediscovery test workflow:
    # Step 1 - start the mock announcing 127.0.0.2
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.2
    # Add the unit in Home Assistant with host=127.0.0.2
    # Step 2 - restart the mock announcing 127.0.0.3 (simulates an IP change)
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.3
    # Any 127.x.x.x address works without 'ip addr add' on Linux (the whole /8 is loopback)

Unit that answers to another Modbus ID:
    python3 script/mock-airfi.py --serial=12345678 --unit-id=5

Multiple units (separate terminals):
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.2
    python3 script/mock-airfi.py --serial=87654321 --ip=127.0.0.3

Behaviour
---------
- Register counts follow the register map version; the highest known map at or
  below the requested one decides. Map 1.5 is kept to try the refusal.
- Requests for a Modbus ID other than the unit's own (--unit-id) or 0 get no answer, and every
  other such request also closes the connection 3 s later, as on the unit.
- Firmware 3.2.0 hides input register 10: any read covering it fails.
- Temperatures and humidity drift slightly.
- A boost (4x62) counts down once a minute, one minute at once when it starts; 0 stops it.
  The fan control % (3x11, 3x12) follows the speed and is raised by the boost speed
  (4x63, 50 %) unless either fan would go above 100 %, in which case the unit does not boost.
- Announcements keep retrying after a send error (no route, VPN).
- Stop with Ctrl+C.
"""

import argparse
import asyncio
from collections.abc import Callable
import contextlib
from enum import Enum, auto
import errno
import ipaddress
import logging
from pathlib import Path
import random
import signal
import socket
import struct
import sys
import time
from typing import Self

sys.path.insert(0, str(Path(__file__).parent / ".."))

from custom_components.airfi_home.api.register_map import REGISTER_LENGTHS_BY_MAP_VERSION
from custom_components.airfi_home.const import (
    AIRFI_MODELS,
    DEFAULT_MODBUS_ID,
    DEFAULT_MODBUS_PORT,
    DISCOVERY_DEVICE_PORT,
    DISCOVERY_MULTICAST_GROUP,
    DISCOVERY_MULTICAST_PORT,
    MODBUS_ID_MAX,
    MODBUS_ID_MIN,
)
from custom_components.airfi_home.sensor.humidity import INPUT_REGISTER_RELATIVE_HUMIDITY
from custom_components.airfi_home.utils.boost import HOLDING_REGISTER_BOOST_SPEED, HOLDING_REGISTER_BOOST_TIME
from custom_components.airfi_home.utils.discovery import get_model_name
from custom_components.airfi_home.utils.fan import HOLDING_REGISTER_FAN_ACTIVE, HOLDING_REGISTER_FAN_SPEED
from custom_components.airfi_home.utils.number import (
    HOLDING_REGISTER_MINIMUM_TEMPERATURE,
    HOLDING_REGISTER_TARGET_TEMPERATURE,
)
from custom_components.airfi_home.utils.temperature import (
    INPUT_REGISTER_EXHAUST_AIR_TEMP,
    INPUT_REGISTER_EXTRACT_AIR_TEMP,
    INPUT_REGISTER_OUTDOOR_AIR_TEMP,
    INPUT_REGISTER_SUPPLY_AIR_TEMP,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("mock-airfi")

BROADCAST_UNIT_ID = 0
WRONG_UNIT_ID_CLOSE_SECONDS = 3.0
MAX_FRAME_LENGTH = 254

READ_HOLDING_REGISTERS = 3
READ_INPUT_REGISTERS = 4
WRITE_SINGLE_REGISTER = 6
ILLEGAL_FUNCTION = 1
ILLEGAL_DATA_ADDRESS = 2
ILLEGAL_DATA_VALUE = 3

MBAP_HEADER = struct.Struct(">HHHB")

HARDWARE_VERSION = 160
TEMPERATURE_REGISTERS = (
    INPUT_REGISTER_OUTDOOR_AIR_TEMP,
    INPUT_REGISTER_EXTRACT_AIR_TEMP,
    INPUT_REGISTER_EXHAUST_AIR_TEMP,
    INPUT_REGISTER_SUPPLY_AIR_TEMP,
)
DRIFT_INTERVAL_SECONDS = 5.0
BOOST_TICK_SECONDS = 60.0
DEFAULT_BOOST_SPEED = 50
INPUT_REGISTER_EXHAUST_FAN_CONTROL = 11
INPUT_REGISTER_SUPPLY_FAN_CONTROL = 12
FAN_CONTROL_BY_SPEED: dict[int, tuple[int, int]] = {
    1: (27, 30),
    2: (35, 40),
    3: (55, 63),
    4: (66, 75),
    5: (88, 100),
}
"""Exhaust and supply fan control % per speed step, as measured on a Model 60 (fw 381, map 3.0)."""
ANNOUNCE_INTERVAL_SECONDS = 2.0

type Version = tuple[int, int, int]

FIRMWARE_HIDING_INPUT_REGISTER_10: Version = (3, 2, 0)
REGISTER_PROFILES: tuple[tuple[Version, tuple[int, int]], ...] = (
    *REGISTER_LENGTHS_BY_MAP_VERSION,
    ((1, 5, 0), (31, 12)),
)


def parse_version(text: str) -> Version:
    """Parse a version such as 3.1.0."""
    parts = text.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise argparse.ArgumentTypeError(f"invalid version: {text}")
    major, minor, patch = (int(part) for part in parts)
    if not 1 <= major <= 9 or minor > 9 or patch > 9:
        raise argparse.ArgumentTypeError(
            f"invalid version: {text} (the unit reports each part as one digit, major 1-9)"
        )
    return major, minor, patch


def parse_serial(text: str) -> int:
    """Parse a serial number that fits the announcement's 32 bits."""
    try:
        serial = int(text)
    except ValueError:
        serial = -1
    if not 0 <= serial <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError(f"invalid serial number: {text}")
    return serial


def parse_ipv4(text: str) -> str:
    """Parse an IPv4 address."""
    try:
        return str(ipaddress.IPv4Address(text))
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"invalid IPv4 address: {text}") from err


class Silence(Enum):
    """How the unit leaves a request unanswered."""

    KEEP_OPEN = auto()
    CLOSE_LATER = auto()


def version_to_register(version: Version) -> int:
    """Encode a version the way the unit reports it: 3.1.0 is 310."""
    major, minor, patch = version
    return major * 100 + minor * 10 + patch


def register_counts(map_version: Version) -> tuple[int, int]:
    """Return the (input, holding) register counts for a register map version."""
    for version, counts in REGISTER_PROFILES:
        if map_version >= version:
            return counts
    return REGISTER_PROFILES[-1][1]


def _set(values: list[int], register: int, value: int) -> None:
    if register <= len(values):
        values[register - 1] = value


def build_input_registers(*, firmware: Version, map_version: Version) -> list[int]:
    """Build input registers with versions and plausible sensor values (temperatures in tenths of °C)."""
    values = [0] * register_counts(map_version)[0]
    _set(values, 1, HARDWARE_VERSION)
    _set(values, 2, version_to_register(firmware))
    _set(values, 3, version_to_register(map_version))
    _set(values, INPUT_REGISTER_OUTDOOR_AIR_TEMP, 52)
    _set(values, INPUT_REGISTER_EXTRACT_AIR_TEMP, 215)
    _set(values, INPUT_REGISTER_EXHAUST_AIR_TEMP, 83)
    _set(values, INPUT_REGISTER_SUPPLY_AIR_TEMP, 200)
    _set(values, INPUT_REGISTER_RELATIVE_HUMIDITY, 45)
    return values


def build_holding_registers(*, map_version: Version) -> list[int]:
    """Build holding registers: speed 3, at home, supply air setpoint 20 °C, minimum temperature 15 °C, boost 50 %."""
    values = [0] * register_counts(map_version)[1]
    _set(values, HOLDING_REGISTER_FAN_SPEED, 3)
    _set(values, HOLDING_REGISTER_TARGET_TEMPERATURE, 200)
    _set(values, HOLDING_REGISTER_MINIMUM_TEMPERATURE, 15)
    _set(values, HOLDING_REGISTER_BOOST_SPEED, DEFAULT_BOOST_SPEED)
    return values


class MockAirfiUnit:
    """Answers Modbus TCP request frames like an Airfi unit.

    Register N is protocol address N in both blocks, as in the Airfi register map.
    """

    def __init__(
        self,
        *,
        input_registers: list[int],
        holding_registers: list[int],
        hidden_input_registers: frozenset[int] = frozenset(),
        unit_id: int = DEFAULT_MODBUS_ID,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the unit with its register values."""
        self.input_registers = input_registers
        self.holding_registers = holding_registers
        self.hidden_input_registers = hidden_input_registers
        self.unit_id = unit_id
        self._clock = clock
        self._last_drift = clock()
        self._last_boost_tick = clock()
        self._unanswered_for_other_ids = 0
        self._update_fan_control()

    @classmethod
    def for_versions(
        cls,
        *,
        firmware: Version,
        map_version: Version,
        unit_id: int = DEFAULT_MODBUS_ID,
        clock: Callable[[], float] = time.monotonic,
    ) -> Self:
        """Build a unit with the registers and quirks of a firmware and register map version."""
        return cls(
            input_registers=build_input_registers(firmware=firmware, map_version=map_version),
            holding_registers=build_holding_registers(map_version=map_version),
            hidden_input_registers=frozenset({10}) if firmware == FIRMWARE_HIDING_INPUT_REGISTER_10 else frozenset(),
            unit_id=unit_id,
            clock=clock,
        )

    def handle(self, frame: bytes) -> bytes | Silence:
        """Return the response frame for one request frame, or how the unit stays silent."""
        if len(frame) < MBAP_HEADER.size + 1:
            return Silence.KEEP_OPEN
        transaction, _protocol, _length, unit_id = MBAP_HEADER.unpack_from(frame)
        if unit_id not in (BROADCAST_UNIT_ID, self.unit_id):
            self._unanswered_for_other_ids += 1
            return Silence.CLOSE_LATER if self._unanswered_for_other_ids % 2 == 0 else Silence.KEEP_OPEN
        self._advance()
        function = frame[MBAP_HEADER.size]
        data = frame[MBAP_HEADER.size + 1 :]

        if function in (READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS, WRITE_SINGLE_REGISTER) and len(data) < 4:
            return _exception(transaction, unit_id, function, ILLEGAL_DATA_VALUE)

        if function in (READ_HOLDING_REGISTERS, READ_INPUT_REGISTERS):
            address, count = struct.unpack_from(">HH", data)
            values = self._read(function, address, count)
            if values is None:
                return _exception(transaction, unit_id, function, ILLEGAL_DATA_ADDRESS)
            return _frame(transaction, unit_id, struct.pack(f">BB{count}H", function, 2 * count, *values))

        if function == WRITE_SINGLE_REGISTER:
            address, value = struct.unpack_from(">HH", data)
            if not self._write(address, value):
                return _exception(transaction, unit_id, function, ILLEGAL_DATA_ADDRESS)
            return _frame(transaction, unit_id, struct.pack(">BHH", function, address, value))

        return _exception(transaction, unit_id, function, ILLEGAL_FUNCTION)

    def _read(self, function: int, address: int, count: int) -> list[int] | None:
        registers = self.holding_registers if function == READ_HOLDING_REGISTERS else self.input_registers
        last = address + count - 1
        if count < 1 or address < 1 or last > len(registers):
            return None
        if function == READ_INPUT_REGISTERS and any(
            address <= hidden <= last for hidden in self.hidden_input_registers
        ):
            return None
        return registers[address - 1 : last]

    def _write(self, address: int, value: int) -> bool:
        if not 1 <= address <= len(self.holding_registers):
            return False
        if address == HOLDING_REGISTER_BOOST_TIME and value > 0:
            # The unit counts a new boost down by one minute at once, then once a minute.
            value -= 1
            self._last_boost_tick = self._clock()
        self.holding_registers[address - 1] = value
        self._update_fan_control()
        return True

    def _advance(self) -> None:
        """Bring the time-driven registers up to the clock."""
        now = self._clock()
        if now - self._last_drift >= DRIFT_INTERVAL_SECONDS:
            self._last_drift = now
            self._drift()
        self._count_boost_down(now)
        self._update_fan_control()

    def _count_boost_down(self, now: float) -> None:
        if len(self.holding_registers) < HOLDING_REGISTER_BOOST_TIME:
            return
        while now - self._last_boost_tick >= BOOST_TICK_SECONDS:
            self._last_boost_tick += BOOST_TICK_SECONDS
            remaining = self.holding_registers[HOLDING_REGISTER_BOOST_TIME - 1]
            self.holding_registers[HOLDING_REGISTER_BOOST_TIME - 1] = max(0, remaining - 1)

    def _update_fan_control(self) -> None:
        """Show the fan control % of the current speed, raised by a running boost unless a fan would pass 100 %."""
        away = self._holding(HOLDING_REGISTER_FAN_ACTIVE) == 1
        speed = 1 if away else self._holding(HOLDING_REGISTER_FAN_SPEED)
        exhaust, supply = FAN_CONTROL_BY_SPEED.get(speed, (0, 0))
        if self._holding(HOLDING_REGISTER_BOOST_TIME) > 0:
            factor = 1 + self._holding(HOLDING_REGISTER_BOOST_SPEED) / 100
            boosted = (int(exhaust * factor), int(supply * factor))
            if max(boosted) <= 100:
                exhaust, supply = boosted
        _set(self.input_registers, INPUT_REGISTER_EXHAUST_FAN_CONTROL, exhaust)
        _set(self.input_registers, INPUT_REGISTER_SUPPLY_FAN_CONTROL, supply)

    def _holding(self, register: int) -> int:
        return self.holding_registers[register - 1] if register <= len(self.holding_registers) else 0

    def _drift(self) -> None:
        for register in TEMPERATURE_REGISTERS:
            value = self.input_registers[register - 1] + random.randint(-2, 2)
            self.input_registers[register - 1] = max(0, min(65535, value))
        humidity = self.input_registers[INPUT_REGISTER_RELATIVE_HUMIDITY - 1] + random.randint(-1, 1)
        self.input_registers[INPUT_REGISTER_RELATIVE_HUMIDITY - 1] = max(20, min(80, humidity))


def _frame(transaction: int, unit_id: int, pdu: bytes) -> bytes:
    return MBAP_HEADER.pack(transaction, 0, len(pdu) + 1, unit_id) + pdu


def _exception(transaction: int, unit_id: int, function: int, code: int) -> bytes:
    return _frame(transaction, unit_id, struct.pack(">BB", function | 0x80, code))


async def serve_client(unit: MockAirfiUnit, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Answer the requests on one connection until the client closes it."""
    peer = writer.get_extra_info("peername")
    LOGGER.debug("Client connected: %s", peer)
    try:
        while True:
            header = await reader.readexactly(MBAP_HEADER.size)
            length = MBAP_HEADER.unpack(header)[2]
            if not 2 <= length <= MAX_FRAME_LENGTH:
                LOGGER.warning("Closing %s: frame length %d", peer, length)
                return
            response = unit.handle(header + await reader.readexactly(length - 1))
            if response is Silence.CLOSE_LATER:
                LOGGER.debug("Closing %s soon: request for another Modbus ID", peer)
                await asyncio.sleep(WRONG_UNIT_ID_CLOSE_SECONDS)
                return
            if isinstance(response, bytes):
                writer.write(response)
                await writer.drain()
    except asyncio.IncompleteReadError, ConnectionError:
        pass
    finally:
        writer.close()
        with contextlib.suppress(ConnectionError):
            await writer.wait_closed()
        LOGGER.debug("Client disconnected: %s", peer)


def get_local_ip() -> str:
    """Get the local IP address used for outbound connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def build_discovery_packet(*, ip: str, serial: int, model_id: int) -> bytes:
    """Build the unit's 12-byte announcement.

    Bytes 0-3 IP address octets in reverse order, 4-5 device port (uint16 LE, always 4000),
    6-9 serial number (uint32 LE), 10 constant 0, 11 model ID.
    """
    octets = bytes(reversed([int(octet) for octet in ip.split(".")]))
    return octets + struct.pack("<HIBB", DISCOVERY_DEVICE_PORT, serial, 0, model_id)


async def send_announcements(packet: bytes, stop_event: asyncio.Event) -> None:
    """Send the announcement every ANNOUNCE_INTERVAL_SECONDS, retrying after send errors."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sending = True
    try:
        while not stop_event.is_set():
            try:
                sock.sendto(packet, (DISCOVERY_MULTICAST_GROUP, DISCOVERY_MULTICAST_PORT))
            except OSError as err:
                if sending:
                    LOGGER.warning(
                        "Announcement not sent (%s); retrying. Adding the unit by its address still works", err
                    )
                    sending = False
            else:
                if not sending:
                    LOGGER.info("Announcements sent again")
                    sending = True
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=ANNOUNCE_INTERVAL_SECONDS)
    finally:
        sock.close()


async def run_mock_unit(args: argparse.Namespace) -> None:
    """Run the Modbus server and the announcements until stopped."""
    unit = MockAirfiUnit.for_versions(firmware=args.firmware, map_version=args.modbus, unit_id=args.unit_id)
    bind_address = args.ip or "0.0.0.0"
    announced_ip = args.ip or get_local_ip()

    try:
        server = await asyncio.start_server(
            lambda reader, writer: serve_client(unit, reader, writer),
            host=bind_address,
            port=DEFAULT_MODBUS_PORT,
            reuse_address=True,
        )
    except OSError as err:
        hint = ". Use a loopback address like 127.0.0.2" if err.errno == errno.EADDRNOTAVAIL else ""
        LOGGER.error("Cannot listen on %s:%d: %s%s", bind_address, DEFAULT_MODBUS_PORT, err, hint)
        raise SystemExit(1) from err

    LOGGER.info("Mock Airfi unit: serial %d, %s (ID %d)", args.serial, get_model_name(args.model), args.model)
    LOGGER.info(
        "Firmware %s, register map %s: %d input, %d holding",
        ".".join(map(str, args.firmware)),
        ".".join(map(str, args.modbus)),
        len(unit.input_registers),
        len(unit.holding_registers),
    )
    LOGGER.info("Modbus TCP on %s:%d, answering Modbus ID %d", bind_address, DEFAULT_MODBUS_PORT, unit.unit_id)
    if unit.hidden_input_registers:
        LOGGER.warning("Input registers %s are hidden, reads covering them fail", sorted(unit.hidden_input_registers))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    announcer: asyncio.Task[None] | None = None
    if args.no_announce:
        LOGGER.info("Announcements off")
    else:
        packet = build_discovery_packet(ip=announced_ip, serial=args.serial, model_id=args.model)
        announcer = asyncio.create_task(send_announcements(packet, stop_event))
        LOGGER.info("Announcing %s on %s:%d", announced_ip, DISCOVERY_MULTICAST_GROUP, DISCOVERY_MULTICAST_PORT)

    async with server:
        await stop_event.wait()
        # Leaving the block waits for every client to disconnect, so a client still connected would keep the mock running.
        server.close_clients()
    if announcer is not None:
        await announcer
    LOGGER.info("Mock unit stopped")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Mock Airfi air handling unit (Modbus TCP server + announcements)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--serial", type=parse_serial, default=12345678, help="serial number")
    parser.add_argument("--firmware", type=parse_version, default="3.8.1", help="firmware version")
    parser.add_argument("--modbus", type=parse_version, default="3.0.0", help="register map version")
    parser.add_argument(
        "--model",
        type=int,
        default=3,
        choices=range(1, 2 * len(AIRFI_MODELS) + 1),
        metavar=f"1-{2 * len(AIRFI_MODELS)}",
        help="model ID; odd IDs are L, even R models",
    )
    parser.add_argument(
        "--ip",
        type=parse_ipv4,
        default=None,
        help="address to announce and bind to; without it, the detected local address is announced and all are bound",
    )
    parser.add_argument(
        "--unit-id",
        type=int,
        default=DEFAULT_MODBUS_ID,
        choices=range(MODBUS_ID_MIN, MODBUS_ID_MAX + 1),
        metavar=f"{MODBUS_ID_MIN}-{MODBUS_ID_MAX}",
        help="Modbus ID the unit answers to, besides 0",
    )
    parser.add_argument("--no-announce", action="store_true", help="do not send announcements")
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_mock_unit(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
