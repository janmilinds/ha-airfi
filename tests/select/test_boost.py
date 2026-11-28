"""Test the boost time select entity."""

from collections.abc import Callable, Coroutine
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.const import DOMAIN
from custom_components.airfi_home.utils.boost import HOLDING_REGISTER_BOOST_TIME
from homeassistant.components.select import ATTR_OPTION, DOMAIN as SELECT_DOMAIN, SERVICE_SELECT_OPTION
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def _boost_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str | None:
    return er.async_get(hass).async_get_entity_id(SELECT_DOMAIN, DOMAIN, f"{entry.unique_id}_boost_timer")


@pytest.mark.integration
@pytest.mark.parametrize(
    ("remaining", "expected"),
    [
        (0, "0"),
        (1, "30"),
        (30, "30"),
        (31, "60"),
        (47, "60"),
        (90, "90"),
        (119, "120"),
        (120, "120"),
        (150, "120"),
    ],
)
async def test_boost_shows_the_shortest_option_covering_the_remaining_time(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
    report_holding_register: Callable[[int, int], Coroutine[None, None, None]],
    remaining: int,
    expected: str,
) -> None:
    """A running 47-minute boost shows 60 minutes; no boost shows 0."""
    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, remaining)

    entity_id = _boost_entity_id(hass, init_map_2_9_integration)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == expected


@pytest.mark.integration
@pytest.mark.parametrize(("option", "minutes"), [("30", 30), ("120", 120), ("0", 0)])
async def test_selecting_an_option_writes_the_boost_timer(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
    map_2_9_api: SimpleNamespace,
    option: str,
    minutes: int,
) -> None:
    """Selecting an option writes its minutes to the boost time, and 0 stops the boost."""
    entity_id = _boost_entity_id(hass, init_map_2_9_integration)
    reads = map_2_9_api.get_data.await_count

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )

    map_2_9_api.write_holding_register.assert_awaited_once_with(HOLDING_REGISTER_BOOST_TIME, minutes)
    assert map_2_9_api.get_data.await_count > reads


@pytest.mark.integration
async def test_selected_option_shows_until_the_unit_reports(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
    report_holding_register: Callable[[int, int], Coroutine[None, None, None]],
) -> None:
    """The chosen option shows at once, and the next poll replaces it with what the unit reports."""
    entry = init_map_2_9_integration
    entity_id = _boost_entity_id(hass, entry)

    with patch.object(entry.runtime_data.coordinator, "async_request_refresh", AsyncMock()):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "90"},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == "90"

    await report_holding_register(HOLDING_REGISTER_BOOST_TIME, 0)
    assert hass.states.get(entity_id).state == "0"


@pytest.mark.integration
async def test_boost_is_not_offered_before_register_map_2_9(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A unit on register map 2.7 has no boost registers, so the select is not created."""
    assert _boost_entity_id(hass, init_integration) is None


@pytest.mark.integration
async def test_boost_is_unknown_when_the_unit_leaves_the_register_out(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
    map_2_9_api: SimpleNamespace,
) -> None:
    """A poll that ends before the boost time register leaves the boost unknown, not unavailable."""
    map_2_9_api.get_data.return_value["holding_registers"] = [0] * (HOLDING_REGISTER_BOOST_TIME - 1)
    await init_map_2_9_integration.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_id = _boost_entity_id(hass, init_map_2_9_integration)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
