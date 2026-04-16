"""Coordinator data processing for Modbus payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AirfiDeviceData:
    """Normalized device payload for coordinator consumers."""

    firmware_version: str
    modbus_register_version: str
    model: str
    holding_registers: list[int]
    input_registers: list[int]
    lookup_registers: list[int]


def parse_device_data(raw_data: dict[str, Any]) -> AirfiDeviceData:
    """Parse raw Modbus payload from API client into typed structure."""
    input_registers = [int(value) for value in raw_data.get("input_registers", [])]
    holding_registers = [int(value) for value in raw_data.get("holding_registers", [])]
    lookup_registers = [int(value) for value in raw_data.get("lookup_registers", [])]

    return AirfiDeviceData(
        firmware_version=str(raw_data.get("firmware_version", "0.0.0")),
        modbus_register_version=str(raw_data.get("modbus_register_version", "0.0.0")),
        model=str(raw_data.get("model", "Airfi")),
        holding_registers=holding_registers,
        input_registers=input_registers,
        lookup_registers=lookup_registers,
    )
