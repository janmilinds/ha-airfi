"""Test supply air temperature number entity for Airfi."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.airfi.number.temperature import ENTITY_DESCRIPTIONS, AirfiTemperatureNumber
from homeassistant.const import UnitOfTemperature


def _build_coordinator(
    holding_registers: list[int],
    *,
    has_minimum_temperature: bool = False,
) -> MagicMock:
    """Build a coordinator mock with holding register data."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = "airfi"
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    feature_manager = MagicMock()
    feature_manager.has_feature = MagicMock(
        side_effect=lambda f: f == "minimum_temperature_set" and has_minimum_temperature
    )

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.async_set_holding_register = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.feature_manager = feature_manager
    coordinator.data = {
        "holding_registers": holding_registers,
        "input_registers": [],
        "model": "Airfi",
        "firmware_version": "3.8.1",
    }
    return coordinator


@pytest.mark.unit
def test_native_unit_and_supply_air_temperature_attribute() -> None:
    """Number entity exposes Celsius unit and supply-air measurement attribute."""
    # HR5 = 200 => setpoint 20.0
    # Input register 8 = 206 => measured 20.6
    input_registers = [0, 0, 0, 0, 0, 0, 0, 206]
    coordinator = _build_coordinator([0, 0, 0, 0, 200])
    coordinator.data["input_registers"] = input_registers

    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_unit_of_measurement == UnitOfTemperature.CELSIUS

    attrs = entity.extra_state_attributes
    assert "supply_air_temperature" in attrs
    assert attrs["supply_air_temperature"] == 20.6


@pytest.mark.unit
def test_extra_state_attributes_no_input_registers() -> None:
    """Test that extra_state_attributes returns empty dict when input registers are missing."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200])
    coordinator.data["input_registers"] = []  # No input registers

    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.extra_state_attributes == {}


@pytest.mark.unit
def test_native_value_reads_register_5() -> None:
    """Test that native_value reads holding register 5 and divides by 10."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200])  # HR5 = 200 => 20.0
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_value == 20.0


@pytest.mark.unit
def test_native_value_fractional() -> None:
    """Test that native_value returns fractional values correctly."""
    coordinator = _build_coordinator([0, 0, 0, 0, 185])  # HR5 = 185 => 18.5
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_value == 18.5


@pytest.mark.unit
def test_native_value_returns_none_when_register_missing() -> None:
    """Test that native_value returns None when register 5 is out of range."""
    coordinator = _build_coordinator([0, 0, 0])  # Only 3 registers
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    assert entity.native_value is None


@pytest.mark.unit
async def test_set_value_writes_register_5() -> None:
    """Test that setting the value writes °C × 10 to register 5."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200])
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_native_value(18.0)

    coordinator.async_set_holding_register.assert_any_await(5, 180)


@pytest.mark.unit
async def test_set_value_does_not_write_minimum_without_feature() -> None:
    """Test that register 50 is NOT written when feature is unavailable."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200], has_minimum_temperature=False)
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_native_value(18.0)

    assert coordinator.async_set_holding_register.await_count == 1
    coordinator.async_set_holding_register.assert_awaited_once_with(5, 180)


@pytest.mark.unit
async def test_set_value_writes_minimum_with_feature() -> None:
    """Test that register 50 is also written when minimum_temperature_set is available."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200], has_minimum_temperature=True)
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_native_value(18.0)

    calls = coordinator.async_set_holding_register.call_args_list
    assert len(calls) == 2
    # First call: register 5 = 180 (18.0 × 10)
    assert calls[0][0] == (5, 180)
    # Second call: register 50 = 18 (raw °C)
    assert calls[1][0] == (50, 18)


@pytest.mark.unit
async def test_set_value_triggers_refresh() -> None:
    """Test that async_request_refresh is called after writing."""
    coordinator = _build_coordinator([0, 0, 0, 0, 200])
    entity = AirfiTemperatureNumber(coordinator, ENTITY_DESCRIPTIONS[0])

    await entity.async_set_native_value(20.0)

    coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.unit
def test_entity_description_constraints() -> None:
    """Test that the entity description has correct min/max/step/mode."""
    desc = ENTITY_DESCRIPTIONS[0]
    assert desc.key == "supply_air_temperature_setting"
    assert desc.native_min_value == 13.0
    assert desc.native_max_value == 25.0
    assert desc.native_step == 1.0
