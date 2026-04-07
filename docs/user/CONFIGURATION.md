# Configuration Reference

All configuration options for the Airfi ventilation unit integration.

## Initial Setup

The integration is configured entirely through the Home Assistant UI — no YAML configuration is needed.

### Connection Settings (Config Entry)

These values are set during initial setup and stored in the config entry:

| Option | Type | Source | Description |
|--------|------|--------|-------------|
| **Host** | string | Auto-discovered or manual | IP address of the ventilation unit |
| **Serial Number** | string | Read from device | Unique device identifier (used as unique ID) |
| **Model Name** | string | Read from device | Device model (e.g., "Airfi 100 L") |

- **Port** is always 502 (Modbus TCP standard) and not configurable
- **No authentication** — Modbus TCP does not use credentials
- **No SSL** — communication is local-network Modbus TCP

The host, serial number, and model are auto-populated when using discovery. For manual setup, you enter the host IP and the integration reads device information via Modbus.

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

### Sensors

| Entity | Device Class | Unit | State Class | Description |
|--------|-------------|------|-------------|-------------|
| **Supply air temperature** | temperature | °C | measurement | Air temperature after heat exchanger |
| **Extract air temperature** | temperature | °C | measurement | Air drawn from rooms |
| **Outdoor air temperature** | temperature | °C | measurement | Outside air intake |
| **Exhaust air temperature** | temperature | °C | measurement | Air exhausted outside |
| **Humidity** | humidity | % | measurement | Relative humidity |

All sensors report `measurement` state class, making them suitable for long-term statistics in Home Assistant.

### Binary Sensors

| Entity | Device Class | Category | Description |
|--------|-------------|----------|-------------|
| **Connectivity** | connectivity | diagnostic | Whether the unit is reachable via Modbus TCP |

### Disabling Entities

If you don't need certain entities:

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find and click the entity
3. Click the settings icon (⚙)
4. Toggle **Enable entity** off

Disabled entities stop polling and don't consume resources.

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

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) — Installation, setup, and removal
- [GitHub Issues](https://github.com/janmilinds/ha-airfi/issues) — Report problems
