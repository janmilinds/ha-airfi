"""Test fan speed number entity for airfi."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.airfi.number.fan_speed import ENTITY_DESCRIPTIONS, AirfiFanSpeedNumber
from homeassistant.components.number import NumberMode


def _build_coordinator(holding_registers: list[int]) -> MagicMock:
    """Build a coordinator mock with holding register data."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = "airfi"
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.async_set_holding_register = AsyncMock()
    coordinator.data = {
        "holding_registers": holding_registers,
        "model": "Airfi",
        "firmware_version": "3.8.1",
    }
    return coordinator


@pytest.mark.unit
@pytest.mark.parametrize("device_value", [1, 2, 3, 4, 5])
def test_fan_speed_number_reads_holding_register_1(device_value: int) -> None:
    """Test that fan speed number reads device value from holding register 1 (index 0)."""
    coordinator = _build_coordinator([device_value])
    entity = AirfiFanSpeedNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_value == float(device_value)


@pytest.mark.unit
def test_fan_speed_number_returns_none_when_register_missing() -> None:
    """Test that fan speed number returns None when holding register 1 is absent."""
    coordinator = _build_coordinator([])
    entity = AirfiFanSpeedNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_value is None


@pytest.mark.unit
@pytest.mark.parametrize("value", [1.0, 2.0, 3.0, 4.0, 5.0])
async def test_fan_speed_number_writes_device_value_on_set(value: float) -> None:
    """Test that setting the value writes the correct integer to register 1."""
    coordinator = _build_coordinator([3])
    entity = AirfiFanSpeedNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_native_value(value)

    coordinator.async_set_holding_register.assert_awaited_once_with(1, int(value))


@pytest.mark.unit
def test_fan_speed_number_description_has_slider_mode() -> None:
    """Test that the entity description uses slider mode with range 1–5."""
    desc = ENTITY_DESCRIPTIONS[0]
    assert desc.mode == NumberMode.SLIDER
    assert desc.native_min_value == 1
    assert desc.native_max_value == 5
    assert desc.native_step == 1
