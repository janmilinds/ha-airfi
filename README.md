# Airfi

<img src="https://raw.githubusercontent.com/janmilinds/ha-airfi/main/docs/logo.svg" alt="Airfi Logo" width="120" />

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

Home Assistant custom integration for controlling Airfi air handling units over local Modbus TCP.

## Why Airfi for Home Assistant

- **Real Home Assistant entities.** The unit appears as a fan with on/off (away and at home on the unit, so the ventilation never stops completely) and speed, together with temperature and humidity sensors that carry the right device classes. They work in Apple Home through HomeKit Bridge, and are designed to work with Google Assistant, Alexa and Assist in the same way.
- **Finds the unit and follows it.** Setup searches your network for Airfi units, so there is no IP address to look up. If the unit later gets a new IP address, the integration finds it again by its serial number and carries on.
- **Local only.** Home Assistant talks to the unit over your own network with Modbus TCP. No cloud account and no internet connection are needed.

Also included: a guided repair when the unit stays unreachable, a warning for unsupported firmware, switches only for the functions your unit's firmware offers, diagnostics with the host and serial number removed, and translations in English, Finnish, Swedish and Polish.

## Features

- Temperature sensors:
  - Outdoor air
  - Extract air
  - Exhaust air
  - Supply air
- Relative humidity sensor
- Diagnostic sensors: firmware version, modbus register version, connectivity (disabled by default)
- Reconfigure flow for host updates without removing the integration
- Reads the unit every 10 seconds; all entities update together

## Supported Models

The integration includes model mapping for Airfi model families and variants (L/R, Electric/Water, ENT/C5/mini where applicable), including:

- 60, 100, 130, 150
- 250 (Electric/Water)
- 350 (Electric/Water)
- C5 variants
- 53 mini / miniENT variants
- ENT variants (60/130/150/250/350)

## Installation

**Prerequisite:** Home Assistant 2026.11 or newer, which has the Marketplace built in (**Settings** > **Marketplace**).

In the Marketplace, open this repository and select **Download**.

<!-- ha-marketplace:exclude-start -->

Airfi is not in the Marketplace catalog, so the button below adds it as a custom repository first:

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=janmilinds&repository=ha-airfi&category=integration)

Airfi 1.0.0 is the last release for Home Assistant 2026.4 to 2026.10. There, install [HACS](https://hacs.xyz/) first, add this repository in HACS as a custom repository of the category **Integration**, download it, and restart Home Assistant.

<details>
<summary><strong>Manual installation</strong></summary>

1. Download `airfi.zip` from the [latest release](https://github.com/janmilinds/ha-airfi/releases/latest).
2. Extract it into `custom_components/airfi/` in your Home Assistant configuration directory.
3. Restart Home Assistant.

</details>

<!-- ha-marketplace:exclude-end -->

## Setup

### Add Integration

Install the integration first.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=airfi)

Or open: Settings -> Devices & Services -> Add Integration -> Airfi.

### Discovery and Manual Setup

When setup starts, Airfi automatically scans your network for devices.

- Typical scan time is about 5 seconds
- In some environments the scan can take up to about 15 seconds

If no device is selected from discovery, you can add manually with:

- Host (IP or hostname)
- Serial number (digits only)
- Model
- Name (optional; Airfi and the model when left empty)

### Reconfigure

Reconfigure updates host only. Serial number and model remain fixed for the configured device entry.

### Update interval

The integration reads the unit every 10 seconds. There is no option for it; to read the unit on your own schedule instead, see [Data update mechanism](docs/user/CONFIGURATION.md#data-update-mechanism).

## Created Entities

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

### Switches (disabled by default, feature-gated)

Available when the device's Modbus register map version supports them:

- **Fireplace function** (≥ 2.5.0) — maintains overpressure indoors
- **Sauna function** (≥ 2.5.0) — prevents a humidity-triggered ventilation increase
- **Boosted cooling** (≥ 2.1.0) — monitors temperatures and boosts air volumes as needed (useful for drawing in cool outside air during summer nights)

These switches must be manually enabled. See [Configuration Reference](docs/user/CONFIGURATION.md) for details.

### Binary Sensors

- Device connection (diagnostic, disabled by default)

### Diagnostic Sensors (Disabled by Default)

- Firmware version
- Modbus register version

## Services

This integration currently does not expose custom service actions.

## Network and Discovery Notes

Auto-discovery uses UDP multicast:

- Group: `239.255.100.200`
- Port: `3000`

If Home Assistant and device are on different VLANs/subnets, multicast routing is required for discovery.

Manual setup works without multicast as long as Modbus TCP to the device is reachable.

## IP Address Changes

If the device IP changes, the integration can recover automatically:

- On communication failure, it runs a short rediscovery
- It matches by serial number
- It updates the stored host and continues polling

This reduces the need for manual reconfiguration after DHCP changes.

## Repairs

If the device stays unreachable for an extended period, Home Assistant can show
a repair issue for the integration. The repair flow lets you:

- Update the stored host/IP address
- Validate connectivity before saving
- Reload the config entry after applying the fix

## Troubleshooting

- Confirm device reachable on local network and Modbus TCP port `502`
- Check entity `Device connection`
- For discovery issues, verify multicast visibility in your network
- Download diagnostics from Devices & Services for deeper troubleshooting

Enable debug logging in [config/configuration.yaml](config/configuration.yaml):

```yaml
logger:
  default: info
  logs:
    custom_components.airfi: debug
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
