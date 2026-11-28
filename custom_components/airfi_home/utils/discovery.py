"""Airfi device discovery via UDP multicast."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
import socket
import struct
from typing import override

from custom_components.airfi_home.const import (
    AIRFI_MODELS,
    DISCOVERY_DEVICE_PORT,
    DISCOVERY_LISTENER_RETRY_SECONDS,
    DISCOVERY_MULTICAST_GROUP,
    DISCOVERY_MULTICAST_PORT,
    DISCOVERY_PACKET_TIMEOUT_SECONDS,
    DISCOVERY_QUIET_PERIOD_SECONDS,
    DOMAIN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.hass_dict import HassKey

LOGGER = logging.getLogger(__name__)


def get_model_name(model_id: int) -> str | None:
    """Return the model name, such as 'Model 60 L' or 'Model 100 R', or None for a model ID not in the table."""
    index, right_handed = divmod(model_id - 1, 2)
    if not 0 <= index < len(AIRFI_MODELS):
        return None
    return f"Model {AIRFI_MODELS[index].replace('{}', 'R' if right_handed else 'L')}"


def unit_title(model_name: str | None) -> str:
    """Return the name a unit gets unless the user gives one: Airfi and its model, when known."""
    return f"Airfi {model_name}" if model_name else "Airfi"


@dataclass
class AirfiDiscoveredDevice:
    """Represents a discovered Airfi device."""

    host: str
    serial: int
    model_id: int

    @property
    def model_name(self) -> str | None:
        """Return the model name, such as 'Model 60 L', or None for a model ID not in the table."""
        return get_model_name(self.model_id)

    @property
    def unique_key(self) -> str:
        """Return a unique identifier for deduplication.

        Uses serial only, since serial is the true device identifier.
        Host (IP) can change but serial remains constant.
        """
        return str(self.serial)


def parse_announcement(data: bytes, sender_ip: str) -> AirfiDiscoveredDevice | None:
    """Parse an Airfi announcement.

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

        if model_id == 0:
            LOGGER.debug("Invalid model_id: %d", model_id)
            return None

        host = packet_ip if packet_ip != "0.0.0.0" else sender_ip
        return AirfiDiscoveredDevice(host=host, serial=serial, model_id=model_id)

    except struct.error as err:
        LOGGER.debug("Failed to parse packet: %s", err)
        return None


def create_discovery_socket() -> socket.socket:
    """Open a non-blocking UDP socket that has joined the announcement multicast group."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((DISCOVERY_MULTICAST_GROUP, DISCOVERY_MULTICAST_PORT))
        mreq = socket.inet_aton(DISCOVERY_MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
    except OSError:
        sock.close()
        raise

    return sock


class AirfiDiscoveryService:
    """Service to discover Airfi devices via UDP multicast."""

    def __init__(self) -> None:
        """Initialize discovery service."""
        self.discovered: dict[str, AirfiDiscoveredDevice] = {}
        self.sock: socket.socket | None = None

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

        Raises:
            OSError: If socket creation or binding fails (e.g., due to network issues or permissions).

        """
        self.discovered = {}
        last_found_time: float | None = None

        self.sock = create_discovery_socket()

        try:
            end_time = asyncio.get_running_loop().time() + timeout_seconds

            while True:
                now = asyncio.get_running_loop().time()
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
                        device = parse_announcement(data, sender_ip)

                        if device:
                            # Store by unique key (deduplication)
                            self.discovered[device.unique_key] = device
                            last_found_time = asyncio.get_running_loop().time()
                            LOGGER.debug("Discovered device: %s (model %s)", device.host, device.model_name)

                except TimeoutError:
                    # Continue scanning
                    continue

        except OSError as err:
            LOGGER.error("Discovery scan error: %s", err)

        finally:
            if self.sock:
                self.sock.close()
                self.sock = None

        return list(self.discovered.values())

    async def _async_receive(self) -> tuple[bytes, tuple[str, int]]:
        """Receive a single UDP packet asynchronously."""
        assert self.sock is not None, "Socket must be initialized"
        loop = asyncio.get_running_loop()
        return await loop.sock_recvfrom(self.sock, 1024)

    def get_discovered_devices(self) -> list[AirfiDiscoveredDevice]:
        """Get list of discovered devices."""
        return list(self.discovered.values())


class AirfiDiscoveryListener(asyncio.DatagramProtocol):
    """
    Listen for unit announcements for as long as Home Assistant runs.

    Reports a unit only when it is new or announces itself from another address than before, since each unit
    announces itself every few seconds.
    """

    def __init__(self, hass: HomeAssistant, on_announcement: Callable[[AirfiDiscoveredDevice], None]) -> None:
        """Initialize the listener; nothing is opened before `async_start`."""
        self._hass = hass
        self._on_announcement = on_announcement
        self._transport: asyncio.DatagramTransport | None = None
        self._cancel_retry: CALLBACK_TYPE | None = None
        self._devices: dict[str, AirfiDiscoveredDevice] = {}

    async def async_start(self) -> None:
        """Join the multicast group, or try again later when the network is not ready."""
        try:
            sock = create_discovery_socket()
        except OSError as err:
            LOGGER.debug(
                "Discovery listener could not open its socket: %s; trying again in %s seconds",
                err,
                DISCOVERY_LISTENER_RETRY_SECONDS,
            )
            self._cancel_retry = async_call_later(self._hass, DISCOVERY_LISTENER_RETRY_SECONDS, self._async_retry)
            return
        self._transport, _ = await self._hass.loop.create_datagram_endpoint(lambda: self, sock=sock)

    async def _async_retry(self, _now: datetime) -> None:
        """Try to open the socket again."""
        self._cancel_retry = None
        await self.async_start()

    @callback
    def async_stop(self, _event: Event | None = None) -> None:
        """Leave the multicast group and cancel a pending retry."""
        if self._cancel_retry is not None:
            self._cancel_retry()
            self._cancel_retry = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @override
    def datagram_received(self, data: bytes, addr: tuple[str | int, ...]) -> None:
        """Record an announcement and report the unit when it is new or has moved."""
        if (device := parse_announcement(data, str(addr[0]))) is None:
            return
        previous = self._devices.pop(device.unique_key, None)
        self._devices[device.unique_key] = device
        if previous is None or previous.host != device.host:
            self._on_announcement(device)

    @callback
    def async_forget(self, serial: str) -> None:
        """Forget a unit, so its next announcement reports it again."""
        self._devices.pop(serial, None)

    def device_with_serial(self, serial: str) -> AirfiDiscoveredDevice | None:
        """Return the unit with this serial number as it last announced itself."""
        return self._devices.get(serial)

    def device_at(self, host: str) -> AirfiDiscoveredDevice | None:
        """Return the unit that last announced itself from this address."""
        return next((device for device in reversed(self._devices.values()) if device.host == host), None)


DATA_DISCOVERY_LISTENER: HassKey[AirfiDiscoveryListener] = HassKey(f"{DOMAIN}_discovery_listener")


def announced_device_at(hass: HomeAssistant, host: str) -> AirfiDiscoveredDevice | None:
    """Return the unit the running listener last heard from this address, if any."""
    listener = hass.data.get(DATA_DISCOVERY_LISTENER)
    return listener.device_at(host) if listener else None


def announced_device_with_serial(hass: HomeAssistant, serial: str) -> AirfiDiscoveredDevice | None:
    """Return the unit with this serial number as the running listener last heard it, if at all."""
    listener = hass.data.get(DATA_DISCOVERY_LISTENER)
    return listener.device_with_serial(serial) if listener else None


__all__ = [
    "DATA_DISCOVERY_LISTENER",
    "AirfiDiscoveredDevice",
    "AirfiDiscoveryListener",
    "AirfiDiscoveryService",
    "announced_device_at",
    "announced_device_with_serial",
    "create_discovery_socket",
    "get_model_name",
    "parse_announcement",
]
