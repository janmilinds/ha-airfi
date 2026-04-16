"""Test the Airfi API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.airfi.api.client import (
    AirfiApiClient,
    AirfiApiClientConnectionError,
    AirfiApiClientError,
    AirfiApiClientModbusError,
    _register_lengths,
)
from custom_components.airfi.utils import version_string, version_tuple

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (270, (2, 7, 0)),
        (381, (3, 8, 1)),
        (150, (1, 5, 0)),
        (99, (9, 9, 0)),
        (5, (5, 0, 0)),
        (0, (0, 0, 0)),
        (1230, (1, 2, 3)),
    ],
)
def test_as_version_tuple(value: int, expected: tuple[int, int, int]) -> None:
    """Test version tuple conversion from register values."""
    assert version_tuple(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (270, "2.7.0"),
        (381, "3.8.1"),
        (5, "5.0.0"),
    ],
)
def test_as_version_string(value: int, expected: str) -> None:
    """Test version string conversion from register values."""
    assert version_string(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("map_version_raw", "expected"),
    [
        (270, (42, 59)),
        (250, (40, 58)),
        (230, (40, 55)),
        (210, (40, 51)),
        (200, (40, 34)),
        (150, (31, 12)),
    ],
)
def test_register_lengths_by_version(map_version_raw: int, expected: tuple[int, int]) -> None:
    """Test register length resolution for each known modbus map version."""
    assert _register_lengths(map_version_raw) == expected


@pytest.mark.unit
def test_register_lengths_fallback_for_unknown_version() -> None:
    """Test that an unknown old version falls back to the oldest mapping."""
    assert _register_lengths(100) == (31, 12)


# ---------------------------------------------------------------------------
# async_test_connection
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_test_connection_calls_read() -> None:
    """Test that async_test_connection reads input registers."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch.object(client, "_async_read_registers", new=AsyncMock(return_value=[0, 0, 0])) as mock_read:
        await client.async_test_connection()

    mock_read.assert_awaited_once_with(start_address=1, length=3, register_type="input")


# ---------------------------------------------------------------------------
# async_get_data (cached profile)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_get_data_uses_cached_register_profile() -> None:
    """Test that polling skips lookup reads when the register profile is cached."""
    client = AirfiApiClient(host="192.168.1.10", port=502)
    client.set_register_profile(
        firmware_version="3.8.1",
        modbus_register_version="3.0.0",
        input_register_length=42,
        holding_register_length=59,
    )

    holding = [1] * 59
    inputs = [0, 381, 300] + [0] * 39
    with (
        patch.object(client, "async_get_lookup_registers", new=AsyncMock()) as lookup_mock,
        patch.object(
            client,
            "_async_read_all_registers",
            new=AsyncMock(return_value=(holding, inputs)),
        ),
    ):
        result = await client.async_get_data()

    lookup_mock.assert_not_awaited()
    assert result["firmware_version"] == "3.8.1"
    assert result["modbus_register_version"] == "3.0.0"
    assert result["lookup_registers"] == []


@pytest.mark.unit
async def test_async_get_data_builds_register_profile_once() -> None:
    """Test that lookup registers are read only once when building the cache."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    holding_1 = [1] * 59
    inputs_1 = [0, 381, 300] + [0] * 39
    holding_2 = [3] * 59
    inputs_2 = [0, 381, 300] + [0] * 39
    with (
        patch.object(
            client,
            "async_get_lookup_registers",
            new=AsyncMock(return_value=[0, 381, 300]),
        ) as lookup_mock,
        patch.object(
            client,
            "_async_read_all_registers",
            new=AsyncMock(
                side_effect=[
                    (holding_1, inputs_1),
                    (holding_2, inputs_2),
                ]
            ),
        ),
    ):
        first_result = await client.async_get_data()
        second_result = await client.async_get_data()

    lookup_mock.assert_awaited_once()
    assert first_result["firmware_version"] == "3.8.1"
    assert first_result["modbus_register_version"] == "3.0.0"
    assert second_result["firmware_version"] == "3.8.1"
    assert second_result["modbus_register_version"] == "3.0.0"


@pytest.mark.unit
async def test_async_get_data_reads_modbus_version_live() -> None:
    """Test that modbus_register_version is read live from input_registers[2].

    Even though the cached profile says "3.0.0", the live register value
    should take precedence so runtime changes are detected.
    """
    client = AirfiApiClient(host="192.168.1.10", port=502)
    client.set_register_profile(
        firmware_version="3.8.1",
        modbus_register_version="3.0.0",
        input_register_length=42,
        holding_register_length=59,
    )

    holding = [1] * 59
    # input_registers[2]=270 → modbus "2.7.0" (changed at runtime)
    inputs = [0, 381, 270] + [0] * 39
    with patch.object(
        client,
        "_async_read_all_registers",
        new=AsyncMock(return_value=(holding, inputs)),
    ):
        result = await client.async_get_data()

    assert result["modbus_register_version"] == "2.7.0"


# ---------------------------------------------------------------------------
# _async_read_chunk (actual Modbus reads)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_read_chunk_input_registers() -> None:
    """Test that _async_read_chunk reads input registers correctly."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [10, 20, 30]
        mock_instance.read_input_registers.return_value = mock_response

        result = await client._async_read_chunk(1, 3, "input")  # noqa: SLF001

    assert result == [10, 20, 30]
    mock_instance.read_input_registers.assert_called_once_with(1, count=3, device_id=1)
    mock_instance.close.assert_called_once()


@pytest.mark.unit
async def test_read_chunk_holding_registers() -> None:
    """Test that _async_read_chunk reads holding registers correctly."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [1, 2, 3, 4, 5]
        mock_instance.read_holding_registers.return_value = mock_response

        result = await client._async_read_chunk(1, 5, "holding")  # noqa: SLF001

    assert result == [1, 2, 3, 4, 5]
    mock_instance.read_holding_registers.assert_called_once_with(1, count=5, device_id=1)


@pytest.mark.unit
async def test_read_chunk_connection_failure() -> None:
    """Test that failed TCP connection raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = False

        with pytest.raises(AirfiApiClientConnectionError, match="Unable to connect"):
            await client._async_read_chunk(1, 3, "input")  # noqa: SLF001


@pytest.mark.unit
async def test_read_chunk_modbus_error_response() -> None:
    """Test that Modbus error response raises AirfiApiClientModbusError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_response = MagicMock()
        mock_response.isError.return_value = True
        mock_instance.read_input_registers.return_value = mock_response

        with pytest.raises(AirfiApiClientModbusError, match="Modbus read error"):
            await client._async_read_chunk(1, 3, "input")  # noqa: SLF001


@pytest.mark.unit
async def test_read_chunk_unexpected_response_length() -> None:
    """Test that mismatched register count raises AirfiApiClientModbusError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [1, 2]  # Expected 3
        mock_instance.read_input_registers.return_value = mock_response

        with pytest.raises(AirfiApiClientModbusError, match="Unexpected Modbus response length"):
            await client._async_read_chunk(1, 3, "input")  # noqa: SLF001


@pytest.mark.unit
async def test_read_chunk_unexpected_exception() -> None:
    """Test that unexpected exceptions are wrapped in AirfiApiClientError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.side_effect = OSError("unexpected")

        with pytest.raises(AirfiApiClientError, match="Unexpected Modbus read failure"):
            await client._async_read_chunk(1, 3, "input")  # noqa: SLF001


# ---------------------------------------------------------------------------
# _async_read_registers (chunking)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_read_registers_chunks_large_reads() -> None:
    """Test that reads larger than MODBUS_READ_LIMIT are chunked correctly."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    # 42 registers → 2 chunks: 30 + 12
    with patch.object(
        client,
        "_async_read_chunk",
        new=AsyncMock(side_effect=[[1] * 30, [2] * 12]),
    ) as mock_chunk:
        result = await client._async_read_registers(1, 42, "input")  # noqa: SLF001

    assert len(result) == 42
    assert mock_chunk.await_count == 2
    mock_chunk.assert_any_await(1, 30, "input")
    mock_chunk.assert_any_await(31, 12, "input")


# ---------------------------------------------------------------------------
# _async_read_all_registers (single-connection batched reads)
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_read_all_registers_success() -> None:
    """Test that _async_read_all_registers reads holding and input in one connection."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True

        holding_resp = MagicMock()
        holding_resp.isError.return_value = False
        holding_resp.registers = list(range(12))

        input_resp = MagicMock()
        input_resp.isError.return_value = False
        input_resp.registers = list(range(10))

        mock_instance.read_holding_registers.return_value = holding_resp
        mock_instance.read_input_registers.return_value = input_resp

        holding, inputs = await client._async_read_all_registers(  # noqa: SLF001
            input_length=10, holding_length=12
        )

    assert holding == list(range(12))
    assert inputs == list(range(10))
    mock_instance.close.assert_called_once()


@pytest.mark.unit
async def test_read_all_registers_connection_failure() -> None:
    """Test that connection failure raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = False

        with pytest.raises(AirfiApiClientConnectionError, match="Unable to connect"):
            await client._async_read_all_registers(  # noqa: SLF001
                input_length=10, holding_length=12
            )


@pytest.mark.unit
async def test_read_all_registers_modbus_error() -> None:
    """Test that Modbus error in holding read raises AirfiApiClientModbusError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True

        error_resp = MagicMock()
        error_resp.isError.return_value = True
        mock_instance.read_holding_registers.return_value = error_resp

        with pytest.raises(AirfiApiClientModbusError, match="Modbus read error"):
            await client._async_read_all_registers(  # noqa: SLF001
                input_length=10, holding_length=12
            )


@pytest.mark.unit
async def test_read_all_registers_unexpected_response_length() -> None:
    """Test that mismatched register count in input read raises AirfiApiClientModbusError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True

        holding_resp = MagicMock()
        holding_resp.isError.return_value = False
        holding_resp.registers = list(range(12))
        mock_instance.read_holding_registers.return_value = holding_resp

        bad_input_resp = MagicMock()
        bad_input_resp.isError.return_value = False
        bad_input_resp.registers = [1, 2]  # Expected 10
        mock_instance.read_input_registers.return_value = bad_input_resp

        with pytest.raises(AirfiApiClientModbusError, match="Unexpected Modbus response length"):
            await client._async_read_all_registers(  # noqa: SLF001
                input_length=10, holding_length=12
            )


@pytest.mark.unit
async def test_read_all_registers_timeout() -> None:
    """Test that timeout raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with (
        patch("asyncio.to_thread", new=AsyncMock(side_effect=TimeoutError("timed out"))),
        pytest.raises(AirfiApiClientConnectionError, match="Timeout"),
    ):
        await client._async_read_all_registers(  # noqa: SLF001
            input_length=10, holding_length=12
        )


@pytest.mark.unit
async def test_read_all_registers_unexpected_exception() -> None:
    """Test that unexpected exceptions are wrapped in AirfiApiClientError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.side_effect = RuntimeError("unexpected")

        with pytest.raises(AirfiApiClientError, match="Unexpected Modbus read failure"):
            await client._async_read_all_registers(  # noqa: SLF001
                input_length=10, holding_length=12
            )


@pytest.mark.unit
async def test_read_all_registers_chunks_large_reads() -> None:
    """Test that reads larger than MODBUS_READ_LIMIT are properly chunked."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True

        # 42 input registers → 2 chunks (30 + 12)
        input_resp_1 = MagicMock()
        input_resp_1.isError.return_value = False
        input_resp_1.registers = list(range(30))
        input_resp_2 = MagicMock()
        input_resp_2.isError.return_value = False
        input_resp_2.registers = list(range(12))

        # 12 holding registers → 1 chunk
        holding_resp = MagicMock()
        holding_resp.isError.return_value = False
        holding_resp.registers = list(range(12))

        mock_instance.read_holding_registers.return_value = holding_resp
        mock_instance.read_input_registers.side_effect = [input_resp_1, input_resp_2]

        holding, inputs = await client._async_read_all_registers(  # noqa: SLF001
            input_length=42, holding_length=12
        )

    assert len(inputs) == 42
    assert len(holding) == 12
    assert mock_instance.read_input_registers.call_count == 2


# ---------------------------------------------------------------------------
# async_write_holding_register
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_write_holding_register_calls_modbus_write() -> None:
    """Test that async_write_holding_register writes the correct register and value."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_instance.write_register.return_value = MagicMock(isError=MagicMock(return_value=False))

        await client.async_write_holding_register(address=1, value=3)

    mock_instance.write_register.assert_called_once_with(1, 3, device_id=1)
    mock_instance.close.assert_called_once()


@pytest.mark.unit
async def test_async_write_holding_register_raises_connection_error_on_tcp_failure() -> None:
    """Test that a failed TCP connection raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = False

        with pytest.raises(AirfiApiClientConnectionError):
            await client.async_write_holding_register(address=1, value=3)


@pytest.mark.unit
async def test_async_write_holding_register_raises_modbus_error_on_error_response() -> None:
    """Test that a Modbus error response raises AirfiApiClientModbusError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_instance.write_register.return_value = MagicMock(isError=MagicMock(return_value=True))

        with pytest.raises(AirfiApiClientModbusError):
            await client.async_write_holding_register(address=1, value=3)


@pytest.mark.unit
async def test_async_write_unexpected_exception() -> None:
    """Test that unexpected write exceptions are wrapped in AirfiApiClientError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.side_effect = OSError("unexpected")

        with pytest.raises(AirfiApiClientError, match="Unexpected Modbus write failure"):
            await client.async_write_holding_register(address=1, value=3)


# ---------------------------------------------------------------------------
# _async_ensure_register_profile
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_ensure_register_profile_skips_when_cached() -> None:
    """Test that ensure_register_profile is a no-op when profile is already cached."""
    client = AirfiApiClient(host="192.168.1.10", port=502)
    client.set_register_profile(
        firmware_version="3.8.1",
        modbus_register_version="3.0.0",
        input_register_length=42,
        holding_register_length=59,
    )

    with patch.object(client, "async_get_lookup_registers", new=AsyncMock()) as mock_lookup:
        await client._async_ensure_register_profile()  # noqa: SLF001

    mock_lookup.assert_not_awaited()


@pytest.mark.unit
async def test_ensure_register_profile_fetches_when_not_cached() -> None:
    """Test that ensure_register_profile fetches lookup registers when not cached."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch.object(
        client,
        "async_get_lookup_registers",
        new=AsyncMock(return_value=[0, 270, 270]),
    ):
        await client._async_ensure_register_profile()  # noqa: SLF001

    assert client._firmware_version == "2.7.0"  # noqa: SLF001
    assert client._modbus_register_version == "2.7.0"  # noqa: SLF001
    assert client._input_register_length == 42  # noqa: SLF001
    assert client._holding_register_length == 59  # noqa: SLF001


# ---------------------------------------------------------------------------
# async_get_lookup_registers
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_async_get_lookup_registers() -> None:
    """Test that async_get_lookup_registers reads the first 3 input registers."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch.object(
        client,
        "_async_read_registers",
        new=AsyncMock(return_value=[0, 270, 270]),
    ) as mock_read:
        result = await client.async_get_lookup_registers()

    mock_read.assert_awaited_once_with(start_address=1, length=3, register_type="input")
    assert result == [0, 270, 270]


# ---------------------------------------------------------------------------
# Timeout paths
# ---------------------------------------------------------------------------


@pytest.mark.unit
async def test_read_chunk_timeout_raises_connection_error() -> None:
    """Test that a read timeout raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with (
        patch("asyncio.to_thread", new=AsyncMock(side_effect=TimeoutError("timed out"))),
        pytest.raises(AirfiApiClientConnectionError, match="Timeout while reading"),
    ):
        await client._async_read_chunk(1, 3, "input")  # noqa: SLF001


@pytest.mark.unit
async def test_write_timeout_raises_connection_error() -> None:
    """Test that a write timeout raises AirfiApiClientConnectionError."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with (
        patch("asyncio.to_thread", new=AsyncMock(side_effect=TimeoutError("timed out"))),
        pytest.raises(AirfiApiClientConnectionError, match="Timeout while writing"),
    ):
        await client.async_write_holding_register(address=1, value=3)


# ---------------------------------------------------------------------------
# update_host
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_update_host_changes_target() -> None:
    """Test that update_host changes the client's target host."""
    client = AirfiApiClient(host="192.168.1.10", port=502)
    client.update_host("10.0.0.1")
    assert client._host == "10.0.0.1"  # noqa: SLF001
