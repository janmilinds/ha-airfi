# Getting Started with Airfi

This guide covers installation, setup, and first steps for the Airfi custom integration for Home Assistant.

## What is Airfi?

Airfi is a Home Assistant integration for **Airfi ventilation units** (heat recovery ventilators). It communicates with the unit over **Modbus TCP** on your local network and provides:

- **Fan control** — turn ventilation on/off and set speed (5 levels)
- **Temperature sensors** — outdoor, extract, exhaust, and supply air temperatures
- **Humidity sensor** — relative humidity measurement
- **Connectivity monitoring** — device reachability status
- **Automatic device discovery** — finds Airfi units on your network via UDP multicast

## Prerequisites

- Home Assistant 2025.7.0 or newer
- HACS (Home Assistant Community Store) installed
- An Airfi ventilation unit connected to the same network as Home Assistant

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations**
3. Click the three dots in the top right corner
4. Select **Custom repositories**
5. Add this repository URL: `https://github.com/janmilinds/ha-airfi`
6. Set category to **Integration**
7. Click **Add**
8. Find **Airfi** in the integration list
9. Click **Download**
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/janmilinds/ha-airfi/releases)
2. Extract the `airfi` folder from the archive
3. Copy it to `custom_components/airfi/` in your Home Assistant configuration directory
4. Restart Home Assistant

## Initial Setup

After installation, add the integration:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Airfi**
4. The integration will automatically scan your network for Airfi devices

### Automatic Discovery

If an Airfi unit is found on your network, you will see a list of discovered devices showing the serial number and model. Select your device and click **Submit**.

### Manual Configuration

If automatic discovery does not find your device (e.g., the unit is on a different subnet), choose **Configure manually** and enter:

- **Host/IP Address** — the IP address of your Airfi ventilation unit
- **Serial Number** — the device serial number (found on the unit's label)
- **Model** — select your model from the dropdown list

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

| Entity | Type | Description |
|--------|------|-------------|
| **Fan** | `fan` | Main ventilation control — on/off and 5-speed control |
| **Outdoor air temperature** | `sensor` | Temperature of incoming outdoor air (°C) |
| **Extract air temperature** | `sensor` | Temperature of air extracted from the building (°C) |
| **Exhaust air temperature** | `sensor` | Temperature of air exhausted outdoors (°C) |
| **Supply air temperature** | `sensor` | Temperature of air supplied to the building (°C) |
| **Relative humidity** | `sensor` | Indoor relative humidity (%) |
| **Device connection** | `binary_sensor` | Whether the unit is reachable (diagnostic, disabled by default) |
| **Firmware version** | `sensor` | Current firmware version (diagnostic, disabled by default) |
| **Modbus register version** | `sensor` | Modbus register map version (diagnostic, disabled by default) |

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

## Configuration Options

After setup, you can adjust the polling interval:

1. Go to **Settings** → **Devices & Services**
2. Find **Airfi** and click **Configure**
3. Set **Update interval** (5–60 seconds, default 10)

See [CONFIGURATION.md](./CONFIGURATION.md) for full details.

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
2. Look at the **API connectivity** binary sensor — it shows `off` when the unit is unreachable
3. The integration automatically attempts to rediscover the device if its IP changes (e.g., DHCP lease renewal)
4. Review logs: **Settings** → **System** → **Logs**
5. Try reloading the integration

### Device Unreachable Repair

If the unit is unreachable for more than 10 minutes, a **repair issue** is created in Home Assistant. You can resolve it by fixing the network issue and clicking **Fix** in the repairs panel — the integration will re-test connectivity.

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: warning
  logs:
    custom_components.airfi: debug
```

Add this to `configuration.yaml`, restart, and reproduce the issue.

## Removing the Integration

To remove the integration:

1. Go to **Settings** → **Devices & Services**
2. Find **Airfi**
3. Click the three dots menu (⋮) and select **Delete**

This removes the integration, its device, and all associated entities. No manual cleanup is needed — the integration does not create any files outside of Home Assistant's database.

## Next Steps

- See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options
- Report issues at [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues)

## Support

- [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues) — bug reports and feature requests
- [GitHub Discussions](https://github.com/janmilinds/ha-airfi/discussions) — questions and help
