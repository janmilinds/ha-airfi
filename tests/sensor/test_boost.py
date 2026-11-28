"""Test the boost end time sensor."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.const import DOMAIN
from custom_components.airfi_home.utils.boost import HOLDING_REGISTER_BOOST_TIME
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

START = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)


def _end_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(SENSOR_DOMAIN, DOMAIN, f"{entry.unique_id}_boost_end")
    assert entity_id is not None
    return entity_id


@pytest.mark.integration
async def test_boost_end_is_unknown_without_a_boost(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
) -> None:
    """With no boost running there is no end time."""
    assert hass.states.get(_end_entity_id(hass, init_map_2_9_integration)).state == STATE_UNKNOWN


@pytest.mark.integration
async def test_boost_end_stays_put_while_the_boost_counts_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_map_2_9_integration: MockConfigEntry,
    report_holding_register: Callable[[int, int], Coroutine[None, None, None]],
) -> None:
    """The end time is set when a boost starts and does not wander as the whole-minute countdown runs."""
    entry = init_map_2_9_integration
    entity_id = _end_entity_id(hass, entry)
    freezer.move_to(START)
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 30)
    expected = (START + timedelta(minutes=30)).isoformat()
    assert hass.states.get(entity_id).state == expected

    freezer.tick(timedelta(seconds=15))
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 29)
    assert hass.states.get(entity_id).state == expected

    freezer.tick(timedelta(seconds=50))
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 29)
    assert hass.states.get(entity_id).state == expected


@pytest.mark.integration
async def test_boost_end_moves_when_the_boost_changes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_map_2_9_integration: MockConfigEntry,
    report_holding_register: Callable[[int, int], Coroutine[None, None, None]],
) -> None:
    """A boost restarted with another time moves the end time, and a stopped boost clears it."""
    entry = init_map_2_9_integration
    entity_id = _end_entity_id(hass, entry)
    freezer.move_to(START)
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 30)

    freezer.tick(timedelta(minutes=5))
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 60)
    assert hass.states.get(entity_id).state == (START + timedelta(minutes=65)).isoformat()

    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 0)
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


@pytest.mark.integration
async def test_boost_end_is_not_offered_before_register_map_2_9(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A unit on register map 2.7 has no boost registers, so the sensor is not created."""
    registry = er.async_get(hass)
    assert registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, f"{init_integration.unique_id}_boost_end") is None
