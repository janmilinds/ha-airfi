"""Test binary sensor connectivity entity for Airfi."""

from unittest.mock import MagicMock

import pytest

from custom_components.airfi_home.binary_sensor.connectivity import ENTITY_DESCRIPTIONS, AirfiConnectivitySensor
from custom_components.airfi_home.const import DOMAIN
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory


def _build_coordinator(*, last_update_success: bool = True) -> MagicMock:
    """Build a coordinator mock for binary sensor tests."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = DOMAIN
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.last_update_success = last_update_success
    coordinator.data = {}
    return coordinator


@pytest.mark.unit
def test_connectivity_sensor_is_on_when_update_success() -> None:
    """Test that connectivity sensor reports ON when last update succeeded."""
    coordinator = _build_coordinator(last_update_success=True)
    sensor = AirfiConnectivitySensor(coordinator, ENTITY_DESCRIPTIONS[0])

    assert sensor.is_on is True


@pytest.mark.unit
def test_connectivity_sensor_is_off_when_update_failed() -> None:
    """Test that connectivity sensor reports OFF when last update failed."""
    coordinator = _build_coordinator(last_update_success=False)
    sensor = AirfiConnectivitySensor(coordinator, ENTITY_DESCRIPTIONS[0])

    assert sensor.is_on is False


@pytest.mark.unit
def test_connectivity_sensor_entity_description() -> None:
    """Test that entity description has correct device class and category."""
    desc = ENTITY_DESCRIPTIONS[0]
    assert desc.key == "device_connectivity"
    assert desc.translation_key == "device_connectivity"
    assert desc.device_class == BinarySensorDeviceClass.CONNECTIVITY
    assert desc.entity_category == EntityCategory.DIAGNOSTIC
