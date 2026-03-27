"""Feature manager for Airfi device detection and validation.

This module provides firmware validation, register length mapping, and device
capability detection.
"""

from __future__ import annotations

from packaging import version

from custom_components.airfi.const import LOGGER


class AirfiFeatureManager:
    """Manage device features and validation based on firmware version."""

    # Minimum supported Modbus protocol version
    MIN_MODBUS_VERSION = "1.5.0"

    # Firmware versions with known issues (not supported)
    UNSUPPORTED_FIRMWARE_VERSIONS = {"3.2.0"}

    # Register count mapping by Modbus map version
    # Format: (input_register_count, holding_register_count)
    REGISTER_LENGTHS_BY_MAP_VERSION = {
        "2.7.0": (42, 59),
        "2.5.0": (40, 58),
        "2.3.0": (40, 55),
        "2.1.0": (40, 51),
        "2.0.0": (40, 34),
        "1.5.0": (31, 12),
    }

    def __init__(self) -> None:
        """Initialize the feature manager."""
        self.firmware_version = ""
        self.modbus_map_version = ""
        self.hw_version = ""

    def initialize(self, device_name: str, lookup_registers: list[int]) -> None:
        """Initialize and validate device based on lookup registers.

        Args:
            device_name: Display name for logging.
            lookup_registers: Input registers 1-3 from device.

        Raises:
            ValueError: If device is not supported or firmware is invalid.

        """
        if not self._validate_lookup_registers(lookup_registers):
            msg = (
                "Failed to retrieve data from the air handling unit. "
                "Please check your network settings, the air handling unit is "
                "powered on and connected to a network. Then restart Home Assistant "
                "and try again."
            )
            raise ValueError(msg)

        # registers[0] = hardware version (3x00001)
        # registers[1] = firmware version, registers[2] = modbus map version
        self.hw_version = self._version_string(lookup_registers[0])
        self.firmware_version = self._version_string(lookup_registers[1])
        self.modbus_map_version = self._version_string(lookup_registers[2])

        self._validate_firmware_version()
        self._log_device_info(device_name)

    def get_register_lengths(self) -> tuple[int, int]:
        """Get input and holding register counts based on modbus map version.

        Returns:
            Tuple of (input_register_count, holding_register_count).

        """
        for map_version_str, (input_len, holding_len) in sorted(
            self.REGISTER_LENGTHS_BY_MAP_VERSION.items(),
            key=lambda x: version.parse(x[0]),
            reverse=True,
        ):
            if version.parse(self.modbus_map_version) >= version.parse(map_version_str):
                LOGGER.debug(
                    "Setting input register length to %d and holding register length to %d",
                    input_len,
                    holding_len,
                )
                return (input_len, holding_len)

        # Fallback to minimum version
        return self.REGISTER_LENGTHS_BY_MAP_VERSION["1.5.0"]

    @staticmethod
    def _validate_lookup_registers(lookup_registers: list[int]) -> bool:
        """Validate that lookup registers contain sufficient data.

        Args:
            lookup_registers: Input registers 1-3 from device.

        Returns:
            True if valid, False otherwise.

        """
        return len(lookup_registers) >= 3

    def _validate_firmware_version(self) -> None:
        """Validate firmware version is supported.

        Raises:
            ValueError: If firmware version is not supported.

        """
        # Check for unsupported firmware versions
        if self.firmware_version in self.UNSUPPORTED_FIRMWARE_VERSIONS:
            msg = (
                f"Air handling unit firmware version {self.firmware_version} is unsupported. "
                "Please downgrade or upgrade to another version."
            )
            LOGGER.error(msg)
            raise ValueError(msg)

        # Check minimum Modbus version
        if version.parse(self.modbus_map_version) < version.parse(self.MIN_MODBUS_VERSION):
            msg = f"Device firmware version {self.firmware_version} is unsupported. Please upgrade to a newer version."
            LOGGER.error(msg)
            raise ValueError(msg)

    def _log_device_info(self, device_name: str) -> None:
        """Log device information and versions.

        Args:
            device_name: Display name for logging.

        """
        headline = f"----- {device_name} -----"
        LOGGER.info(headline)
        LOGGER.info("  Firmware version: %s", self.firmware_version)
        LOGGER.info("  Modbus map version: %s", self.modbus_map_version)
        LOGGER.info("-" * len(headline))

    @staticmethod
    def _version_string(register_value: int) -> str:
        """Convert register value to version string.

        Example: 270 -> "2.7.0"

        Args:
            register_value: The register value to convert.

        Returns:
            Version string (e.g., "2.7.0").

        """
        digits = str(max(0, register_value))
        if len(digits) >= 3:
            return f"{digits[0]}.{digits[1]}.{digits[2]}"
        if len(digits) == 2:
            return f"{digits[0]}.{digits[1]}.0"
        return f"{digits[0]}.0.0"


__all__ = ["AirfiFeatureManager"]
