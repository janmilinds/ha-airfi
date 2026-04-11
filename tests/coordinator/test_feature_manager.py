"""Test feature manager behavior."""

from __future__ import annotations

import pytest

from custom_components.airfi.coordinator.feature_manager import AirfiFeatureManager
from custom_components.airfi.utils import version_string


@pytest.mark.unit
def test_feature_manager_initializes_supported_device() -> None:
    """Test that a supported device initializes and resolves register lengths."""
    manager = AirfiFeatureManager()

    manager.initialize("Airfi AIRFI-12345", [0, 381, 300])

    assert manager.firmware_version == "3.8.1"
    assert manager.modbus_register_version == "3.0.0"
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


@pytest.mark.unit
def test_feature_manager_fallback_register_lengths() -> None:
    """Test that an unknown map version falls back to minimum version.

    This path is defensive — normally _validate_firmware_version rejects
    versions below MIN_MODBUS_VERSION during initialize().
    """
    manager = AirfiFeatureManager()
    # Bypass validation by setting version directly
    manager.modbus_register_version = "0.0.1"
    assert manager.get_register_lengths() == (31, 12)


@pytest.mark.unit
def test_version_string_two_digit_register_value() -> None:
    """Test that a 2-digit register value produces correct version string."""
    assert version_string(27) == "2.7.0"


@pytest.mark.unit
def test_version_string_one_digit_register_value() -> None:
    """Test that a 1-digit register value produces correct version string."""
    assert version_string(5) == "5.0.0"


# ——— Feature flag tests ———


@pytest.mark.unit
def test_feature_flags_all_false_before_initialize() -> None:
    """Test that all feature flags are False before initialize() is called."""
    manager = AirfiFeatureManager()

    assert manager.has_feature("fireplace_function") is False
    assert manager.has_feature("sauna_function") is False
    assert manager.has_feature("boosted_cooling") is False
    assert manager.has_feature("minimum_temperature_set") is False


@pytest.mark.unit
def test_feature_flags_unknown_feature_returns_false() -> None:
    """Test that has_feature returns False for unknown feature names."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 270])

    assert manager.has_feature("nonexistent_feature") is False


@pytest.mark.unit
def test_feature_flags_modbus_270_all_enabled() -> None:
    """Test that all features are enabled with modbus map version 2.7.0."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 270])

    assert manager.has_feature("minimum_temperature_set") is True
    assert manager.has_feature("fireplace_function") is True
    assert manager.has_feature("sauna_function") is True
    assert manager.has_feature("boosted_cooling") is True


@pytest.mark.unit
def test_feature_flags_modbus_250_all_enabled() -> None:
    """Test that all features are enabled with modbus map version 2.5.0."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 250])

    assert manager.has_feature("minimum_temperature_set") is True
    assert manager.has_feature("fireplace_function") is True
    assert manager.has_feature("sauna_function") is True
    assert manager.has_feature("boosted_cooling") is True


@pytest.mark.unit
def test_feature_flags_modbus_210_only_minimum_temperature() -> None:
    """Test that only minimum_temperature_set is enabled with modbus 2.1.0."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 210])

    assert manager.has_feature("minimum_temperature_set") is True
    assert manager.has_feature("fireplace_function") is False
    assert manager.has_feature("sauna_function") is False
    assert manager.has_feature("boosted_cooling") is False


@pytest.mark.unit
def test_feature_flags_modbus_200_none_enabled() -> None:
    """Test that no features are enabled with modbus map version 2.0.0."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 200])

    assert manager.has_feature("minimum_temperature_set") is False
    assert manager.has_feature("fireplace_function") is False
    assert manager.has_feature("sauna_function") is False
    assert manager.has_feature("boosted_cooling") is False


@pytest.mark.unit
def test_feature_flags_modbus_150_none_enabled() -> None:
    """Test that no features are enabled with modbus map version 1.5.0."""
    manager = AirfiFeatureManager()
    manager.initialize("Airfi AIRFI-12345", [0, 381, 150])

    assert manager.has_feature("minimum_temperature_set") is False
    assert manager.has_feature("fireplace_function") is False
