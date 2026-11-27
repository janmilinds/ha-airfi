"""Test the identity the base entity gives every entity and its device."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.airfi_home.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er


@pytest.mark.integration
async def test_entities_and_device_are_keyed_by_serial_number(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Every entity's unique ID and the device's identifier carry the unit's serial number."""
    device = device_registry.async_get_device_by_identifier((DOMAIN, "12345678"), init_integration.entry_id)
    assert device is not None
    assert device.serial_number == "12345678"

    entries = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    assert entries
    assert all(entry.unique_id.startswith("12345678_") for entry in entries)
    assert all(entry.device_id == device.id for entry in entries)


@pytest.mark.integration
@pytest.mark.usefixtures("mock_api")
async def test_unit_added_again_keeps_what_the_user_set(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Deleting the entry and adding the same unit again restores the device and its entities as the user left them."""
    area = area_registry.async_create("Technical room")
    device = device_registry.async_get_device_by_identifier((DOMAIN, "12345678"), init_integration.entry_id)
    assert device is not None
    device_registry.async_update_device(device.id, area_id=area.id, name_by_user="Ventilation unit")
    fan = entity_registry.async_get_entity_id("fan", DOMAIN, "12345678_fan")
    assert fan is not None
    entity_registry.async_update_entity(fan, new_entity_id="fan.house_ventilation", name="House air")
    humidity = entity_registry.async_get_entity_id("sensor", DOMAIN, "12345678_relative_humidity")
    assert humidity is not None
    entity_registry.async_update_entity(humidity, hidden_by=er.RegistryEntryHider.USER)
    temperature = entity_registry.async_get_entity_id("sensor", DOMAIN, "12345678_outdoor_air_temperature")
    assert temperature is not None
    entity_registry.async_update_entity(temperature, disabled_by=er.RegistryEntryDisabler.USER)

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    added_again = MockConfigEntry(
        domain=DOMAIN,
        data=dict(init_integration.data),
        unique_id=init_integration.unique_id,
        title=init_integration.title,
    )
    added_again.add_to_hass(hass)
    assert await hass.config_entries.async_setup(added_again.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier((DOMAIN, "12345678"), added_again.entry_id)
    assert device is not None
    assert (device.area_id, device.name_by_user) == (area.id, "Ventilation unit")
    fan_entry = entity_registry.async_get("fan.house_ventilation")
    assert fan_entry is not None
    assert (fan_entry.unique_id, fan_entry.name) == ("12345678_fan", "House air")
    humidity_entry = entity_registry.async_get(humidity)
    assert humidity_entry is not None
    assert humidity_entry.hidden_by is er.RegistryEntryHider.USER
    temperature_entry = entity_registry.async_get(temperature)
    assert temperature_entry is not None
    assert temperature_entry.disabled_by is er.RegistryEntryDisabler.USER
