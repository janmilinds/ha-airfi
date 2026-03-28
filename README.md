# Airfi

<img src="docs/logo.svg" alt="Airfi Logo" width="120" />

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

Home Assistant custom integration for controlling Airfi air handling units over local Modbus TCP.

## Features

- Local Modbus TCP integration, no cloud account required
- Automatic device discovery (UDP multicast) with manual fallback
- Fan control (on/off + speed percentage)
- Temperature sensors:
  - Outdoor air
  - Extract air
  - Exhaust air
  - Supply air
- Relative humidity sensor
- Connectivity diagnostic binary sensor
- Reconfigure flow for host updates without removing the integration
- Automatic IP recovery after device IP changes (serial-based rediscovery)
- Service for manual data refresh: `airfi.reload_data`

## Supported Models

The integration includes model mapping for Airfi model families and variants (L/R, Electric/Water, ENT/C5/mini where applicable), including:

- 60, 100, 130, 150
- 250 (Electric/Water)
- 350 (Electric/Water)
- C5 variants
- 53 mini / miniENT variants
- ENT variants (60/130/150/250/350)

## Installation

### HACS (Recommended)

Prerequisite: [HACS](https://hacs.xyz/) is installed.

This repository is not in the official HACS default list, so add it as a custom repository first:

1. Open HACS in Home Assistant.
2. Open **Integrations**.
3. Click the three-dot menu in the top-right corner.
4. Select **Custom repositories**.
5. Add repository URL: `https://github.com/janmilinds/ha-airfi`.
6. Select category: **Integration**.
7. Click **Add**.
8. Find **Airfi** in HACS and click **Download**.
9. Restart Home Assistant.

### Manual Installation

1. Copy [custom_components/airfi](custom_components/airfi) to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Setup

### Add Integration

Make sure installation is complete first (HACS or manual) and Home Assistant has been restarted after installation.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=airfi)

Or open: Settings -> Devices & Services -> Add Integration -> Airfi.

### Discovery and Manual Setup

When setup starts, Airfi automatically scans your network for devices.

- Typical scan time is about 5 seconds
- In some environments the scan can take up to about 15 seconds

If no device is selected from discovery, you can add manually with:

- Host (IP or hostname)
- Serial number
- Model

### Reconfigure

Reconfigure updates host only. Serial number and model remain fixed for the configured device entry.

## Created Entities

### Fan

- Fan: on/off state and speed percentage (mapped to device speed levels)

### Sensors

- Outdoor air temperature
- Extract air temperature
- Exhaust air temperature
- Supply air temperature
- Relative humidity

### Binary Sensors

- API connectivity (diagnostic)

## Service

### `airfi.reload_data`

Force an immediate coordinator refresh from the device.

Example:

```yaml
service: airfi.reload_data
```

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

## Troubleshooting

- Confirm device reachable on local network and Modbus TCP port `502`
- Check entity `API connectivity`
- For discovery issues, verify multicast visibility in your network
- Download diagnostics from Devices & Services for deeper troubleshooting

Enable debug logging in [config/configuration.yaml](config/configuration.yaml):

```yaml
logger:
  default: info
  logs:
    custom_components.airfi: debug
```

## Development

- Project guidelines: [AGENTS.md](AGENTS.md)
- Architecture notes: [docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md)
- User docs: [docs/user/GETTING_STARTED.md](docs/user/GETTING_STARTED.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

[commits-shield]: https://img.shields.io/github/commit-activity/y/janmilinds/ha-airfi.svg?style=for-the-badge
[commits]: https://github.com/janmilinds/ha-airfi/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/janmilinds/ha-airfi.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40janmilinds-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/janmilinds/ha-airfi.svg?style=for-the-badge
[releases]: https://github.com/janmilinds/ha-airfi/releases
