"""Test the boost increase number entity."""

from types import SimpleNamespace

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.const import DOMAIN
from custom_components.airfi_home.utils.boost import HOLDING_REGISTER_BOOST_SPEED
from homeassistant.components.number import ATTR_VALUE, DOMAIN as NUMBER_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def _increase_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str | None:
    return er.async_get(hass).async_get_entity_id(NUMBER_DOMAIN, DOMAIN, f"{entry.unique_id}_boost_increase")


@pytest.fixture
def boost_increase_50(map_2_9_api: SimpleNamespace) -> SimpleNamespace:
    """Report a boost increase of 50 %, the value the developer's unit came with."""
    map_2_9_api.get_data.return_value["holding_registers"][HOLDING_REGISTER_BOOST_SPEED - 1] = 50
    return map_2_9_api


@pytest.mark.integration
async def test_boost_increase_is_a_disabled_setting(
    hass: HomeAssistant,
    boost_increase_50: SimpleNamespace,
    init_map_2_9_integration: MockConfigEntry,
) -> None:
    """The boost increase is a setting, off until the user turns it on."""
    entity_id = _increase_entity_id(hass, init_map_2_9_integration)
    assert entity_id is not None
    entry = er.async_get(hass).async_get(entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert entry.entity_category == "config"


@pytest.mark.integration
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_boost_increase_reads_and_writes_the_register(
    hass: HomeAssistant,
    boost_increase_50: SimpleNamespace,
    init_map_2_9_integration: MockConfigEntry,
) -> None:
    """The boost increase shows the unit's value and a new value is written to the unit."""
    entity_id = _increase_entity_id(hass, init_map_2_9_integration)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "50"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 70},
        blocking=True,
    )

    boost_increase_50.write_holding_register.assert_awaited_once_with(HOLDING_REGISTER_BOOST_SPEED, 70)


@pytest.mark.integration
async def test_boost_increase_is_not_offered_before_register_map_2_9(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """A unit on register map 2.7 has no boost registers, so the number is not created."""
    assert _increase_entity_id(hass, init_integration) is None


@pytest.mark.integration
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_boost_increase_is_unknown_when_the_unit_leaves_the_register_out(
    hass: HomeAssistant,
    init_map_2_9_integration: MockConfigEntry,
    map_2_9_api: SimpleNamespace,
) -> None:
    """A poll that ends before the boost speed register leaves the increase unknown, not unavailable."""
    map_2_9_api.get_data.return_value["holding_registers"] = [0] * (HOLDING_REGISTER_BOOST_SPEED - 1)
    await init_map_2_9_integration.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    entity_id = _increase_entity_id(hass, init_map_2_9_integration)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
