# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0-rc.2] - 2026-04-16

### Changed

- All device data is now read in a single connection per update cycle, and state changes no longer trigger an additional immediate read — reduces network load on the device and improves update reliability
- Sensor and binary sensor entities now update in parallel, improving how quickly Home Assistant reflects the latest device state
- **Breaking:** Renamed `device_connectivity` binary sensor (was `api_connectivity`) — update any automations or dashboards using `binary_sensor.<name>_api_connectivity` to `binary_sensor.<name>_device_connectivity`
- When device discovery cannot open a network socket (e.g. the port is already in use), you now see a clear error instead of a generic "No devices found" message
- Setup now shows separate error messages for unsupported firmware versus unreadable device data

### Fixed

- Fan and switch states shown in Home Assistant could get stuck after a manual change and not reflect actual device state; state is now confirmed on every scheduled update
- Version number from device registers could fail to parse with certain values — now handled gracefully
- A port conflict during automatic device IP recovery could crash the integration instead of gracefully skipping rediscovery

### Removed

- Diagnostics snapshot contained leftover placeholder fields and a duplicate host entry

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/compare/v1.0.0-rc.1...v1.0.0-rc.2

## [1.0.0-rc.1] - 2026-04-15

### Added

- Raise a repairs issue for unsupported firmware version
- Supply air temperature state attribute for temperature setting entity

### Changed

- Adjustments to default icons

### Fixed

- Missing temperature unit for supply air temperature setting
- Read modbus register version directly from input registers

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.4...v1.0.0-rc.1

## [1.0.0-beta.4] - 2026-04-11

### Added

- Supply air temperature setting
- Function switches for fireplace, sauna and boosted cooling functions (if supported by device firmware)
- Mock AHU device for development and testing purposes, simulating Modbus TCP communication and dynamic sensor values.

### Fixed

- Fan state UI bouncing when turning fan on/off; added optimistic state handling to update HA state immediately.

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.3...v1.0.0-beta.4

## [1.0.0-beta.3] - 2026-04-08

### Added

- Icon translations and icon mappings for states.
- Diagnostic insights: new diagnostic sensor entities and diagnostics support for deeper device visibility.
- Repairs & utilities: expanded repairs flow support and added an error-mapping utility.
- Documentation: added Quality Scale report and expanded user/developer docs.

### Changed

- Translations updated.
- Refactor & robustness: centralised error handling, consolidated version/options logic, moved initial device handshake, and removed several unused listeners.
- Docs overhaul: major updates to README, Getting Started and Configuration docs;
- Improved config flow typing and integration options.
- Test coverage up to 100% for all major modules; added tests for config flow, coordinator, API client, entities and repairs.

### Fixed

- Stability fixes: hardened recovery/error mapping, fixed double-logging, corrected host handling, guarded model-name parsing, and addressed compliance issues.
- Sensor correctness: added proper state_class for temperature sensors.

### Removed

- Unnecessary service-action implementation.
- Unused coordinator/listeners.py from template.

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.2...v1.0.0-beta.3

## [1.0.0-beta.2] - 2026-03-28

### Added

- Localisation: added Finnish, Swedish and Polish translations and improved English translations. (PR #8)

### Changed

- Standardised naming and documentation; clarified wording by removing references to credentials/authentication. (PR #7)
- Removed reauthentication-related UI/logic (the integration does not use authentication). (PR #7)
- Refactored entity descriptions to use `translation_key` for proper localisation (fan and sensor entities). (PR #8)
- Coordinator / API client focus moved to Modbus communication and host rediscovery handling; diagnostics, services and messages updated to reflect Modbus usage (e.g. `api` → `modbus`, adjusted diagnostic fields). (PR #7)

### Removed

- Removed reauthentication flow, and several unused helper modules/templates that were only relevant to credential flows. (PR #7)

### Notes

- These changes are primarily documentation, i18n and code-quality improvements that simplify the config flow and enable translations. Related to issue #5.

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.1...v1.0.0-beta.2

## [1.0.0-beta.1] - 2026-03-27

First public beta release.

### Added

- Airfi device integration for Home Assistant via Modbus TCP
- Automatic device discovery over UDP multicast
- Config flow with autodiscovery selection, manual fallback, and reconfigure support
- Fan entity with speed control (5 levels) and at-home/away mode (on/off)
- Temperature sensors (supply air, extract air, outdoor air, exhaust air)
- Relative humidity sensor
- Connectivity binary sensor
- Reload data service action
- Diagnostics support with sensitive data redaction
- Repair flow for connection issues
- Brand assets (light and dark icons) for Home Assistant brands proxy
- Local installation via HACS custom repository

---
**Full Changelog**: https://github.com/janmilinds/ha-airfi/commits/v1.0.0-beta.1
