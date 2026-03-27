"""Test fan entity for airfi."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.airfi.fan.fan import ENTITY_DESCRIPTIONS, AirfiFan


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
def test_fan_is_on_when_device_value_0() -> None:
    """Test that fan is ON when register 12 is 0 (at-home)."""
    coordinator = _build_coordinator([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.is_on is True


@pytest.mark.unit
def test_fan_is_off_when_device_value_1() -> None:
    """Test that fan is OFF when register 12 is 1 (away)."""
    coordinator = _build_coordinator([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.is_on is False


@pytest.mark.unit
def test_fan_is_none_when_register_missing() -> None:
    """Test that fan is_on returns None when register 12 is missing."""
    coordinator = _build_coordinator([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.is_on is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("device_speed", "expected_percentage"),
    [(1, 20), (2, 40), (3, 60), (4, 80), (5, 100)],
)
def test_fan_percentage_maps_device_speed(device_speed: int, expected_percentage: int) -> None:
    """Test that fan percentage correctly maps device speed 1-5 to 20-100%."""
    coordinator = _build_coordinator([device_speed, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.percentage == expected_percentage


@pytest.mark.unit
def test_fan_percentage_returns_0_when_off() -> None:
    """Test that fan percentage returns 0 when is_on is False."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.percentage == 0


@pytest.mark.unit
def test_fan_percentage_returns_none_when_register_missing() -> None:
    """Test that fan percentage returns None when speed register is missing."""
    coordinator = _build_coordinator([])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.percentage is None


@pytest.mark.unit
def test_fan_icon_is_fan_when_on() -> None:
    """Test that icon is mdi:fan when fan is on."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.icon == "mdi:fan"


@pytest.mark.unit
def test_fan_icon_is_fan_off_when_off() -> None:
    """Test that icon is mdi:fan-off when fan is off."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.icon == "mdi:fan-off"


@pytest.mark.unit
def test_fan_icon_defaults_to_fan_when_register_missing() -> None:
    """Test that icon defaults to mdi:fan when register is missing."""
    coordinator = _build_coordinator([3])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.icon == "mdi:fan"


@pytest.mark.unit
async def test_fan_turn_on_writes_0_to_register_12() -> None:
    """Test that turning on writes 0 to register 12 (at-home)."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_turn_on()

    coordinator.async_set_holding_register.assert_awaited_once_with(12, 0)


@pytest.mark.unit
async def test_fan_turn_off_writes_1_to_register_12() -> None:
    """Test that turning off writes 1 to register 12 (away)."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_turn_off()

    coordinator.async_set_holding_register.assert_awaited_once_with(12, 1)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("percentage", "expected_device_speed"),
    [(20, 1), (40, 2), (60, 3), (80, 4), (100, 5)],
)
async def test_fan_set_percentage_writes_device_speed(
    percentage: int,
    expected_device_speed: int,
) -> None:
    """Test that set_percentage converts percentage to device speed and writes to register 1."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_percentage(percentage)

    calls = coordinator.async_set_holding_register.call_args_list
    assert len(calls) == 2
    # First call: ensure on (register 12 = 0)
    assert calls[0][0] == (12, 0)
    # Second call: set speed (register 1 = expected_device_speed)
    assert calls[1][0] == (1, expected_device_speed)


@pytest.mark.unit
async def test_fan_set_percentage_0_turns_off() -> None:
    """Test that set_percentage(0) calls turn_off."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_percentage(0)

    coordinator.async_set_holding_register.assert_awaited_once_with(12, 1)


@pytest.mark.unit
async def test_fan_turn_on_with_percentage() -> None:
    """Test that turn_on with percentage also sets the speed."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_turn_on(percentage=60)

    calls = coordinator.async_set_holding_register.call_args_list
    assert len(calls) == 3
    # First call: turn on (register 12 = 0)
    assert calls[0][0] == (12, 0)
    # Second call: ensure on (register 12 = 0 again from set_percentage)
    assert calls[1][0] == (12, 0)
    # Third call: set speed (register 1 = 3)
    assert calls[2][0] == (1, 3)


@pytest.mark.unit
async def test_fan_set_percentage_turns_on_if_off() -> None:
    """Test that set_percentage turns on the fan if it's currently off."""
    coordinator = _build_coordinator([3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    entity = AirfiFan(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_percentage(60)

    calls = coordinator.async_set_holding_register.call_args_list
    assert len(calls) == 2
    # First call: ensure on (register 12 = 0)
    assert calls[0][0] == (12, 0)
    # Second call: set speed (register 1 = 3)
    assert calls[1][0] == (1, 3)
