"""Test switch entities for Airfi special functions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.airfi.coordinator.data_processing import AirfiDeviceData
from custom_components.airfi.switch.functions import ENTITY_DESCRIPTIONS, AirfiFunctionSwitch


def _build_coordinator(holding_registers: list[int]) -> MagicMock:
    """Build a coordinator mock with holding register data."""
    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.domain = "airfi"
    config_entry.title = "Airfi Unit"
    config_entry.data = {"host": "192.168.1.10"}

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.async_set_holding_register = AsyncMock()
    coordinator.data = AirfiDeviceData(
        holding_registers=holding_registers,
        input_registers=[],
        lookup_registers=[],
        model="Airfi",
        firmware_version="3.8.1",
        modbus_register_version="3.0.0",
    )
    return coordinator


def _build_switch(key: str, holding_registers: list[int]) -> AirfiFunctionSwitch:
    """Build a switch entity with mocked async_write_ha_state for optimistic updates."""
    desc = _description_for(key)
    coordinator = _build_coordinator(holding_registers)
    entity = AirfiFunctionSwitch(coordinator, desc)
    entity.async_write_ha_state = MagicMock()
    return entity


def _registers_with(address: int, value: int) -> list[int]:
    """Return a list of holding registers with a given value at address (1-based)."""
    regs = [0] * 59  # Full 2.7.0 register set
    regs[address - 1] = value
    return regs


def _description_for(key: str):
    """Get switch description by key."""
    return next(d for d in ENTITY_DESCRIPTIONS if d.key == key)


# ——— Fireplace function tests ———


@pytest.mark.unit
def test_fireplace_is_on() -> None:
    """Test fireplace switch reads ON when register 58 is 1."""
    desc = _description_for("fireplace_function")
    coordinator = _build_coordinator(_registers_with(58, 1))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is True


@pytest.mark.unit
def test_fireplace_is_off() -> None:
    """Test fireplace switch reads OFF when register 58 is 0."""
    desc = _description_for("fireplace_function")
    coordinator = _build_coordinator(_registers_with(58, 0))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is False


@pytest.mark.unit
async def test_fireplace_turn_on() -> None:
    """Test turning on fireplace writes 1 to register 58."""
    entity = _build_switch("fireplace_function", _registers_with(58, 0))

    await entity.async_turn_on()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(58, 1)
    # Optimistic write should have been performed
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.unit
async def test_fireplace_turn_off() -> None:
    """Test turning off fireplace writes 0 to register 58."""
    entity = _build_switch("fireplace_function", _registers_with(58, 1))

    await entity.async_turn_off()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(58, 0)
    # Optimistic write should have been performed
    entity.async_write_ha_state.assert_called_once()


# ——— Sauna function tests ———


@pytest.mark.unit
def test_sauna_is_on() -> None:
    """Test sauna switch reads ON when register 57 is 1."""
    desc = _description_for("sauna_function")
    coordinator = _build_coordinator(_registers_with(57, 1))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is True


@pytest.mark.unit
def test_sauna_is_off() -> None:
    """Test sauna switch reads OFF when register 57 is 0."""
    desc = _description_for("sauna_function")
    coordinator = _build_coordinator(_registers_with(57, 0))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is False


@pytest.mark.unit
async def test_sauna_turn_on() -> None:
    """Test turning on sauna writes 1 to register 57."""
    entity = _build_switch("sauna_function", _registers_with(57, 0))

    await entity.async_turn_on()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(57, 1)
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.unit
async def test_sauna_turn_off() -> None:
    """Test turning off sauna writes 0 to register 57."""
    entity = _build_switch("sauna_function", _registers_with(57, 1))

    await entity.async_turn_off()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(57, 0)
    entity.async_write_ha_state.assert_called_once()


# ——— Boosted cooling tests ———


@pytest.mark.unit
def test_boosted_cooling_is_on() -> None:
    """Test boosted cooling reads ON when register 51 is 1."""
    desc = _description_for("boosted_cooling")
    coordinator = _build_coordinator(_registers_with(51, 1))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is True


@pytest.mark.unit
def test_boosted_cooling_is_off() -> None:
    """Test boosted cooling reads OFF when register 51 is 0."""
    desc = _description_for("boosted_cooling")
    coordinator = _build_coordinator(_registers_with(51, 0))
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is False


@pytest.mark.unit
async def test_boosted_cooling_turn_on() -> None:
    """Test turning on boosted cooling writes 1 to register 51."""
    entity = _build_switch("boosted_cooling", _registers_with(51, 0))

    await entity.async_turn_on()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(51, 1)
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.unit
async def test_boosted_cooling_turn_off() -> None:
    """Test turning off boosted cooling writes 0 to register 51."""
    entity = _build_switch("boosted_cooling", _registers_with(51, 1))

    await entity.async_turn_off()

    entity.coordinator.async_set_holding_register.assert_awaited_once_with(51, 0)
    entity.async_write_ha_state.assert_called_once()


# ——— General tests ———


@pytest.mark.unit
def test_is_on_returns_none_when_register_missing() -> None:
    """Test that is_on returns None when the register index is out of range."""
    desc = _description_for("fireplace_function")
    coordinator = _build_coordinator([0, 0])  # Only 2 registers
    entity = AirfiFunctionSwitch(coordinator, desc)

    assert entity.is_on is None


@pytest.mark.unit
def test_all_switches_disabled_by_default() -> None:
    """Test that all switch descriptions have entity_registry_enabled_default=False."""
    for desc in ENTITY_DESCRIPTIONS:
        assert desc.entity_registry_enabled_default is False, f"{desc.key} should be disabled by default"


@pytest.mark.unit
async def test_optimistic_state_set_and_cleared() -> None:
    """Test optimistic state is applied after write and cleared on coordinator update."""
    entity = _build_switch("boosted_cooling", _registers_with(51, 0))

    # After turn_on, optimistic state should be set and visible via is_on
    await entity.async_turn_on()
    assert entity._optimistic_state is True  # noqa: SLF001
    assert entity.is_on is True
    entity.async_write_ha_state.assert_called()

    # Simulate coordinator update which should clear optimistic state
    entity._handle_coordinator_update()  # noqa: SLF001
    assert entity._optimistic_state is None  # noqa: SLF001


@pytest.mark.unit
def test_entity_description_feature_flags() -> None:
    """Test that each switch description has the correct feature flag."""
    expected = {
        "fireplace_function": "fireplace_function",
        "sauna_function": "sauna_function",
        "boosted_cooling": "boosted_cooling",
    }
    for desc in ENTITY_DESCRIPTIONS:
        assert desc.feature_flag == expected[desc.key]
