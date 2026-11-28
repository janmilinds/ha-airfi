"""Modbus TCP API client for Airfi devices."""

import asyncio
from collections.abc import Callable
import logging
import threading
from typing import Any
import weakref

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from custom_components.airfi_home.const import DEFAULT_MODBUS_ID, LOGGER
from custom_components.airfi_home.utils import version_string, version_tuple

from .register_map import register_lengths

_LOGGER = logging.getLogger(__name__)
_MODBUS_DUMP_LOGGER = LOGGER.getChild("modbus")

_DEVICE_LOCKS: weakref.WeakValueDictionary[tuple[str, int], threading.Lock] = weakref.WeakValueDictionary()

DEVICE_LOCK_POLL_SECONDS = 0.1
MODBUS_READ_LIMIT = 30


class AirfiApiClientError(Exception):
    """Base exception for Airfi API client errors."""


class AirfiApiClientConnectionError(AirfiApiClientError):
    """Exception raised when the device is unreachable at the TCP level.

    This includes failed TCP connections and timeouts. A connection error
    suggests the device may have changed IP address and warrants a
    rediscovery attempt.
    """


class AirfiApiClientNoResponseError(AirfiApiClientConnectionError):
    """Exception raised when the unit accepts the connection but does not answer.

    The unit stays silent towards a request for another Modbus ID, and sometimes closes the connection a few seconds
    later, so this is what a wrong Modbus ID looks like. To the coordinator it is still an unreachable unit.
    """


class AirfiApiClientModbusError(AirfiApiClientError):
    """Exception raised for Modbus protocol-level errors.

    The TCP connection succeeded but the Modbus exchange failed, for
    example due to an error response or unexpected register count. The
    device is reachable, so rediscovery is not warranted.
    """


def _device_lock_for(host: str, port: int) -> threading.Lock:
    """Return the lock shared by every client that talks to the unit at this address."""
    key = (host.strip().lower().rstrip("."), port)
    lock = _DEVICE_LOCKS.get(key)
    if lock is None:
        lock = threading.Lock()
        _DEVICE_LOCKS[key] = lock
    return lock


class AirfiApiClient:
    """API client that reads and writes Airfi Modbus registers, one connection to an address at a time."""

    def __init__(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 2.0,
        *,
        unit_id: int = DEFAULT_MODBUS_ID,
        retries: int = 3,
    ) -> None:
        """Initialize the Modbus client configuration.

        Args:
            host: Address of the unit.
            port: Modbus TCP port of the unit.
            timeout_seconds: How long to wait for each answer.
            unit_id: Modbus ID the unit answers to.
            retries: How many times an unanswered request is sent again.
        """
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._unit_id = unit_id
        self._retries = retries
        self._firmware_version: str | None = None
        self._modbus_register_version: str | None = None
        self._input_register_length: int | None = None
        self._holding_register_length: int | None = None
        self._lock = asyncio.Lock()
        self._device_lock = _device_lock_for(host, port)

    async def async_get_lookup_registers(self) -> list[int]:
        """Read device lookup registers (firmware and modbus map version).

        Returns:
            List of lookup register values [unknown, firmware_version, modbus_register_version].

        Raises:
            AirfiApiClientConnectionError: If unable to reach the device.
            AirfiApiClientModbusError: If the Modbus exchange fails.
        """
        async with self._lock:
            return await self._async_read_registers(start_address=1, length=3, register_type="input")

    def set_register_profile(
        self,
        *,
        firmware_version: str,
        modbus_register_version: str,
        input_register_length: int,
        holding_register_length: int,
    ) -> None:
        """Set cached register profile resolved at setup time."""
        self._firmware_version = firmware_version
        self._modbus_register_version = modbus_register_version
        self._input_register_length = input_register_length
        self._holding_register_length = holding_register_length

    def update_host(self, host: str) -> None:
        """Update target host after rediscovery finds the same device at a new IP."""
        self._host = host
        self._device_lock = _device_lock_for(host, self._port)

    async def _async_ensure_register_profile(self) -> None:
        """Initialize register profile once if coordinator did not preconfigure it."""
        if (
            self._firmware_version is not None
            and self._modbus_register_version is not None
            and self._input_register_length is not None
            and self._holding_register_length is not None
        ):
            return

        input_lookup = await self._async_read_registers(start_address=1, length=3, register_type="input")
        firmware_raw = input_lookup[1] if len(input_lookup) > 1 else 0
        modbus_map_raw = input_lookup[2] if len(input_lookup) > 2 else 0
        input_length, holding_length = register_lengths(version_tuple(modbus_map_raw))
        self.set_register_profile(
            firmware_version=version_string(firmware_raw),
            modbus_register_version=version_string(modbus_map_raw),
            input_register_length=input_length,
            holding_register_length=holding_length,
        )

    async def async_get_data(self) -> Any:
        """Read Airfi device state from Modbus registers.

        Uses a single TCP connection for all register reads within the poll
        cycle to minimise connection overhead.
        """
        async with self._lock:
            await self._async_ensure_register_profile()
            holding_registers, input_registers = await self._async_read_all_registers(
                input_length=self._input_register_length or 0,
                holding_length=self._holding_register_length or 0,
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

        # Read firmware_version live from input register 2 (index 1) so that
        # runtime firmware changes are detected by the coordinator within one
        # polling cycle. Fall back to the cached value only if the register
        # list is unexpectedly short.
        live_firmware_version = (
            version_string(input_registers[1]) if len(input_registers) > 1 else self._firmware_version or "0.0.0"
        )

        # Read modbus_register_version live from input register 3 (index 2)
        # so that runtime modbus map changes are detected.
        live_modbus_register_version = (
            version_string(input_registers[2]) if len(input_registers) > 2 else self._modbus_register_version or "0.0.0"
        )

        return {
            "firmware_version": live_firmware_version,
            "modbus_register_version": live_modbus_register_version,
            "holding_registers": holding_registers,
            "input_registers": input_registers,
        }

    async def _async_run_on_device[T](self, request: Callable[[], T], *, timeout: float, action: str) -> T:
        """Run a blocking request in a worker thread, never alongside another connection to the same address.

        The thread lock is shared by every client for that address, so the config flow's connection check and a
        reloaded entry's new client wait as well. It also holds while a thread outlives the timeout or cancellation of
        the task awaiting it, which the asyncio lock cannot. A request abandoned while it waited is dropped without
        reaching the unit, so a write reported as failed is never sent later, and its thread does not wait out the lock.

        Raises:
            AirfiApiClientNoResponseError: If the timeout passes after the request reached the unit.
            AirfiApiClientConnectionError: If it passes while the request still waits for another connection to end.
        """
        abandoned = threading.Event()
        started = threading.Event()
        device_lock = self._device_lock

        def _run() -> T:
            while not device_lock.acquire(timeout=DEVICE_LOCK_POLL_SECONDS):
                if abandoned.is_set():
                    msg = "Request abandoned while waiting for the device"
                    raise AirfiApiClientConnectionError(msg)
            try:
                if abandoned.is_set():
                    msg = "Request abandoned before it reached the device"
                    raise AirfiApiClientConnectionError(msg)
                started.set()
                return request()
            finally:
                device_lock.release()

        try:
            async with asyncio.timeout(timeout):
                try:
                    return await asyncio.to_thread(_run)
                except asyncio.CancelledError:
                    abandoned.set()
                    raise
        except TimeoutError as exception:
            msg = f"Timeout while {action}: {exception}"
            if started.is_set():
                raise AirfiApiClientNoResponseError(msg) from exception
            raise AirfiApiClientConnectionError(msg) from exception

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
            client = self._connect()

            try:
                response = self._request_registers(client, register_type, start_address, length)

                if response.isError():
                    msg = f"Modbus read error for {register_type} registers at {start_address}"
                    raise AirfiApiClientModbusError(msg)

                registers = getattr(response, "registers", None)
                if not isinstance(registers, list) or len(registers) != length:
                    msg = f"Unexpected Modbus response length for {register_type} registers at {start_address}"
                    raise AirfiApiClientModbusError(msg)

                return [int(value) for value in registers]
            finally:
                client.close()

        try:
            return await self._async_run_on_device(_read, timeout=10, action="reading Modbus registers")
        except AirfiApiClientError:
            raise
        except Exception as exception:
            msg = f"Unexpected Modbus read failure: {exception}"
            raise AirfiApiClientError(msg) from exception

    async def _async_read_all_registers(
        self,
        *,
        input_length: int,
        holding_length: int,
    ) -> tuple[list[int], list[int]]:
        """Read all holding and input registers in a single TCP connection.

        This reduces connection overhead from ~4 connections per poll to 1.
        """

        def _read_all() -> tuple[list[int], list[int]]:
            client = self._connect()
            try:
                holding = self._read_registers_sync(client, 1, holding_length, "holding")
                inputs = self._read_registers_sync(client, 1, input_length, "input")
                return holding, inputs
            finally:
                client.close()

        holding_chunks = max(1, (holding_length + MODBUS_READ_LIMIT - 1) // MODBUS_READ_LIMIT)
        input_chunks = max(1, (input_length + MODBUS_READ_LIMIT - 1) // MODBUS_READ_LIMIT)
        poll_timeout = (holding_chunks + input_chunks) * self._timeout_seconds

        try:
            return await self._async_run_on_device(_read_all, timeout=poll_timeout, action="reading Modbus registers")
        except AirfiApiClientError:
            raise
        except Exception as exception:
            msg = f"Unexpected Modbus read failure: {exception}"
            raise AirfiApiClientError(msg) from exception

    def _read_registers_sync(
        self,
        client: ModbusTcpClient,
        start_address: int,
        length: int,
        register_type: str,
    ) -> list[int]:
        """Read registers synchronously with chunking on an existing connection."""
        values: list[int] = []
        for offset in range(0, length, MODBUS_READ_LIMIT):
            read_start = start_address + offset
            read_length = min(MODBUS_READ_LIMIT, length - offset)
            _LOGGER.debug(
                "Reading %s registers: start_address=%d, length=%d",
                register_type,
                read_start,
                read_length,
            )
            response = self._request_registers(client, register_type, read_start, read_length)

            if response.isError():
                msg = f"Modbus read error for {register_type} registers at {read_start}"
                raise AirfiApiClientModbusError(msg)

            registers = getattr(response, "registers", None)
            if not isinstance(registers, list) or len(registers) != read_length:
                msg = f"Unexpected Modbus response length for {register_type} registers at {read_start}"
                raise AirfiApiClientModbusError(msg)

            values.extend(int(value) for value in registers)
        return values

    async def async_write_holding_register(self, address: int, value: int) -> None:
        """Write a single Airfi holding register over Modbus TCP.

        Args:
            address: 1-based Modbus holding register address (e.g. 1 for 4x00001).
            value: Integer value to write.

        Raises:
            AirfiApiClientConnectionError: If the device is unreachable.
            AirfiApiClientNoResponseError: If the device takes the connection but does not answer.
            AirfiApiClientModbusError: If the Modbus write fails.
            AirfiApiClientError: For unexpected failures.
        """

        def _write() -> None:
            _LOGGER.debug("Writing holding register: address=%d, value=%d", address, value)
            client = self._connect()
            try:
                try:
                    response = client.write_register(address, value, device_id=self._unit_id)
                except (ConnectionException, ModbusIOException) as exception:
                    raise self._no_response(exception) from exception
                if response.isError():
                    msg = f"Modbus write error for holding register at {address}"
                    raise AirfiApiClientModbusError(msg)
            finally:
                client.close()

        try:
            async with self._lock:
                await self._async_run_on_device(_write, timeout=10, action="writing Modbus register")
        except AirfiApiClientError:
            raise
        except Exception as exception:
            msg = f"Unexpected Modbus write failure: {exception}"
            raise AirfiApiClientError(msg) from exception

    def _connect(self) -> ModbusTcpClient:
        """Open a connection to the unit.

        Raises:
            AirfiApiClientConnectionError: If the connection cannot be opened.
        """
        client = ModbusTcpClient(self._host, port=self._port, timeout=self._timeout_seconds, retries=self._retries)
        if not client.connect():
            msg = f"Unable to connect to device at {self._host}:{self._port}"
            raise AirfiApiClientConnectionError(msg)
        return client

    def _no_response(self, exception: Exception) -> AirfiApiClientNoResponseError:
        """Describe a request the unit left unanswered on an open connection."""
        msg = f"No answer from device at {self._host}:{self._port} to Modbus ID {self._unit_id}: {exception}"
        return AirfiApiClientNoResponseError(msg)

    def _request_registers(self, client: ModbusTcpClient, register_type: str, start_address: int, length: int) -> Any:
        """Read holding or input registers on an open connection.

        Raises:
            AirfiApiClientNoResponseError: If the unit times out or closes the connection instead of answering.
        """
        read = client.read_holding_registers if register_type == "holding" else client.read_input_registers
        try:
            return read(start_address, count=length, device_id=self._unit_id)
        except (ConnectionException, ModbusIOException) as exception:
            raise self._no_response(exception) from exception
