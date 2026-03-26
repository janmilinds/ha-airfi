"""Test the Airfi API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

import pytest

from custom_components.airfi.api.client import AirfiApiClient


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
