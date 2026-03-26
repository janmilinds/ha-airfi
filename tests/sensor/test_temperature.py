"""Test temperature sensors for airfi."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.airfi.sensor.temperature import ENTITY_DESCRIPTIONS, AirfiTemperatureSensor, convert_temperature


def _build_coordinator(input_registers: list[int]) -> MagicMock:
    """Build a coordinator mock suitable for Airfi entities."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = "airfi"
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.data = {
        "input_registers": input_registers,
        "model": "Airfi",
        "firmware_version": "3.8.1",
    }
    return coordinator


def _description_for(key: str):
    """Get the sensor description for a given key."""
    return next(description for description in ENTITY_DESCRIPTIONS if description.key == key)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (215, 21.5),
        (65534, -0.1),
        (62804, -273.1),
        (float("nan"), 0.0),
    ],
)
def test_convert_temperature(raw_value: float, expected: float) -> None:
    """Test conversion from Airfi register values to Celsius."""
    assert convert_temperature(raw_value) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("sensor_key", "register_value", "expected"),
    [
        ("outdoor_air_temperature", 193, 19.3),
        ("extract_air_temperature", 204, 20.4),
        ("exhaust_air_temperature", 205, 20.5),
        ("supply_air_temperature", 206, 20.6),
    ],
)
def test_temperature_sensor_value_mapping(sensor_key: str, register_value: int, expected: float) -> None:
    """Test each temperature sensor reads the expected input register."""
    input_registers = [0, 0, 0, 193, 0, 204, 205, 206]
    coordinator = _build_coordinator(input_registers)

    if sensor_key == "outdoor_air_temperature":
        input_registers[3] = register_value
    elif sensor_key == "extract_air_temperature":
        input_registers[5] = register_value
    elif sensor_key == "exhaust_air_temperature":
        input_registers[6] = register_value
    else:
        input_registers[7] = register_value

    sensor = AirfiTemperatureSensor(coordinator, _description_for(sensor_key))

    assert sensor.native_value == expected


@pytest.mark.unit
def test_temperature_sensor_returns_none_when_register_missing() -> None:
    """Test sensor value is unavailable when input register is not present."""
    coordinator = _build_coordinator([0, 0, 0, 193])
    sensor = AirfiTemperatureSensor(coordinator, _description_for("supply_air_temperature"))

    assert sensor.native_value is None
