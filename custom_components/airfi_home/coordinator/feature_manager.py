"""Feature manager for Airfi device detection and validation.

This module provides firmware validation, register length mapping, and device
capability detection based on the Modbus map version.
"""

from packaging import version

from custom_components.airfi_home.api.register_map import MapVersion, register_lengths
from custom_components.airfi_home.const import LOGGER
from custom_components.airfi_home.utils import version_string, version_tuple


class AirfiDeviceError(Exception):
    """Base exception for device validation errors."""


class InvalidDeviceDataError(AirfiDeviceError):
    """Raised when lookup registers contain insufficient or invalid data."""


class UnsupportedFirmwareError(AirfiDeviceError):
    """Raised when the firmware or Modbus map version is unsupported."""


class AirfiFeatureManager:
    """Manage device features and validation based on firmware version."""

    # Minimum supported Modbus protocol version
    MIN_MODBUS_VERSION = "2.0.0"

    # Firmware versions with known issues (not supported)
    UNSUPPORTED_FIRMWARE_VERSIONS = {"3.2.0"}

    # Feature flags gated by minimum Modbus map version
    _FEATURE_VERSION_MAP: dict[str, MapVersion] = {
        "boost": (2, 9, 0),
        "minimum_temperature_set": (2, 1, 0),
        "fireplace_function": (2, 5, 0),
        "boosted_cooling": (2, 1, 0),
        "sauna_function": (2, 5, 0),
    }

    def __init__(self) -> None:
        """Initialize the feature manager."""
        self.firmware_version = ""
        self.modbus_register_version = ""
        self.hw_version = ""
        self._map_version: MapVersion = (0, 0, 0)
        self._feature_flags: dict[str, bool] = dict.fromkeys(self._FEATURE_VERSION_MAP, False)

    def initialize(self, device_name: str, lookup_registers: list[int]) -> None:
        """Initialize and validate device based on lookup registers.

        Args:
            device_name: Display name for logging.
            lookup_registers: Input registers 1-3 from device.

        Raises:
            InvalidDeviceDataError: If lookup registers are insufficient.
            UnsupportedFirmwareError: If firmware version is not supported.

        """
        if len(lookup_registers) < 3:
            msg = f"Expected 3 lookup registers, got {len(lookup_registers)}"
            raise InvalidDeviceDataError(msg)

        # registers[0] = hardware version (3x00001)
        # registers[1] = firmware version, registers[2] = modbus map version
        self.hw_version = version_string(lookup_registers[0])
        self.firmware_version = version_string(lookup_registers[1])
        self.modbus_register_version = version_string(lookup_registers[2])
        self._map_version = version_tuple(lookup_registers[2])

        self.check_supported(lookup_registers)
        self._set_feature_flags()
        self._log_device_info(device_name)

    def get_register_lengths(self) -> tuple[int, int]:
        """Get input and holding register counts based on modbus map version.

        Returns:
            Tuple of (input_register_count, holding_register_count).

        """
        input_len, holding_len = register_lengths(self._map_version)
        LOGGER.debug(
            "Setting input register length to %d and holding register length to %d",
            input_len,
            holding_len,
        )
        return (input_len, holding_len)

    @classmethod
    def check_supported(cls, lookup_registers: list[int]) -> None:
        """Refuse a unit whose software this integration does not support.

        Args:
            lookup_registers: Input registers 1-3 from device.

        Raises:
            InvalidDeviceDataError: If the lookup registers are incomplete or hold no version.
            UnsupportedFirmwareError: If the firmware is blocklisted or the register map is older than 2.0.

        """
        if len(lookup_registers) < 3:
            msg = f"Expected 3 lookup registers, got {len(lookup_registers)}"
            raise InvalidDeviceDataError(msg)
        if 0 in (lookup_registers[1], lookup_registers[2]):
            msg = f"Lookup registers {lookup_registers[1:]} hold no firmware and register map version"
            raise InvalidDeviceDataError(msg)
        firmware_version = version_string(lookup_registers[1])
        modbus_register_version = version_string(lookup_registers[2])
        if cls.is_configuration_unsupported(firmware_version, modbus_register_version):
            msg = f"Firmware {firmware_version} with register map {modbus_register_version} is not supported"
            raise UnsupportedFirmwareError(msg)

    @classmethod
    def is_configuration_unsupported(cls, firmware_version: str, modbus_register_version: str) -> bool:
        """Check whether firmware or modbus version is unsupported.

        Combines the firmware blocklist check with the minimum Modbus version
        check so runtime validation catches both cases.
        """
        if firmware_version in cls.UNSUPPORTED_FIRMWARE_VERSIONS:
            return True
        return bool(modbus_register_version) and version.parse(modbus_register_version) < version.parse(
            cls.MIN_MODBUS_VERSION
        )

    def _log_device_info(self, device_name: str) -> None:
        """Log device information and versions.

        Args:
            device_name: Display name for logging.

        """
        headline = f"----- {device_name} -----"
        LOGGER.info(headline)
        LOGGER.info("  Firmware version: %s", self.firmware_version)
        LOGGER.info("  Modbus map version: %s", self.modbus_register_version)
        LOGGER.info("-" * len(headline))
        LOGGER.debug("  Feature flags: %s", self._feature_flags)

    def has_feature(self, feature: str) -> bool:
        """Check whether the device supports a given feature.

        Args:
            feature: Feature flag key (e.g. ``"fireplace_function"``).

        """
        return self._feature_flags.get(feature, False)

    def _set_feature_flags(self) -> None:
        """Set feature flags based on the Modbus map version."""
        for feature, min_version in self._FEATURE_VERSION_MAP.items():
            self._feature_flags[feature] = self._map_version >= min_version


__all__ = ["AirfiFeatureManager"]
