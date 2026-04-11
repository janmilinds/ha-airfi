"""Tests for platform async_setup_entry functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.airfi.binary_sensor import async_setup_entry as binary_sensor_setup
from custom_components.airfi.data import AirfiData
from custom_components.airfi.fan import async_setup_entry as fan_setup
from custom_components.airfi.number import async_setup_entry as number_setup
from custom_components.airfi.sensor import async_setup_entry as sensor_setup
from custom_components.airfi.switch import async_setup_entry as switch_setup


def _make_entry(hass, *, features: dict[str, bool] | None = None) -> MagicMock:
    """Build a mock config entry with runtime data containing a coordinator."""
    feature_manager = MagicMock()
    feature_manager.has_feature = MagicMock(side_effect=lambda f: (features or {}).get(f, False))

    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.feature_manager = feature_manager
    entry = MagicMock()
    entry.runtime_data = AirfiData(
        client=MagicMock(),
        coordinator=coordinator,
        integration=MagicMock(),
    )
    entry.entry_id = "test-entry-id"
    return entry


@pytest.mark.unit
async def test_binary_sensor_setup_entry_adds_entities(hass) -> None:
    """Test that binary_sensor platform adds connectivity entities."""
    entry = _make_entry(hass)
    added = []
    await binary_sensor_setup(hass, entry, added.extend)
    assert len(added) >= 1


@pytest.mark.unit
async def test_fan_setup_entry_adds_entities(hass) -> None:
    """Test that fan platform adds fan entities."""
    entry = _make_entry(hass)
    added = []
    await fan_setup(hass, entry, added.extend)
    assert len(added) >= 1


@pytest.mark.unit
async def test_sensor_setup_entry_adds_entities(hass) -> None:
    """Test that sensor platform adds humidity and temperature entities."""
    entry = _make_entry(hass)
    added = []
    await sensor_setup(hass, entry, added.extend)
    assert len(added) >= 5  # 1 humidity + 4 temperature


@pytest.mark.unit
async def test_number_setup_entry_adds_entities(hass) -> None:
    """Test that number platform adds temperature number entity."""
    entry = _make_entry(hass)
    added = []
    await number_setup(hass, entry, added.extend)
    assert len(added) >= 1


@pytest.mark.unit
async def test_switch_setup_entry_adds_entities_when_features_available(hass) -> None:
    """Test that switch platform adds entities when features are supported."""
    entry = _make_entry(
        hass,
        features={
            "fireplace_function": True,
            "sauna_function": True,
            "boosted_cooling": True,
        },
    )
    added = []
    await switch_setup(hass, entry, added.extend)
    assert len(added) == 3


@pytest.mark.unit
async def test_switch_setup_entry_adds_no_entities_when_features_unavailable(hass) -> None:
    """Test that switch platform adds no entities when features are not supported."""
    entry = _make_entry(hass, features={})
    added = []
    await switch_setup(hass, entry, added.extend)
    assert len(added) == 0
