"""Test diagnostic sensors for Airfi."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.airfi.sensor.diagnostics import ENTITY_DESCRIPTIONS, AirfiDiagnosticSensor
from homeassistant.const import EntityCategory


def _build_coordinator(
    firmware_version: str | None = "3.8.1",
    modbus_register_version: str | None = "2.7.0",
) -> MagicMock:
    """Build a coordinator mock suitable for Airfi diagnostic entities."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = "airfi"
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    data: dict[str, str] = {}
    if firmware_version is not None:
        data["firmware_version"] = firmware_version
    if modbus_register_version is not None:
        data["modbus_register_version"] = modbus_register_version

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.data = data
    return coordinator


def _desc(key: str) -> object:
    """Return the entity description with the given key."""
    return next(d for d in ENTITY_DESCRIPTIONS if d.key == key)


@pytest.mark.unit
def test_firmware_version_sensor_reads_coordinator_data() -> None:
    """Test firmware version sensor reads value from coordinator data."""
    coordinator = _build_coordinator(firmware_version="3.8.1")
    sensor = AirfiDiagnosticSensor(coordinator, _desc("firmware_version"))

    assert sensor.native_value == "3.8.1"


@pytest.mark.unit
def test_modbus_register_version_sensor_reads_coordinator_data() -> None:
    """Test modbus map version sensor reads value from coordinator data."""
    coordinator = _build_coordinator(modbus_register_version="2.7.0")
    sensor = AirfiDiagnosticSensor(coordinator, _desc("modbus_register_version"))

    assert sensor.native_value == "2.7.0"


@pytest.mark.unit
def test_firmware_version_sensor_returns_none_when_missing() -> None:
    """Test firmware version sensor returns None when key absent from data."""
    coordinator = _build_coordinator()
    coordinator.data = {}
    sensor = AirfiDiagnosticSensor(coordinator, _desc("firmware_version"))

    assert sensor.native_value is None


@pytest.mark.unit
def test_modbus_register_version_sensor_returns_none_when_missing() -> None:
    """Test modbus map version sensor returns None when key absent from data."""
    coordinator = _build_coordinator()
    coordinator.data = {}
    sensor = AirfiDiagnosticSensor(coordinator, _desc("modbus_register_version"))

    assert sensor.native_value is None


@pytest.mark.unit
def test_diagnostic_sensors_are_disabled_by_default() -> None:
    """Test all diagnostic sensors have entity_registry_enabled_default=False."""
    for desc in ENTITY_DESCRIPTIONS:
        assert desc.entity_registry_enabled_default is False, f"{desc.key} should be disabled by default"


@pytest.mark.unit
def test_diagnostic_sensors_have_diagnostic_category() -> None:
    """Test all diagnostic sensors use EntityCategory.DIAGNOSTIC."""
    for desc in ENTITY_DESCRIPTIONS:
        assert desc.entity_category == EntityCategory.DIAGNOSTIC, f"{desc.key} should have DIAGNOSTIC entity category"


@pytest.mark.unit
def test_firmware_sensor_unique_id() -> None:
    """Test firmware version sensor has the expected unique ID."""
    coordinator = _build_coordinator()
    sensor = AirfiDiagnosticSensor(coordinator, _desc("firmware_version"))

    assert sensor.unique_id == "entry-1_firmware_version"


@pytest.mark.unit
def test_modbus_map_sensor_unique_id() -> None:
    """Test modbus map version sensor has the expected unique ID."""
    coordinator = _build_coordinator()
    sensor = AirfiDiagnosticSensor(coordinator, _desc("modbus_register_version"))

    assert sensor.unique_id == "entry-1_modbus_register_version"


@pytest.mark.unit
def test_diagnostic_entity_descriptions_count() -> None:
    """Test that the expected number of diagnostic entity descriptions exist."""
    assert len(ENTITY_DESCRIPTIONS) == 2


@pytest.mark.unit
def test_diagnostic_entity_description_keys() -> None:
    """Test that entity description keys match the expected values."""
    keys = {desc.key for desc in ENTITY_DESCRIPTIONS}
    assert keys == {"firmware_version", "modbus_register_version"}


@pytest.mark.unit
def test_diagnostic_entity_translation_keys() -> None:
    """Test that translation_key matches the entity key for each description."""
    for desc in ENTITY_DESCRIPTIONS:
        assert desc.translation_key == desc.key, f"translation_key should match key for {desc.key}"
