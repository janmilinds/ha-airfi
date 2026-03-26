"""Test humidity sensors for airfi."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.airfi.sensor.humidity import ENTITY_DESCRIPTIONS, AirfiHumiditySensor


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


@pytest.mark.unit
def test_humidity_sensor_reads_register_23() -> None:
    """Test humidity sensor reads value from input register 23."""
    input_registers = [0] * 22 + [47]
    coordinator = _build_coordinator(input_registers)
    sensor = AirfiHumiditySensor(coordinator, ENTITY_DESCRIPTIONS[0])

    assert sensor.native_value == 47


@pytest.mark.unit
def test_humidity_sensor_returns_none_when_register_missing() -> None:
    """Test humidity sensor returns None when register 23 is not present."""
    coordinator = _build_coordinator([0] * 22)
    sensor = AirfiHumiditySensor(coordinator, ENTITY_DESCRIPTIONS[0])

    assert sensor.native_value is None
