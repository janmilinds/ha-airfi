"""Test the Airfi API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from custom_components.airfi.api.client import AirfiApiClient, AirfiApiClientConnectionError, AirfiApiClientModbusError


@pytest.mark.unit
async def test_async_get_data_uses_cached_register_profile() -> None:
    """Test that polling skips lookup reads when the register profile is cached."""
    client = AirfiApiClient(host="192.168.1.10", port=502)
    client.set_register_profile(
        firmware_version="3.8.1",
        modbus_map_version="3.0.0",
        input_register_length=42,
        holding_register_length=59,
    )

    with (
        patch.object(client, "async_get_lookup_registers", new=AsyncMock()) as lookup_mock,
        patch.object(
            client,
            "_async_read_registers",
            new=AsyncMock(side_effect=[[1] * 59, [2] * 42]),
        ) as read_mock,
    ):
        result = await client.async_get_data()

    lookup_mock.assert_not_awaited()
    assert read_mock.await_args_list == [
        call(start_address=1, length=59, register_type="holding"),
        call(start_address=1, length=42, register_type="input"),
    ]
    assert result["firmware_version"] == "3.8.1"
    assert result["modbus_map_version"] == "3.0.0"
    assert result["lookup_registers"] == []


@pytest.mark.unit
async def test_async_get_data_builds_register_profile_once() -> None:
    """Test that lookup registers are read only once when building the cache."""
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with (
        patch.object(
            client,
            "async_get_lookup_registers",
            new=AsyncMock(return_value=[0, 381, 300]),
        ) as lookup_mock,
        patch.object(
            client,
            "_async_read_registers",
            new=AsyncMock(side_effect=[[1] * 59, [2] * 42, [3] * 59, [4] * 42]),
        ),
    ):
        first_result = await client.async_get_data()
        second_result = await client.async_get_data()

    lookup_mock.assert_awaited_once()
    assert first_result["firmware_version"] == "3.8.1"
    assert first_result["modbus_map_version"] == "3.0.0"
    assert second_result["firmware_version"] == "3.8.1"
    assert second_result["modbus_map_version"] == "3.0.0"


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
    """Test that a Modbus error response raises AirfiApiClientModbusError.

    This covers cases such as writing an invalid value to a register or
    targeting a register address that does not support writes.
    """
    client = AirfiApiClient(host="192.168.1.10", port=502)

    with patch("custom_components.airfi.api.client.ModbusTcpClient") as MockTcpClient:
        mock_instance = MockTcpClient.return_value
        mock_instance.connect.return_value = True
        mock_instance.write_register.return_value = MagicMock(isError=MagicMock(return_value=True))

        with pytest.raises(AirfiApiClientModbusError):
            await client.async_write_holding_register(address=1, value=3)
