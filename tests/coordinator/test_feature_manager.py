"""Test feature manager behavior."""

from __future__ import annotations

import pytest

from custom_components.airfi.coordinator.feature_manager import AirfiFeatureManager


@pytest.mark.unit
def test_feature_manager_initializes_supported_device() -> None:
    """Test that a supported device initializes and resolves register lengths."""
    manager = AirfiFeatureManager()

    manager.initialize("Airfi AIRFI-12345", [0, 381, 300])

    assert manager.firmware_version == "3.8.1"
    assert manager.modbus_map_version == "3.0.0"
    assert manager.get_register_lengths() == (42, 59)


@pytest.mark.unit
def test_feature_manager_rejects_unsupported_firmware() -> None:
    """Test that firmware version 3.2.0 is rejected."""
    manager = AirfiFeatureManager()

    with pytest.raises(ValueError, match="unsupported"):
        manager.initialize("Airfi AIRFI-12345", [0, 320, 300])


@pytest.mark.unit
def test_feature_manager_rejects_too_old_modbus_map() -> None:
    """Test that a too old Modbus map version is rejected."""
    manager = AirfiFeatureManager()

    with pytest.raises(ValueError, match="Please upgrade"):
        manager.initialize("Airfi AIRFI-12345", [0, 140, 140])


@pytest.mark.unit
def test_feature_manager_rejects_short_lookup_payload() -> None:
    """Test that incomplete lookup data fails validation."""
    manager = AirfiFeatureManager()

    with pytest.raises(ValueError, match="Failed to retrieve data"):
        manager.initialize("Airfi AIRFI-12345", [0, 381])
