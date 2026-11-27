"""
Custom integration to integrate Airfi with Home Assistant.

Connects to an Airfi ventilation unit over Modbus TCP on the local network and
exposes its fan, sensors, switches and setpoints as Home Assistant entities.

For more details about this integration, please refer to:
https://github.com/janmilinds/ha-airfi

For integration development guidelines:
https://developers.home-assistant.io/docs/creating_integration_manifest
"""

from typing import TYPE_CHECKING

from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
    ConfigEntryChange,
    DiscoveryKey,
)
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.loader import async_get_loaded_integration

from .api import AirfiApiClient
from .const import DEFAULT_MODBUS_PORT, DOMAIN, LOGGER, UPDATE_INTERVAL
from .coordinator import AirfiDataUpdateCoordinator
from .data import AirfiData
from .utils.discovery import DATA_DISCOVERY_LISTENER, AirfiDiscoveredDevice, AirfiDiscoveryListener

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import AirfiConfigEntry

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

# This integration is configured via config entries only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the integration: listen for unit announcements until Home Assistant stops.

    A unit that announces itself is offered under Discovered, or, when it is already set up and its address has
    changed, has the new address stored. A unit whose entry is removed, or no longer ignored, is offered again.
    Home Assistant runs this once the first entry exists; before that, the DHCP matcher in the manifest finds the
    first unit.
    """

    @callback
    def _async_announced(device: AirfiDiscoveredDevice) -> None:
        entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, device.unique_key)
        if entry is not None and entry.data.get(CONF_HOST) == device.host:
            return
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=device,
            discovery_key=DiscoveryKey(domain=DOMAIN, key=device.unique_key, version=1),
        )

    listener = AirfiDiscoveryListener(hass, _async_announced)
    hass.data[DATA_DISCOVERY_LISTENER] = listener

    @callback
    def _async_entry_changed(change: ConfigEntryChange, entry: ConfigEntry) -> None:
        if change is ConfigEntryChange.REMOVED and entry.domain == DOMAIN and entry.unique_id:
            listener.async_forget(entry.unique_id)

    async_dispatcher_connect(hass, SIGNAL_CONFIG_ENTRY_CHANGED, _async_entry_changed)
    await listener.async_start()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, listener.async_stop)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
) -> bool:
    """
    Set up this integration using UI.

    This is called when a config entry is loaded. It:
    1. Creates the API client with device connection details from the config entry
    2. Initializes the DataUpdateCoordinator for data fetching
    3. Performs the first data refresh
    4. Sets up the entity platforms
    5. Reloads the entry when its connection details change

    Data flow in this integration:
    1. Device is discovered automatically or configured manually in config flow
    2. Connection details are stored in the config entry
    3. API Client initialized with connection settings (api/client.py)
    4. Coordinator fetches Modbus data using the client (coordinator/base.py)
    5. Entities access data via self.coordinator.data

    This pattern ensures connection details from setup flow are used throughout
    the integration lifecycle.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        True if setup was successful.

    For more information:
    https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
    """
    # Initialize client first
    client = AirfiApiClient(
        host=entry.data[CONF_HOST],
        port=DEFAULT_MODBUS_PORT,
    )

    coordinator = AirfiDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        config_entry=entry,
        update_interval=UPDATE_INTERVAL,
    )

    # Store runtime data
    entry.runtime_data = AirfiData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_initial_setup()
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="first_refresh_failed",
            translation_placeholders={"host": entry.data.get(CONF_HOST, "unknown")},
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
) -> bool:
    """
    Unload a config entry.

    This is called when the integration is being removed or reloaded.
    It unloads the platform entities; the update listener is removed by the
    entry's unload callbacks.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        True if unload was successful.

    For more information:
    https://developers.home-assistant.io/docs/config_entries_index/#unloading-entries
    """

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: AirfiConfigEntry,
) -> None:
    """
    Reload config entry.

    This is called when the entry data changes, such as a new address from
    reconfiguring, a repair, or rediscovery. It unloads and then reloads the
    integration with the new connection details.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being reloaded.

    For more information:
    https://developers.home-assistant.io/docs/config_entries_index/#reloading-entries
    """
    await hass.config_entries.async_reload(entry.entry_id)
