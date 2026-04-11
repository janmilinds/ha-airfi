# Configuration Reference

All configuration options for the Airfi ventilation unit integration.

## Initial Setup

The integration is configured entirely through the Home Assistant UI — no YAML configuration is needed.

### Connection Settings (Config Entry)

These values are set during initial setup and stored in the config entry:

| Option | Type | Source | Description |
|--------|------|--------|-------------|
| **Host** | string | Auto-discovered or manual | IP address of the ventilation unit |
| **Serial Number** | string | Auto-discovered or manual | Unique device identifier (used as unique ID) |
| **Model Name** | string | Auto-discovered or manual | Device model (e.g., "Airfi 100 L") |

- **Port** is always 502 (Modbus TCP standard) and not configurable
- **No authentication** — Modbus TCP does not use credentials
- **No SSL** — communication is local-network Modbus TCP

When using **automatic discovery**, all three fields are populated from the device's UDP announcement. When using **manual setup**, you must enter all three fields yourself: host IP, serial number (from the device label), and model (selected from a dropdown).

### Reconfigure

To change the device IP address after setup:

1. Go to **Settings** → **Devices & Services**
2. Find "Airfi"
3. Click the three-dot menu (⋮) → **Reconfigure**
4. Enter the new IP address
5. Click **Submit**

This is useful when the ventilation unit gets a new IP address (e.g., DHCP lease change). Consider assigning a static IP or DHCP reservation to avoid this.

## Options (Runtime Settings)

After initial setup, you can modify runtime options:

1. Go to **Settings** → **Devices & Services**
2. Find "Airfi"
3. Click **Configure**

| Option | Type | Range | Default | Description |
|--------|------|-------|---------|-------------|
| **Update interval** | integer (seconds) | 5–60 | 10 | How often to poll the device for updates |

### Choosing an Update Interval

The integration polls the ventilation unit via Modbus TCP at the configured interval:

- **5 seconds** — Near real-time monitoring, higher network usage
- **10 seconds** (default) — Good balance for most setups
- **30–60 seconds** — Lower resource usage, suitable for slow-changing values

Modbus TCP is lightweight, so even 5-second polling is fine for local network use. Increase the interval only if you notice issues with multiple Modbus devices sharing the same unit.

## Entities

The integration creates one device with the following entities:

### Fan

| Entity | Description | Features |
|--------|-------------|----------|
| **Ventilation** | Main ventilation fan control | 5 speed presets (1–5), on/off |

Fan speed presets map directly to the ventilation unit's speed settings (1 = lowest, 5 = highest). Turning the fan off sets speed to 0; turning it on restores the previous speed or defaults to speed 1.

### Controls

| Entity | Type | Range | Description |
|--------|------|-------|-------------|
| **Supply air temperature setting** | number | 13–25 °C | Target supply air temperature |

The supply air temperature setting controls the target temperature for air delivered into the rooms. When the device supports minimum temperature parity (Modbus map version ≥ 2.1.0), the minimum temperature setting is also updated automatically to keep both values in sync.

### Sensors

| Entity | Device Class | Unit | State Class | Description |
|--------|-------------|------|-------------|-------------|
| **Supply air temperature** | temperature | °C | measurement | Air temperature after heat exchanger |
| **Extract air temperature** | temperature | °C | measurement | Air drawn from rooms |
| **Outdoor air temperature** | temperature | °C | measurement | Outside air intake |
| **Exhaust air temperature** | temperature | °C | measurement | Air exhausted outside |
| **Humidity** | humidity | % | measurement | Relative humidity |

All sensors report `measurement` state class, making them suitable for long-term statistics in Home Assistant.

### Diagnostic Entities (Disabled by Default)

These entities are disabled by default and can be enabled in entity settings if needed:

| Entity | Type | Category | Description |
|--------|------|----------|-------------|
| **Device connection** | binary_sensor | diagnostic | Whether the unit is reachable via Modbus TCP |
| **Firmware version** | sensor | diagnostic | Current firmware version of the unit |
| **Modbus register version** | sensor | diagnostic | Modbus register map version |

The connectivity sensor is redundant in most cases — all entities automatically become unavailable when the device is unreachable. The version sensors are useful for tracking firmware updates.

### Special Function Switches (Disabled by Default, Feature-Gated)

These switches are only available when the device's Modbus register map version supports them (≥ 2.5.0). They are disabled by default and must be manually enabled:

| Entity | Feature Flag | Description |
|--------|-------------|-------------|
| **Fireplace function** | `fireplace_function` | When activated, overpressure is maintained for 30 min. |
| **Sauna function** | `sauna_function` | When activated, prevents ventilation increase for 30 min when unit detects increase in humidity. |
| **Boosted cooling** | `boosted_cooling` | When activated, the unit monitors temperatures and boosts air volumes as needed depending on conditions. Useful especially during summer time to draw in cool outside air during nighttime. |

To enable a switch:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find the switch entity (it may be hidden — use the filter)
3. Click the settings icon (⚙)
4. Toggle **Enable entity** on

**Note:** If the switches don't appear at all, your unit's firmware may not support these features. Check the Modbus register version diagnostic sensor — it needs to be 2.5.0 or newer.

### Disabling Entities

If you don't need certain entities:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find and click the entity
3. Click the settings icon (⚙)
4. Toggle **Enable entity** off

Disabled entities are hidden from normal use and stop updating as entities in Home Assistant.

## Multiple Devices

You can add multiple Airfi ventilation units — each gets its own config entry:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Airfi"
4. The discovery scan will find any new units on the network

Each unit is identified by its serial number, so re-adding an already-configured unit is prevented automatically.

## Diagnostic Data

To download diagnostic data for troubleshooting:

1. Go to **Settings** → **Devices & Services**
2. Find "Airfi" → click on the device
3. Click **Download Diagnostics**

Diagnostic data includes coordinator statistics, Modbus connection status, device information, and entity states. **Sensitive data (host IP, serial number) is automatically redacted.**

## Network Requirements

The integration communicates with the ventilation unit over your local network:

- **Protocol:** Modbus TCP
- **Port:** 502 (standard Modbus port)
- **Discovery:** UDP multicast on 239.255.100.200:3000

Ensure:

- Home Assistant and the ventilation unit are on the same network (or routable)
- Port 502 is not blocked by firewalls
- UDP multicast is allowed if using automatic discovery

## Supported Devices

The integration supports all Airfi ventilation unit models with Modbus register version 1.5.0 or newer. Supported models (L = left, R = right variant):

| Model Family | Variants |
|-------------|----------|
| **60** | 60 L, 60 R |
| **100** | 100 L, 100 R |
| **130** | 130 L, 130 R |
| **150** | 150 L, 150 R |
| **250 Electric** | 250 L Electric, 250 R Electric |
| **250 Water** | 250 L Water, 250 R Water |
| **350 Electric** | 350 L Electric, 350 R Electric |
| **350 Water** | 350 L Water, 350 R Water |
| **C5 Electric** | C5 L Electric, C5 R Electric |
| **C5 Water** | C5 L Water, C5 R Water |
| **53 mini** | 53 mini L, 53 mini R |
| **53 miniENT** | 53 miniENT L, 53 miniENT R |
| **60 ENT** | 60 ENT L, 60 ENT R |
| **130 ENT** | 130 ENT L, 130 ENT R |
| **150 ENT** | 150 ENT L, 150 ENT R |
| **250 ENT Electric** | 250 ENT L Electric, 250 ENT R Electric |
| **250 ENT Water** | 250 ENT L Water, 250 ENT R Water |
| **350 ENT Electric** | 350 ENT L Electric, 350 ENT R Electric |
| **350 ENT Water** | 350 ENT L Water, 350 ENT R Water |

**Firmware note:** Firmware version 3.2.0 is known to have issues and is explicitly unsupported. Update to a newer firmware version if you encounter compatibility problems.

## Data Update Mechanism

The integration polls the ventilation unit via Modbus TCP at the configured update interval (default: 10 seconds). Each poll cycle reads:

- **Input registers** — Sensor values (temperatures, humidity, device status)
- **Holding registers** — Configuration state (fan speed, operating mode)

All entity states are updated together in a single coordinator cycle. The poll is synchronous Modbus TCP executed in an executor thread to avoid blocking the Home Assistant event loop.

**Recovery behavior:** If the device becomes unreachable for more than 90 seconds, the integration attempts to rediscover the device via UDP multicast (the device may have changed IP). If unreachable for more than 10 minutes, a repair issue is raised in the Home Assistant UI.

## Known Limitations

- **Single device per config entry** — Each ventilation unit requires its own config entry (multiple units are supported, but each is added separately).
- **No write-back for all registers** — Currently only fan speed and at-home/away mode can be controlled. Other unit settings must be configured via the unit's own interface.
- **Local network only** — Modbus TCP requires direct network access; remote access needs a VPN or similar solution.
- **Synchronous Modbus** — The pymodbus library uses synchronous calls run in an executor thread. Very short polling intervals (5 seconds) with an unstable connection may cause brief delays.
- **No authentication** — Modbus TCP has no built-in security. Ensure the ventilation unit is on a trusted network.

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) — Installation, setup, and removal
- [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues) — Report problems
