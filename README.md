# Airfi

<img src="https://raw.githubusercontent.com/janmilinds/ha-airfi/main/docs/logo.svg" alt="Airfi Logo" width="120" />

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

A user-friendly Home Assistant integration for Airfi ventilation units: local control, with native Home Assistant
entities that are ready for Apple Home and voice assistants.

> ⚠️ **Updating from 1.x?** Version 2.0.0 moves the integration to a domain of its own, and the Marketplace cannot
> update it in place. Before you update, follow [Moving from version 1.x](#moving-from-version-1x): delete your
> units, uninstall Airfi and download it again, then add the units back with the same names.

## Why Airfi for Home Assistant

- **Real Home Assistant entities.** The unit appears as a fan with on/off (away and at home on the unit, so the ventilation never stops completely) and speed, together with temperature and humidity sensors that carry the right device classes. They work in Apple Home through HomeKit Bridge, and are designed to work with Google Assistant, Alexa and Assist in the same way.
- **Finds the unit and follows it.** Home Assistant offers Airfi units on your network under **Discovered** on its own, and setup can search the network too, so there is no IP address to look up. If a unit later gets a new IP address, the integration notices as soon as the unit tells the network, and carries on.
- **Local only.** Home Assistant talks to the unit over your own network with Modbus TCP. No cloud account and no internet connection are needed.

Also included: a guided repair when the unit stays unreachable, a warning for unsupported firmware, switches only for the functions your unit's firmware offers, diagnostics with the host and serial number removed, and translations in English, Finnish, Swedish and Polish.

## Features

- Temperature sensors:
  - Outdoor air
  - Extract air
  - Exhaust air
  - Supply air
- Relative humidity sensor
- Diagnostic sensors: firmware version, Modbus register version, connection (disabled by default)
- Change the unit's IP address without removing it
- Reads the unit every 10 seconds; all entities update together

## Supported models

The unit's software needs Modbus register map 2.0 or newer; map 1.5 and firmware 3.2.0 are not supported. The integration includes model mapping for Airfi model families and variants (L/R, Electric/Water, ENT/C5/mini where applicable), including:

- 60, 100, 130, 150
- 250 (Electric/Water)
- 350 (Electric/Water)
- C5 variants
- 53 mini / miniENT variants
- ENT variants (60/130/150/250/350)

## Installation

**Prerequisite:** Home Assistant 2026.11 or newer, which has the Marketplace built in (**Settings** > **Marketplace**).

In the Marketplace, open this repository and select **Download**.

### Moving from version 1.x

⚠️ Version 2.0.0 changes the integration's domain from `airfi` to `airfi_home`, and the Marketplace cannot update it in
place. The move takes a few steps:

1. Take a backup of Home Assistant.
2. Note each unit's name and one of its entity IDs, any entity ID you changed by hand, the entities you turned on
   yourself, and the settings of any helper that uses the unit's entities.
3. Delete each unit, ignored ones included: **Settings** > **Devices & services** > **Airfi** > ⋮ > **Delete**. When
   you delete the last one, Home Assistant asks whether to uninstall Airfi too: select **Uninstall**. If it does not
   ask, uninstall Airfi in the Marketplace.
4. Uninstalling also removes Airfi from the Marketplace, so open it again with this button, download Airfi, and
   restart Home Assistant.

   [![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=janmilinds&repository=ha-airfi&category=integration)

5. Add each unit again with the same name it had, or leave the name empty if it had the default: **Settings** >
   **Devices & services** > **Add integration** > **Airfi**.
6. Compare the entity IDs with the ones you noted, and change any that differ back in the entity's settings.
7. Turn on again the entities you had turned on yourself. The fireplace, sauna and boosted cooling switches are off by
   default.
8. Create again the helpers that used the unit's entities, with the entity IDs they had. Statistics, Trend, History
   stats and Change device type helpers are deleted together with the entity they follow.

Once the entity IDs are the same as before, history, automations and dashboards carry on. Areas, custom names and
icons, labels and hidden entities are set again. The full steps are in
[Getting Started](docs/user/GETTING_STARTED.md#moving-from-version-1x).

<!-- ha-marketplace:exclude-start -->

Airfi is not in the Marketplace catalog, so the button below adds it as a custom repository first:

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=janmilinds&repository=ha-airfi&category=integration)

Airfi 1.0.0 is the last release for Home Assistant 2026.4 to 2026.10. There, install [HACS](https://hacs.xyz/) first, add this repository in HACS as a custom repository of the category **Integration**, download it, and restart Home Assistant.

<details>
<summary><strong>Manual installation</strong></summary>

1. Download `airfi_home.zip` from the [latest release](https://github.com/janmilinds/ha-airfi/releases/latest).
2. Extract it into `custom_components/airfi_home/` in your Home Assistant configuration directory.
3. Restart Home Assistant.

</details>

<!-- ha-marketplace:exclude-end -->

## Setup

### Add the integration

Install the integration first.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=airfi_home)

Or go to **Settings** > **Devices & services** > **Add integration** > **Airfi**.

### Found automatically

Home Assistant offers Airfi units under **Settings** > **Devices & services** > **Discovered**, without you starting a setup:

- The first unit appears when Home Assistant sees it on your network, by the address of its network card. This happens when the unit gets its IP address from your router, or at the latest within an hour.
- Once one unit is set up, further units appear within seconds.

Select **Add**, give the unit a name if you want one, and confirm. A unit with a static IP address may not be offered on its own; add it as below.

### Search and manual setup

When you start setup yourself, Airfi searches your network for units. The search usually takes about 5 seconds, and
up to about 15 seconds on some networks.

If the search finds nothing, or you choose to, add the unit manually with:

- Host (IP or hostname)
- Serial number (digits only)
- Model
- Name (optional; Airfi and the model when left empty)

If Home Assistant finds the unit but it does not answer, setup asks for the unit's [Modbus ID](docs/user/CONFIGURATION.md#modbus-id), which is almost always 1. Units found by Home Assistant are checked the same way.

### Reconfigure

Reconfigure updates the host, and the Modbus ID under **Advanced**. Serial number and model remain fixed for the configured device entry. An address that belongs to another Airfi unit is refused; when Home Assistant cannot tell which unit is at the address, it asks you to confirm.

### Update interval

The integration reads the unit every 10 seconds. There is no option for it; to read the unit on your own schedule instead, see [Data update mechanism](docs/user/CONFIGURATION.md#data-update-mechanism).

## Created entities

### Fan

- Fan: on/off state and speed percentage (mapped to device speed levels). Off sets the unit to away mode, which runs the ventilation at the lowest speed; on returns it to at-home mode and its previous speed

### Sensors

- Outdoor air temperature
- Extract air temperature
- Exhaust air temperature
- Supply air temperature
- Relative humidity

### Number

- Supply air temperature setting (target temperature, 13–25 °C)

### Switches (disabled by default, depending on firmware)

Available when the device's Modbus register map version supports them:

- **Fireplace function** (≥ 2.5.0) — maintains overpressure indoors
- **Sauna function** (≥ 2.5.0) — prevents a humidity-triggered ventilation increase
- **Boosted cooling** (≥ 2.1.0) — monitors temperatures and boosts air volumes as needed (useful for drawing in cool outside air during summer nights)

These switches must be manually enabled. See [Configuration Reference](docs/user/CONFIGURATION.md) for details.

### Binary sensors

- Device connection (diagnostic, disabled by default)

### Diagnostic sensors (disabled by default)

- Firmware version
- Modbus register version

## Actions

The integration adds no actions of its own; control the unit through its entities.

## Network and discovery

Auto-discovery uses UDP multicast:

- Group: `239.255.100.200`
- Port: `3000`

If Home Assistant and device are on different VLANs/subnets, multicast routing is required for discovery.

The first unit is recognised through Home Assistant's DHCP discovery, by the start of its MAC address (`BC:97:40:7`). Home Assistant sees it when the unit requests an address from your router, so a unit with a static IP address may never be offered this way; set it up from **Add integration** instead, whose search finds it by its multicast announcement.

Manual setup works without multicast as long as Modbus TCP to the device is reachable.

## IP address changes

If the device IP changes, the integration follows it automatically:

- The unit announces itself regularly; an announcement from a new address is stored at once
- If no announcement arrives and the unit stops answering, it runs a short rediscovery after 90 seconds
- It matches by serial number
- It updates the stored host and continues polling

This reduces the need for manual reconfiguration after DHCP changes.

## Repairs

If the device stays unreachable for an extended period, Home Assistant can show
a repair issue for the integration. The repair flow lets you:

- Update the stored host/IP address
- Enter the unit's Modbus ID when the unit is reached but does not answer
- Validate connectivity before saving, and refuse an address that belongs to another Airfi unit
- Confirm an address when Home Assistant cannot tell which unit is there
- Reload the config entry after applying the fix

## Troubleshooting

- Check that the unit is reachable on your network, on Modbus TCP port `502`
- Look at the **Device connection** entity
- If units are not found, check that multicast reaches Home Assistant on your network
- Download diagnostics from **Settings** > **Devices & services** > **Airfi** for a closer look

Enable debug logging in [config/configuration.yaml](config/configuration.yaml):

```yaml
logger:
  default: info
  logs:
    custom_components.airfi_home: debug
```

## Documentation

- [Getting Started](docs/user/GETTING_STARTED.md) — Installation, setup, and first steps
- [Configuration Reference](docs/user/CONFIGURATION.md) — All options, entities, and supported devices

<!-- ha-marketplace:exclude-start -->

## Development

- Project guidelines: [AGENTS.md](AGENTS.md)
- Architecture notes: [docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md)
- Tests: `script/test` runs the suite, which covers 100 % of the integration's code; CI fails any change that lowers the coverage

<!-- ha-marketplace:exclude-end -->

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

[commits-shield]: https://img.shields.io/github/commit-activity/y/janmilinds/ha-airfi.svg?style=for-the-badge
[commits]: https://github.com/janmilinds/ha-airfi/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/janmilinds/ha-airfi.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40janmilinds-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/janmilinds/ha-airfi.svg?style=for-the-badge
[releases]: https://github.com/janmilinds/ha-airfi/releases
