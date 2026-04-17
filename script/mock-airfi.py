#!/usr/bin/env python3
"""Mock Airfi air handling unit for local development.

Runs a pymodbus TCP server simulating an Airfi device with configurable
register profiles, plus sends UDP multicast discovery packets so the
HA integration can auto-discover the mock device.

Usage
-----
Basic (single device):
    python3 script/mock-airfi.py --serial=12345678

Full options:
    python3 script/mock-airfi.py --serial=12345678 --firmware=3.1.0 --modbus=2.5.0 --model=3

Fixed IP in discovery packets (useful for rediscovery testing):
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.2

Rediscovery test workflow:
    # Step 1 – start mock advertising 127.0.0.2
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.2
    # Configure HA integration with host=127.0.0.2
    # Step 2 – restart mock advertising 127.0.0.3 (simulates IP change)
    python3 script/mock-airfi.py --serial=12345678 --ip=127.0.0.3
    # HA loses connection to 127.0.0.2, triggers rediscovery, finds 127.0.0.3
    # Any 127.x.x.x address works without 'ip addr add' on Linux (entire /8 is loopback)

Multiple devices (open separate terminals):
    python3 script/mock-airfi.py --serial=12345678
    python3 script/mock-airfi.py --serial=87654321

Arguments:
---------
--serial        Device serial number (default: 12345678)
--firmware      Firmware version string, e.g. 3.1.0 (default: 3.1.0)
--modbus        Modbus register map version, e.g. 2.7.0 (default: 2.7.0)
--model         Model ID 1-38 (default: 3, i.e. "150 L")
--ip            IP address to advertise in discovery packets AND to bind the Modbus
                server to. The server only responds to connections on this address,
                which enables rediscovery testing (see usage examples above).
                Use 127.0.0.x addresses – the full 127/8 loopback block is always
                available on Linux without 'ip addr add'.
                (default: auto-detect local IP, bind to 0.0.0.0)

Notes:
-----
- Registers are initialized with realistic simulated values.
- Register profile is loaded from the --modbus version parameter.
- SO_REUSEADDR is set for the discovery socket.
- Stop with Ctrl+C.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
from pathlib import Path
import random
import signal
import socket
import struct
import sys

from packaging import version as pkg_version

# Allow running from repo root without install
sys.path.insert(0, str(Path(__file__).parent / ".."))

from pymodbus.datastore import ModbusDeviceContext, ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.datastore.store import ExcCodes
from pymodbus.server import ModbusTcpServer

from custom_components.airfi.const import AIRFI_MODELS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger("mock-airfi")


class Fw320InputBlock(ModbusSequentialDataBlock):
    """Input register block that simulates firmware 3.2.0 behaviour.

    Firmware 3.2.0 has a hidden register at address 10 (1-based). Any bulk
    read request whose range includes address 10 returns a Modbus error,
    breaking multi-register reads that span across it.

    In pymodbus 3.x, ``ModbusDeviceContext`` adds +1 to the protocol address
    before calling ``getValues``, so protocol address 10 becomes internal
    address 11.  We override ``getValues`` (not ``validate``, which is never
    called in pymodbus 3.x) to intercept the read.
    """

    HIDDEN_ADDRESS = 10  # 1-based protocol address

    def getValues(self, address: int, count: int = 1) -> list[int] | list[bool] | ExcCodes:
        """Return ILLEGAL_ADDRESS when the read range crosses the hidden register."""
        # ModbusDeviceContext adds +1 to the protocol address before calling
        # getValues, so hidden protocol addr 10 → internal addr 11.
        hidden_internal = self.HIDDEN_ADDRESS + 1
        end_address = address + count - 1
        if address <= hidden_internal <= end_address:
            LOGGER.debug(
                "FW 3.2.0 simulation: rejecting read [%d..%d] (hidden reg %d, internal %d)",
                address - 1,
                end_address - 1,
                self.HIDDEN_ADDRESS,
                hidden_internal,
            )
            return ExcCodes.ILLEGAL_ADDRESS
        return super().getValues(address, count)


# Discovery constants (must match integration)
DISCOVERY_MULTICAST_GROUP = "239.255.100.200"
DISCOVERY_MULTICAST_PORT = 3000
DISCOVERY_DEVICE_PORT = 4000

# Register length profiles by modbus map version
REGISTER_PROFILES: dict[str, tuple[int, int]] = {
    "2.7.0": (42, 59),
    "2.5.0": (40, 58),
    "2.3.0": (40, 55),
    "2.1.0": (40, 51),
    "2.0.0": (40, 34),
    "1.5.0": (31, 12),
}


def version_to_register(version_str: str) -> int:
    """Convert version string '3.1.0' to register value 310."""
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version: {version_str}")
    return int(parts[0]) * 100 + int(parts[1]) * 10 + int(parts[2])


def get_model_name(model_id: int) -> str:
    """Return human-readable model name."""
    if model_id < 1:
        return "Unknown"
    try:
        index = (model_id - 1) // 2
        base_name = AIRFI_MODELS[index]
        variant = "L" if model_id % 2 == 1 else "R"
    except IndexError:
        return "Unknown"
    return f"Model {base_name.replace('{}', variant)}"


def build_input_registers(
    *,
    firmware: str,
    modbus: str,
    input_count: int,
) -> list[int]:
    """Build initial input register values with simulated sensor data.

    Register map (1-based addressing, stored 0-based):
        3x00001: Hardware version
        3x00002: Firmware version
        3x00003: Modbus map version
        3x00004: Outdoor air temperature (°C × 10)
        3x00005: (reserved)
        3x00006: Extract air temperature (°C × 10)
        3x00007: Exhaust air temperature (°C × 10)
        3x00008: Supply air temperature (°C × 10)
        3x00023: Relative humidity (0-100%)
    """
    values = [0] * input_count

    # 3x00001: Hardware version (e.g. 1.0.0 = 100)
    values[0] = 100
    # 3x00002: Firmware version
    values[1] = version_to_register(firmware)
    # 3x00003: Modbus map version
    values[2] = version_to_register(modbus)
    # 3x00004: Outdoor air temperature (e.g. 5.2°C = 52)
    values[3] = 52
    # 3x00005: reserved
    values[4] = 0
    # 3x00006: Extract air temperature (e.g. 21.5°C = 215)
    values[5] = 215
    # 3x00007: Exhaust air temperature (e.g. 8.3°C = 83)
    values[6] = 83
    # 3x00008: Supply air temperature (e.g. 20.0°C = 200)
    values[7] = 200

    # 3x00023: Relative humidity (45%)
    if input_count >= 23:
        values[22] = 45

    return values


def build_holding_registers(
    *,
    modbus: str,
    holding_count: int,
) -> list[int]:
    """Build initial holding register values with reasonable defaults.

    Register map (1-based addressing, stored 0-based):
        4x00001: Fan speed (1-5)
        4x00005: Target supply air temperature (°C × 10)
        4x00012: Fan active state (0=at-home, 1=away)
        4x00050: Minimum temperature (modbus >= 2.1.0)
        4x00051: Boosted cooling (modbus >= 2.5.0)
        4x00057: Sauna function (modbus >= 2.5.0)
        4x00058: Fireplace function (modbus >= 2.5.0)
    """
    values = [0] * holding_count

    # 4x00001: Fan speed = 3 (medium)
    values[0] = 3
    # 4x00005: Target temperature = 20.0°C
    if holding_count >= 5:
        values[4] = 200
    # 4x00012: Fan active = at-home (0)
    if holding_count >= 12:
        values[11] = 0

    # Modbus >= 2.1.0 features
    if pkg_version.parse(modbus) >= pkg_version.parse("2.1.0") and holding_count >= 50:
        # 4x00050: Minimum temperature = 15°C
        values[49] = 15

    # Modbus >= 2.5.0 features
    if pkg_version.parse(modbus) >= pkg_version.parse("2.5.0"):
        # 4x00051: Boosted cooling = off
        if holding_count >= 51:
            values[50] = 0
        # 4x00057: Sauna function = off
        if holding_count >= 57:
            values[56] = 0
        # 4x00058: Fireplace function = off
        if holding_count >= 58:
            values[57] = 0

    return values


def get_local_ip() -> str:
    """Get the local IP address used for outbound connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
    except OSError:
        return "127.0.0.1"
    else:
        return ip


def build_discovery_packet(
    *,
    local_ip: str,
    serial: int,
    model_id: int,
) -> bytes:
    """Build a 12-byte discovery packet matching the Airfi wire format.

    Format:
        [0-3]  IP address octets (little-endian / reversed)
        [4-5]  Device port (uint16 LE, always 4000)
        [6-9]  Serial number (uint32 LE)
        [10]   Unknown/constant (0x00)
        [11]   Model ID
    """
    octets = [int(o) for o in local_ip.split(".")]
    packet = bytearray(12)
    # IP reversed (little-endian octets)
    packet[0] = octets[3]
    packet[1] = octets[2]
    packet[2] = octets[1]
    packet[3] = octets[0]
    # Port 4000 LE
    struct.pack_into("<H", packet, 4, DISCOVERY_DEVICE_PORT)
    # Serial LE
    struct.pack_into("<I", packet, 6, serial)
    # Constant
    packet[10] = 0x00
    # Model ID
    packet[11] = model_id
    return bytes(packet)


async def send_discovery_packets(
    *,
    advertised_ip: str,
    serial: int,
    model_id: int,
    rate_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    """Periodically send UDP multicast discovery packets."""
    packet = build_discovery_packet(local_ip=advertised_ip, serial=serial, model_id=model_id)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    LOGGER.info(
        "Discovery: broadcasting on %s:%d every %.1fs (IP=%s, serial=%d, model=%d)",
        DISCOVERY_MULTICAST_GROUP,
        DISCOVERY_MULTICAST_PORT,
        rate_seconds,
        advertised_ip,
        serial,
        model_id,
    )

    try:
        while not stop_event.is_set():
            sock.sendto(packet, (DISCOVERY_MULTICAST_GROUP, DISCOVERY_MULTICAST_PORT))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=rate_seconds)
    finally:
        sock.close()
        LOGGER.info("Discovery sender stopped")


async def simulate_sensor_drift(
    context: ModbusServerContext,
    stop_event: asyncio.Event,
) -> None:
    """Slowly drift sensor values to simulate a live device."""
    while not stop_event.is_set():
        try:
            store = context[1]  # slave_id=1

            # Drift input registers (temperatures, 1-based addresses)
            for reg_addr in (4, 6, 7, 8):  # outdoor, extract, exhaust, supply
                current = store.getValues(4, reg_addr, count=1)  # ir uses fx=4
                if current:
                    val = current[0]
                    drift = random.randint(-2, 2)
                    new_val = max(0, min(65535, val + drift))
                    store.setValues(4, reg_addr, [new_val])

            # Drift humidity (1-based address 23)
            current_hum = store.getValues(4, 23, count=1)
            if current_hum:
                hum = current_hum[0]
                drift = random.randint(-1, 1)
                new_hum = max(20, min(80, hum + drift))
                store.setValues(4, 23, [new_hum])

        except Exception:  # noqa: BLE001
            LOGGER.warning("Sensor drift update failed", exc_info=True)

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=5.0)


async def run_mock_device(args: argparse.Namespace) -> None:
    """Run the mock Airfi device (Modbus server + discovery sender)."""
    serial = int(args.serial)
    firmware = args.firmware
    modbus = args.modbus
    model_id = int(args.model)
    port = 502
    advertised_ip = args.ip or get_local_ip()

    # Resolve register profile
    profile = None
    for ver_str, lengths in sorted(
        REGISTER_PROFILES.items(),
        key=lambda x: pkg_version.parse(x[0]),
        reverse=True,
    ):
        if pkg_version.parse(modbus) >= pkg_version.parse(ver_str):
            profile = lengths
            break
    if profile is None:
        profile = REGISTER_PROFILES["1.5.0"]

    input_count, holding_count = profile

    # Build register data
    input_values = build_input_registers(
        firmware=firmware,
        modbus=modbus,
        input_count=input_count,
    )
    holding_values = build_holding_registers(
        modbus=modbus,
        holding_count=holding_count,
    )

    LOGGER.info("=" * 60)
    LOGGER.info("  Mock Airfi Air Handling Unit")
    LOGGER.info("=" * 60)
    LOGGER.info("  Serial:        %d", serial)
    LOGGER.info("  Model:         %s (ID=%d)", get_model_name(model_id), model_id)
    LOGGER.info("  Firmware:      %s", firmware)
    LOGGER.info("  Modbus map:    %s", modbus)
    LOGGER.info("  Registers:     %d input, %d holding", input_count, holding_count)
    LOGGER.info("  Modbus port:   %d", port)
    LOGGER.info("  Bind address:  %s", args.ip or "0.0.0.0 (all interfaces)")
    LOGGER.info("  Discovery IP:  %s", advertised_ip)
    LOGGER.info("=" * 60)

    # Create Modbus datastore
    # pymodbus 3.x has an internal +1 offset: reading address N returns
    # array[N+1] from a block starting at address 0.  Prepend two dummy
    # elements so that protocol address 1 maps to our values[0].

    # Firmware 3.2.0 simulation: use a custom block that hides register 10
    if firmware == "3.2.0":
        LOGGER.warning("Firmware 3.2.0: input register 10 is hidden (bulk reads crossing it will fail)")
        ir_block = Fw320InputBlock(0, [0, 0, *input_values])
    else:
        ir_block = ModbusSequentialDataBlock(0, [0, 0, *input_values])
    hr_block = ModbusSequentialDataBlock(0, [0, 0, *holding_values])

    slave_context = ModbusDeviceContext(
        ir=ir_block,
        hr=hr_block,
    )
    server_context = ModbusServerContext(
        devices={1: slave_context},
        single=False,
    )

    # Prepare stop event and signal handlers
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        LOGGER.info("Shutting down...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Determine bind address: use --ip if provided and available, else 0.0.0.0
    bind_addr = args.ip or "0.0.0.0"
    if args.ip:
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind((args.ip, port))
            test_sock.close()
        except OSError as exc:
            if exc.errno == 99:  # EADDRNOTAVAIL
                LOGGER.error(
                    "IP address %s is not assigned to any local interface. "
                    "Use a loopback alias like 127.0.0.2 instead.",
                    args.ip,
                )
            else:
                LOGGER.error("Cannot bind to %s:%d: %s", args.ip, port, exc)
            raise SystemExit(1) from exc

    # Create Modbus TCP server bound to the resolved address
    server = ModbusTcpServer(
        context=server_context,
        address=(bind_addr, port),
    )

    # Start server with no fallback — if binding fails, it was reported above
    await server.serve_forever(background=True)

    # Start discovery + sensor drift tasks
    discovery_task = asyncio.create_task(
        send_discovery_packets(
            advertised_ip=advertised_ip,
            serial=serial,
            model_id=model_id,
            rate_seconds=2.0,
            stop_event=stop_event,
        )
    )
    drift_task = asyncio.create_task(simulate_sensor_drift(server_context, stop_event))

    LOGGER.info("Modbus TCP server listening on %s:%d (slave_id=1)", bind_addr, port)

    try:
        await stop_event.wait()
    finally:
        await server.shutdown()
        discovery_task.cancel()
        drift_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await discovery_task
        with contextlib.suppress(asyncio.CancelledError):
            await drift_task

    LOGGER.info("Mock device stopped")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Mock Airfi air handling unit (Modbus TCP server + UDP discovery)")
    parser.add_argument("--serial", default="12345678", help="Device serial number (default: 12345678)")
    parser.add_argument("--firmware", default="3.1.0", help="Firmware version (default: 3.1.0)")
    parser.add_argument("--modbus", default="2.7.0", help="Modbus register map version (default: 2.7.0)")
    parser.add_argument("--model", type=int, default=3, help="Model ID 1-38 (default: 3 = '150 L')")
    parser.add_argument(
        "--ip",
        default=None,
        help="IP address to advertise in discovery packets (default: auto-detect)",
    )
    return parser.parse_args()


def main() -> int:
    """Entry point."""
    args = parse_args()

    # Validate inputs
    try:
        version_to_register(args.firmware)
        version_to_register(args.modbus)
    except ValueError as e:
        LOGGER.error("Invalid version format: %s", e)
        return 1

    if int(args.model) < 1 or int(args.model) > 38:
        LOGGER.error("Model ID must be 1-38, got %d", int(args.model))
        return 1

    try:
        asyncio.run(run_mock_device(args))
    except KeyboardInterrupt:
        LOGGER.info("Interrupted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
