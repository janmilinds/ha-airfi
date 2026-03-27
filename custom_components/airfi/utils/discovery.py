"""Airfi device discovery via UDP multicast."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import socket
import struct

from custom_components.airfi.const import (
    AIRFI_MODELS,
    DISCOVERY_DEVICE_PORT,
    DISCOVERY_MULTICAST_GROUP,
    DISCOVERY_MULTICAST_PORT,
    DISCOVERY_PACKET_TIMEOUT_SECONDS,
    DISCOVERY_QUIET_PERIOD_SECONDS,
)

LOGGER = logging.getLogger(__name__)


def get_model_name(model_id: int) -> str:
    """Return human-readable model name (e.g., 'Model 60 L', 'Model 100 R')."""
    try:
        index = (model_id - 1) // 2
        base_name = AIRFI_MODELS[index]
        variant = "L" if model_id % 2 == 1 else "R"
    except (IndexError, ZeroDivisionError):
        return "Unknown"
    else:
        return f"Model {base_name.replace('{}', variant)}"


@dataclass
class AirfiDiscoveredDevice:
    """Represents a discovered Airfi device."""

    host: str
    serial: int
    model_id: int

    @property
    def model_name(self) -> str:
        """Get human-readable model name (e.g., 'Model 60 L', 'Model 100 R')."""
        return get_model_name(self.model_id)

    @property
    def unique_key(self) -> str:
        """Return a unique identifier for deduplication.

        Uses serial only, since serial is the true device identifier.
        Host (IP) can change but serial remains constant.
        """
        return str(self.serial)


class AirfiDiscoveryService:
    """Service to discover Airfi devices via UDP multicast."""

    def __init__(self) -> None:
        """Initialize discovery service."""
        self.discovered: dict[str, AirfiDiscoveredDevice] = {}
        self.sock: socket.socket | None = None

    def _parse_packet(self, data: bytes, sender_ip: str) -> AirfiDiscoveredDevice | None:
        """Parse Airfi discovery packet.

        Packet format (variable length, minimum 12 bytes):
        - Bytes 0-3: Device IPv4 address (little-endian octets)
        - Bytes 4-5: Device response port (little-endian uint16, must be 4000)
        - Bytes 6-9: Serial number (little-endian uint32)
        - Byte 10: Unknown/constant
        - Byte 11: Model ID

        Args:
            data: Raw packet bytes
            sender_ip: Source IP of sender

        Returns:
            Parsed device or None if invalid

        """
        if len(data) < 12:
            LOGGER.debug("Packet too short: %d bytes", len(data))
            return None

        try:
            # Validate device port (bytes 4-5, little-endian uint16 must be 4000)
            device_port = struct.unpack_from("<H", data, 4)[0]
            if device_port != DISCOVERY_DEVICE_PORT:
                LOGGER.debug("Ignoring non-Airfi packet (port %d)", device_port)
                return None

            packet_ip = socket.inet_ntoa(bytes(reversed(data[:4])))

            # Parse serial (bytes 6-9, little-endian uint32)
            serial = struct.unpack_from("<I", data, 6)[0]

            # Parse model ID (byte 11)
            model_id = data[11]

            # Validate model_id is in reasonable range (1-8 for MVP)
            if model_id < 1 or model_id > 255:
                LOGGER.debug("Invalid model_id: %d", model_id)
                return None

            host = packet_ip if packet_ip != "0.0.0.0" else sender_ip
            return AirfiDiscoveredDevice(host=host, serial=serial, model_id=model_id)

        except struct.error as err:
            LOGGER.debug("Failed to parse packet: %s", err)
            return None

    def _create_socket(self) -> socket.socket:
        """Create and configure UDP multicast socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to multicast group
        sock.bind(("", DISCOVERY_MULTICAST_PORT))

        # Join multicast group
        mreq = socket.inet_aton(DISCOVERY_MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Set non-blocking
        sock.setblocking(False)

        return sock

    async def async_scan(
        self,
        timeout_seconds: int = DISCOVERY_PACKET_TIMEOUT_SECONDS,
        quiet_period_seconds: float = DISCOVERY_QUIET_PERIOD_SECONDS,
    ) -> list[AirfiDiscoveredDevice]:
        """Scan for Airfi devices and return unique discovered devices.

        Stops early once no new device has been seen for ``quiet_period_seconds``
        after the first device is found, instead of always waiting the full timeout.

        Args:
            timeout_seconds: Maximum scan duration in seconds.
            quiet_period_seconds: Stop scanning this many seconds after the last
                device was found (only applies once at least one device is known).

        Returns:
            List of discovered devices

        """
        self.discovered = {}
        last_found_time: float | None = None

        try:
            self.sock = self._create_socket()
        except OSError as err:
            LOGGER.error("Failed to create multicast socket: %s", err)
            return []

        try:
            end_time = asyncio.get_event_loop().time() + timeout_seconds

            while True:
                now = asyncio.get_event_loop().time()
                remaining = end_time - now
                if remaining <= 0:
                    break

                # Stop early once the network has been quiet for quiet_period_seconds
                if last_found_time is not None and (now - last_found_time) >= quiet_period_seconds:
                    LOGGER.debug(
                        "Discovery stopping after quiet period (found %d device(s))",
                        len(self.discovered),
                    )
                    break

                try:
                    # Use asyncio wait_for to add timeout to socket.recvfrom
                    data, addr = await asyncio.wait_for(
                        self._async_receive(),
                        timeout=min(remaining, 0.5),
                    )

                    if data and len(addr) >= 1:
                        sender_ip = addr[0]
                        device = self._parse_packet(data, sender_ip)

                        if device:
                            # Store by unique key (deduplication)
                            self.discovered[device.unique_key] = device
                            last_found_time = asyncio.get_event_loop().time()
                            LOGGER.debug("Discovered device: %s (model %s)", device.host, device.model_name)

                except TimeoutError:
                    # Continue scanning
                    continue

        except Exception as err:  # noqa: BLE001
            LOGGER.error("Discovery scan error: %s", err)

        finally:
            if self.sock:
                self.sock.close()
                self.sock = None

        return list(self.discovered.values())

    async def _async_receive(self) -> tuple[bytes, tuple[str, int]]:
        """Receive a single UDP packet asynchronously."""
        assert self.sock is not None, "Socket must be initialized"
        loop = asyncio.get_event_loop()
        return await loop.sock_recvfrom(self.sock, 1024)

    def get_discovered_devices(self) -> list[AirfiDiscoveredDevice]:
        """Get list of discovered devices."""
        return list(self.discovered.values())


__all__ = [
    "AirfiDiscoveredDevice",
    "AirfiDiscoveryService",
    "get_model_name",
]
