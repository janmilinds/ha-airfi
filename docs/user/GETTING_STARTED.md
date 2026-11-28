# Getting Started with Airfi

This guide covers installation, setup, and first steps for the Airfi custom integration for Home Assistant.

## What is Airfi?

Airfi is a Home Assistant integration for **Airfi ventilation units** (heat recovery ventilators). It communicates with the unit over **Modbus TCP** on your local network and provides:

- **Fan control** — turn ventilation on/off and set speed (5 levels)
- **Temperature sensors** — outdoor, extract, exhaust, and supply air temperatures
- **Humidity sensor** — relative humidity measurement
- **Connectivity monitoring** — device reachability status
- **Automatic device discovery** — finds Airfi units on your network

## Prerequisites

- Home Assistant 2026.11 or newer
- An Airfi ventilation unit connected to the same network as Home Assistant, with software on Modbus register map 2.0 or newer (not firmware 3.2.0)

Airfi 1.0.0 is the last release for Home Assistant 2026.4 to 2026.10; there it installs through HACS as a custom
repository.

## Installation

### Via the Marketplace (Recommended)

Airfi is not in the Marketplace catalog, so add it as a custom repository:

1. Select the button below. It opens this repository in the Marketplace of your Home Assistant instance and offers to
   add it as a custom repository.

   [![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=janmilinds&repository=ha-airfi&category=integration)

2. Select **Download**

### Manual Installation

1. Download `airfi_home.zip` from the [latest release](https://github.com/janmilinds/ha-airfi/releases/latest)
2. Extract it into `custom_components/airfi_home/` in your Home Assistant configuration directory
3. Restart Home Assistant

## Moving from version 1.x

Version 2.0.0 changes the integration's domain from `airfi` to `airfi_home`, so it now installs into
`custom_components/airfi_home/` instead of `custom_components/airfi/`. Home Assistant cannot move a unit from one
domain to another, and the Marketplace does not update an integration whose domain changes: its update stops with a
message asking you to uninstall and install again. So each unit is deleted, the integration is installed again, and
each unit is added again. Done in this order, the new entities take over the entity IDs of the old ones, so history,
long-term statistics, automations and dashboards carry on.

1. **Take a backup** of Home Assistant: **Settings** > **System** > **Backups**.
2. **Write down each unit's name and one of its entity IDs**, for example `fan.airfi_model_60_l_ventilation`. The
   entity IDs were formed from the name the unit got when it was first added: Airfi and its model, or the name you
   typed then. Renaming the device later did not change them, so the entity ID shows which name to use. Also write
   down:
   - every entity ID you changed by hand
   - the entities you turned on yourself: the fireplace, sauna and boosted cooling switches and the diagnostic
     sensors are off by default
   - the settings of every helper that uses the unit's entities, such as a Statistics helper for a daily mean
     temperature
3. **Delete each unit:** go to **Settings** > **Devices & services** > **Airfi**, open the unit's ⋮ menu and select
   **Delete**. Delete units you chose to ignore too: the Marketplace does not uninstall an integration while any of
   its entries remain. Delete first: if the old unit is still there when the new one is added, the new entities get
   IDs ending in `_2`, and history and automations do not follow.
4. **Install again:** when you delete the last unit, Home Assistant asks whether to uninstall Airfi too. Select
   **Uninstall**; if it does not ask, open Airfi in the Marketplace and uninstall it there. Uninstalling also removes
   Airfi from the Marketplace, so open it again with the button under [Installation](#via-the-marketplace-recommended),
   download it, and restart Home Assistant. Uninstalling removes `custom_components/airfi/`. If you installed
   manually, delete that folder yourself and extract `airfi_home.zip` into `custom_components/airfi_home/`.
5. **Add each unit again:** **Settings** > **Devices & services** > **Add integration** > **Airfi**. The search finds
   the unit at once; you can also select it under **Discovered** if Home Assistant already offers it there. **Give the
   unit the same name it had**: leave the name empty if its entity IDs start with `airfi_model_`, and type the custom
   name otherwise. A different name gives different entity IDs.
6. **Check the entity IDs** against your notes, and change any that differ back in the entity's settings (⚙️ >
   **Entity ID**); history, automations and dashboards follow the ID.
7. **Set again** what belonged to the old entries, since Home Assistant keeps it per domain:
   - entity IDs you changed by hand: rename the new entity to the old ID
   - entities you turned on yourself: turn them on again on the device page, under the entities that are not shown
   - areas, labels, custom entity names and icons
   - hidden entities
   - unit and display precision you chose for an entity
   - which entities are exposed to voice assistants, and their aliases
   - the logger key, if you enabled debug logging: `custom_components.airfi_home`
8. **Create the helpers again** that used the unit's entities, and give each the entity ID it had. Statistics, Trend,
   History stats and Change device type helpers are deleted together with the entity they follow; other helpers stay,
   and work again once the entity IDs are the same as before.

## Initial Setup

### Found by Home Assistant

After installation and a restart, Home Assistant offers Airfi units under **Settings** > **Devices & services** > **Discovered**:

- The first unit appears when Home Assistant sees it on your network. This happens when the unit gets its IP address from your router, or at the latest within an hour.
- Once one unit is set up, further units appear within seconds, and a unit that gets a new IP address is followed at once.

Select **Add**, give the unit a name if you want one, and select **Submit**.

A unit with a static IP address may not be offered on its own. Add it as below; the search finds it without the IP address.

### Adding a unit yourself

1. Go to **Settings** > **Devices & services**.
2. Select **Add integration**.
3. Search for **Airfi**.
4. The integration searches your network for Airfi units.

If an Airfi unit is found, you will see a list of discovered devices showing the serial number and model. Select your device and select **Submit**.

### Manual Configuration

If automatic discovery does not find your device (e.g., the unit is on a different subnet), choose **Configure manually** and enter:

- **Host/IP Address** — the IP address of your Airfi ventilation unit
- **Serial Number** — the device serial number, digits only (found on the unit's type plate, or in the Airfi app or web interface)
- **Model** — select your model from the dropdown list
- **Name** — optional; left empty, the device is named Airfi and its model. The entity IDs are formed from this name, so when you add a unit again, give it the name it had before

Modbus TCP port 502 is used automatically. Click **Submit** to test the connection and complete setup.

## What Gets Created

After successful setup, the integration creates:

### Device

A device entry representing your Airfi ventilation unit with:

- Manufacturer: Airfi
- Model name (e.g., Model 60 L, Model 100 R)
- Serial number
- Firmware and hardware versions

### Entities

| Entity                      | Type            | Description                                                     |
| --------------------------- | --------------- | --------------------------------------------------------------- |
| **Fan**                     | `fan`           | Main ventilation control — on/off and 5-speed control           |
| **Outdoor air temperature** | `sensor`        | Temperature of incoming outdoor air (°C)                        |
| **Extract air temperature** | `sensor`        | Temperature of air extracted from the building (°C)             |
| **Exhaust air temperature** | `sensor`        | Temperature of air exhausted outdoors (°C)                      |
| **Supply air temperature**  | `sensor`        | Temperature of air supplied to the building (°C)                |
| **Relative humidity**       | `sensor`        | Indoor relative humidity (%)                                    |
| **Device connection**       | `binary_sensor` | Whether the unit is reachable (diagnostic, disabled by default) |
| **Firmware version**        | `sensor`        | Current firmware version (diagnostic, disabled by default)      |
| **Modbus register version** | `sensor`        | Modbus register map version (diagnostic, disabled by default)   |

All temperature and humidity sensors support **long-term statistics** in Home Assistant.

## First Steps

### Dashboard Cards

Add a card to monitor your ventilation unit:

```yaml
type: entities
title: Airfi Ventilation
entities:
  - entity: fan.airfi_fan
  - entity: sensor.airfi_supply_air_temperature
  - entity: sensor.airfi_extract_air_temperature
  - entity: sensor.airfi_outdoor_air_temperature
  - entity: sensor.airfi_relative_humidity
```

### Automations

**Example — boost ventilation when humidity is high:**

```yaml
automation:
  - alias: "Boost ventilation on high humidity"
    trigger:
      - trigger: numeric_state
        entity_id: sensor.airfi_relative_humidity
        above: 70
    action:
      - action: fan.set_percentage
        target:
          entity_id: fan.airfi_fan
        data:
          percentage: 100
```

**Example — reduce ventilation at night:**

```yaml
automation:
  - alias: "Night mode ventilation"
    trigger:
      - trigger: time
        at: "22:00:00"
    action:
      - action: fan.set_percentage
        target:
          entity_id: fan.airfi_fan
        data:
          percentage: 20
```

### More Use Cases

- **Monitor indoor air quality** — track temperatures and humidity over time using Home Assistant's long-term statistics
- **Away mode control** — automatically switch to low-speed away mode when everyone leaves home (via presence detection) and restore normal speed on return
- **Dashboard monitoring** — display real-time ventilation status, temperatures, and humidity on Lovelace dashboards
- **Alert on problems** — get notified when the ventilation unit becomes unreachable or humidity rises above a threshold

## Update interval

The integration reads the unit every 10 seconds, and there is nothing to configure after setup. To read the unit on your own schedule, see [Data update mechanism](./CONFIGURATION.md#data-update-mechanism).

## Troubleshooting

### Connection Failed

If setup fails with connection errors:

1. Verify the IP address is correct and reachable (`ping <ip>`)
2. Ensure nothing is blocking Modbus TCP port 502
3. Check that the Airfi unit is powered on and connected to the network
4. Check Home Assistant logs for detailed error messages

### Entities Not Updating

If entities show "Unavailable" or don't update:

1. Check that the ventilation unit is powered on and on the network
2. Look at the **Device connection** binary sensor — it shows `off` when the unit is unreachable
3. The integration automatically attempts to rediscover the device if its IP changes (e.g., DHCP lease renewal)
4. Review logs: **Settings** → **System** → **Logs**
5. Try reloading the integration

### Device Unreachable Repair

If the unit is unreachable for more than 10 minutes, a **repair issue** is created in Home Assistant. Select **Fix** in the repairs panel and enter the unit's IP address; the integration tests the connection before saving.

- If the address belongs to another Airfi unit, it is refused.
- If Home Assistant cannot tell which unit is at the address, it asks you to confirm. This is normal on networks where the units' announcements do not reach Home Assistant.

### A unit is not offered under Discovered

- A unit with a static IP address does not ask your router for an address, so Home Assistant may not see it. Add it from **Add integration**.
- Home Assistant must be on the same network as the unit. In a container, use host networking.
- If the search in **Add integration** finds nothing either, the units' announcements do not reach Home Assistant; see [Network requirements](./CONFIGURATION.md#network-requirements), or add the unit manually.

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: warning
  logs:
    custom_components.airfi_home: debug
```

Add this to `configuration.yaml`, restart, and reproduce the issue.

## Removing the Integration

To remove the integration:

1. Go to **Settings** → **Devices & Services**
2. Find **Airfi**
3. Click the three dots menu (⋮) and select **Delete**

This removes the integration, its device, and all associated entities. No manual cleanup is needed — the integration does not create any files outside of Home Assistant's database.

If you add the same unit again within 30 days, Home Assistant restores what you had set: the device's area and name, and each entity's ID, name, icon, and hidden or disabled state. History and automations then carry on as before.

## Next Steps

- See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options
- Report issues at [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues)

## Support

- [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues) — bug reports and feature requests
- [GitHub Discussions](https://github.com/janmilinds/ha-airfi/discussions) — questions and help
