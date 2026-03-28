"""Modbus TCP API client for Airfi devices."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pymodbus.client import ModbusTcpClient

_LOGGER = logging.getLogger(__name__)
_MODBUS_DUMP_LOGGER = logging.getLogger("custom_components.airfi.modbus")

MODBUS_READ_LIMIT = 30
MODBUS_SLAVE_ID = 1
REGISTER_LENGTHS_BY_MAP_VERSION: tuple[tuple[tuple[int, int, int], tuple[int, int]], ...] = (
    ((2, 7, 0), (42, 59)),
    ((2, 5, 0), (40, 58)),
    ((2, 3, 0), (40, 55)),
    ((2, 1, 0), (40, 51)),
    ((2, 0, 0), (40, 34)),
    ((1, 5, 0), (31, 12)),
)


class AirfiApiClientError(Exception):
    """Base exception for Airfi API client errors."""


class AirfiApiClientCommunicationError(
    AirfiApiClientError,
):
    """Exception raised for Modbus communication errors."""


def _as_version_tuple(value: int) -> tuple[int, int, int]:
    """Convert register value to semantic version tuple.

    Example: 270 -> (2, 7, 0)
    """
    digits = str(max(0, value))
    if len(digits) >= 3:
        return int(digits[0]), int(digits[1]), int(digits[2])
    if len(digits) == 2:
        return int(digits[0]), int(digits[1]), 0
    return int(digits[0]), 0, 0


def _as_version_string(value: int) -> str:
    """Convert register value to version string."""
    version = _as_version_tuple(value)
    return f"{version[0]}.{version[1]}.{version[2]}"


def _register_lengths(map_version_raw: int) -> tuple[int, int]:
    """Return input/holding register lengths based on modbus map version."""
    map_version = _as_version_tuple(map_version_raw)
    for min_version, lengths in REGISTER_LENGTHS_BY_MAP_VERSION:
        if map_version >= min_version:
            return lengths

    return REGISTER_LENGTHS_BY_MAP_VERSION[-1][1]


class AirfiApiClient:
    """API client that reads and writes Airfi Modbus registers."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 2.0,
    ) -> None:
        """Initialize the Modbus client configuration."""
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._firmware_version: str | None = None
        self._modbus_map_version: str | None = None
        self._input_register_length: int | None = None
        self._holding_register_length: int | None = None

    async def async_test_connection(self) -> None:
        """Validate that the device is reachable and responds to lookup read."""
        await self._async_read_registers(start_address=1, length=3, register_type="input")

    async def async_get_lookup_registers(self) -> list[int]:
        """Read device lookup registers (firmware and modbus map version).

        Returns:
            List of lookup register values [unknown, firmware_version, modbus_map_version].

        Raises:
            AirfiApiClientCommunicationError: If unable to read from device.
        """
        return await self._async_read_registers(start_address=1, length=3, register_type="input")

    def set_register_profile(
        self,
        *,
        firmware_version: str,
        modbus_map_version: str,
        input_register_length: int,
        holding_register_length: int,
    ) -> None:
        """Set cached register profile resolved at setup time."""
        self._firmware_version = firmware_version
        self._modbus_map_version = modbus_map_version
        self._input_register_length = input_register_length
        self._holding_register_length = holding_register_length

    def update_host(self, host: str) -> None:
        """Update target host after rediscovery finds the same device at a new IP."""
        self._host = host

    async def _async_ensure_register_profile(self) -> None:
        """Initialize register profile once if coordinator did not preconfigure it."""
        if (
            self._firmware_version is not None
            and self._modbus_map_version is not None
            and self._input_register_length is not None
            and self._holding_register_length is not None
        ):
            return

        input_lookup = await self.async_get_lookup_registers()
        firmware_raw = input_lookup[1] if len(input_lookup) > 1 else 0
        modbus_map_raw = input_lookup[2] if len(input_lookup) > 2 else 0
        input_length, holding_length = _register_lengths(modbus_map_raw)
        self.set_register_profile(
            firmware_version=_as_version_string(firmware_raw),
            modbus_map_version=_as_version_string(modbus_map_raw),
            input_register_length=input_length,
            holding_register_length=holding_length,
        )

    async def async_get_data(self) -> Any:
        """Read Airfi device state from Modbus registers."""
        await self._async_ensure_register_profile()

        input_length = self._input_register_length or 0
        holding_length = self._holding_register_length or 0
        holding_registers = await self._async_read_registers(
            start_address=1,
            length=holding_length,
            register_type="holding",
        )
        input_registers = await self._async_read_registers(
            start_address=1,
            length=input_length,
            register_type="input",
        )
        _MODBUS_DUMP_LOGGER.debug(
            "Input registers (length=%d): %s",
            len(input_registers),
            input_registers,
        )
        _MODBUS_DUMP_LOGGER.debug(
            "Holding registers (length=%d): %s",
            len(holding_registers),
            holding_registers,
        )

        return {
            "firmware_version": self._firmware_version or "0.0.0",
            "modbus_map_version": self._modbus_map_version or "0.0.0",
            "holding_registers": holding_registers,
            "input_registers": input_registers,
            "lookup_registers": [],
            "model": "Airfi",
        }

    async def _async_read_registers(
        self,
        start_address: int,
        length: int,
        register_type: str,
    ) -> list[int]:
        """Read registers using chunked Modbus requests."""
        values: list[int] = []

        for offset in range(0, length, MODBUS_READ_LIMIT):
            read_start = start_address + offset
            read_length = min(MODBUS_READ_LIMIT, length - offset)
            chunk = await self._async_read_chunk(read_start, read_length, register_type)
            values.extend(chunk)

        return values

    async def _async_read_chunk(self, start_address: int, length: int, register_type: str) -> list[int]:
        """Read one register chunk in an executor thread."""

        def _read() -> list[int]:
            _LOGGER.debug(
                "Reading %s registers: start_address=%d, length=%d",
                register_type,
                start_address,
                length,
            )
            client = ModbusTcpClient(self._host, port=self._port, timeout=self._timeout_seconds)
            if not client.connect():
                msg = f"Unable to connect to device at {self._host}:{self._port}"
                raise AirfiApiClientCommunicationError(msg)

            try:
                if register_type == "holding":
                    response = self._read_holding_registers(client, start_address, length)
                else:
                    response = self._read_input_registers(client, start_address, length)

                if response.isError():
                    msg = f"Modbus read error for {register_type} registers at {start_address}"
                    raise AirfiApiClientCommunicationError(msg)

                registers = getattr(response, "registers", None)
                if not isinstance(registers, list) or len(registers) != length:
                    msg = f"Unexpected Modbus response length for {register_type} registers at {start_address}"
                    raise AirfiApiClientCommunicationError(msg)

                return [int(value) for value in registers]
            finally:
                client.close()

        try:
            async with asyncio.timeout(10):
                return await asyncio.to_thread(_read)
        except TimeoutError as exception:
            msg = f"Timeout while reading Modbus registers: {exception}"
            raise AirfiApiClientCommunicationError(msg) from exception
        except AirfiApiClientError:
            raise
        except Exception as exception:
            msg = f"Unexpected Modbus read failure: {exception}"
            raise AirfiApiClientError(msg) from exception

    async def async_write_holding_register(self, address: int, value: int) -> None:
        """Write a single Airfi holding register over Modbus TCP.

        Args:
            address: 1-based Modbus holding register address (e.g. 1 for 4x00001).
            value: Integer value to write.

        Raises:
            AirfiApiClientCommunicationError: If the connection or write fails.
            AirfiApiClientError: For unexpected failures.
        """

        def _write() -> None:
            _LOGGER.debug("Writing holding register: address=%d, value=%d", address, value)
            client = ModbusTcpClient(self._host, port=self._port, timeout=self._timeout_seconds)
            if not client.connect():
                msg = f"Unable to connect to device at {self._host}:{self._port}"
                raise AirfiApiClientCommunicationError(msg)
            try:
                response = client.write_register(address, value, device_id=MODBUS_SLAVE_ID)
                if response.isError():
                    msg = f"Modbus write error for holding register at {address}"
                    raise AirfiApiClientCommunicationError(msg)
            finally:
                client.close()

        try:
            async with asyncio.timeout(10):
                await asyncio.to_thread(_write)
        except TimeoutError as exception:
            msg = f"Timeout while writing Modbus register: {exception}"
            raise AirfiApiClientCommunicationError(msg) from exception
        except AirfiApiClientError:
            raise
        except Exception as exception:
            msg = f"Unexpected Modbus write failure: {exception}"
            raise AirfiApiClientError(msg) from exception

    @staticmethod
    def _read_holding_registers(client: ModbusTcpClient, start_address: int, length: int) -> Any:
        """Read holding registers."""
        return client.read_holding_registers(start_address, count=length, device_id=MODBUS_SLAVE_ID)

    @staticmethod
    def _read_input_registers(client: ModbusTcpClient, start_address: int, length: int) -> Any:
        """Read input registers."""
        return client.read_input_registers(start_address, count=length, device_id=MODBUS_SLAVE_ID)
