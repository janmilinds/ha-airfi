# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0-beta.1](https://github.com/janmilinds/ha-airfi/compare/v1.2.1...v2.0.0-beta.1) (2026-11-27)


### ⚠ BREAKING CHANGES

* **manifest:** the Marketplace cannot update from 1.x: delete every unit, uninstall Airfi and download it again, then add each unit again with the same name; see "Moving from version 1.x" in the README
* **entity:** entities and the device are identified by the unit's serial number instead of the entry; this takes effect with the move to the new domain, where every unit is added again
* the update interval option is gone and every unit is read every 10 seconds; to read it on your own schedule, turn off polling in the entry's system options and refresh the unit from an automation

### 🎉 What's new

* **config-flow:** ask for a name in manual setup and key the unit by its announced serial ([12766fb](https://github.com/janmilinds/ha-airfi/commit/12766fb78b9922631640eed18700e780dfe9b867))
* **config-flow:** discover Airfi units automatically ([8e1d7e5](https://github.com/janmilinds/ha-airfi/commit/8e1d7e5c6b8ca093ba1cdbb092d04bb973868d24))
* **entity:** key entities and the device by the unit's serial number ([ce4c577](https://github.com/janmilinds/ha-airfi/commit/ce4c5777e36e01e26a21eb5bbe64da5da36fa9bc))
* **manifest:** install into its own domain, airfi_home ([a828245](https://github.com/janmilinds/ha-airfi/commit/a82824586c776e5e0f9eb24b1a163312ecb22323))
* poll the unit at a fixed interval ([434e68a](https://github.com/janmilinds/ha-airfi/commit/434e68aba0e67fc92649288370865096dc5bd95b))


### 🐛 Fixed

* **config-flow:** check a unit's serial number before storing its address ([2dbaba3](https://github.com/janmilinds/ha-airfi/commit/2dbaba3bcaf8d2bc4e7f714136d36ab46ecbf83d))


### Maintenance

* tell the release notes how this integration's notes read ([#105](https://github.com/janmilinds/ha-airfi/issues/105)) ([6f188db](https://github.com/janmilinds/ha-airfi/commit/6f188db339fe863ddc6360f926ee0fc13fc196a8))

## [1.2.1](https://github.com/janmilinds/ha-airfi/compare/v1.2.0...v1.2.1) (2026-11-27)


### 🐛 Fixed

* **config-flow:** add the confirmed unit when several are found ([e358996](https://github.com/janmilinds/ha-airfi/commit/e35899669f76c711bb92f61004bb0ebf53f088fd))
* **config-flow:** show the unit on the confirm form after a failed check ([95d81bb](https://github.com/janmilinds/ha-airfi/commit/95d81bb5bd017b36af5160b419196b16d98e953a))

## [1.2.0](https://github.com/janmilinds/ha-airfi/compare/v1.1.0...v1.2.0) (2026-11-26)


### 🎉 What's new

* **diagnostics:** include the raw register values ([5ece255](https://github.com/janmilinds/ha-airfi/commit/5ece255c4cc919a1a3169f2f00e901d1d6412d4d))


### 🐛 Fixed

* **api:** count a write the unit never answers as unreachable ([2f8487c](https://github.com/janmilinds/ha-airfi/commit/2f8487c81874b19fc9e3926aa3b0f880a645604b))
* **api:** free a waiting thread as soon as its request is abandoned ([4728f04](https://github.com/janmilinds/ha-airfi/commit/4728f04dc5283a1c8c3f746dbd1c43b010e67ab5))
* **api:** keep a timed-out request from overlapping the next one ([ab9e0a8](https://github.com/janmilinds/ha-airfi/commit/ab9e0a87d513cafa9626a5f369a126c97a30b5c0))
* **api:** serialize Modbus access to the device ([acadbfc](https://github.com/janmilinds/ha-airfi/commit/acadbfc9ef40b7d48ba44b2158e8ba4cb2fe899b))
* **api:** share the connection lock between clients for the same unit ([7001133](https://github.com/janmilinds/ha-airfi/commit/7001133d981bc0a0cf81472a109638fc7d83c070))
* **config-flow:** describe every setup field ([5c47ef5](https://github.com/janmilinds/ha-airfi/commit/5c47ef5ace74fdd415fc60be4a191a8ce9ff0287))
* **config-flow:** keep the setup help true when the search cannot reach the device ([0d24dff](https://github.com/janmilinds/ha-airfi/commit/0d24dffb1651ea14114c82183993e4f70032fef9))
* **config-flow:** name the search option for what it does ([64b8adf](https://github.com/janmilinds/ha-airfi/commit/64b8adf33f7c7d09599101f6cfa2cc31c837f5d7))
* **config-flow:** say the model forms the device name and entity IDs ([4bac934](https://github.com/janmilinds/ha-airfi/commit/4bac9347c71fafe0599fc11f447ffae5d21a8dfc))
* **config-flow:** say the serial must match and explain the extra list entries ([70ace41](https://github.com/janmilinds/ha-airfi/commit/70ace41bd8e315d21156a2d6151b33032615dcfe))
* **config-flow:** say what the model choice changes ([fceacdd](https://github.com/janmilinds/ha-airfi/commit/fceacddf7d7719c6e8d9d0e378f4d65b58bac35c))
* **config-flow:** set the entry up once after reconfiguring ([f60e216](https://github.com/janmilinds/ha-airfi/commit/f60e2165776cfcee8fbddf00d3ef1f38e79bb28f))
* **config-flow:** translate the device list options ([f0d9533](https://github.com/janmilinds/ha-airfi/commit/f0d9533bc9c1e9d6b32b8173c846c119fecb50d6))
* **config-flow:** word the manual option the same way everywhere in Swedish ([a29f0dd](https://github.com/janmilinds/ha-airfi/commit/a29f0dd2c2c553bf96e6f476c66131c589b7b62b))
* **coordinator:** mask the serial number in logs ([aa1cd1a](https://github.com/janmilinds/ha-airfi/commit/aa1cd1a2314d888cc7a03fce686b4f9b09abe939))
* **coordinator:** mask the serial number in the startup log ([1311258](https://github.com/janmilinds/ha-airfi/commit/1311258a5742c5e8db6cfe14ef614ee30a3b4872))
* **coordinator:** report failed writes as translated errors ([45592f4](https://github.com/janmilinds/ha-airfi/commit/45592f4dbe5b014f887f9de698aba92b728f841d))
* **coordinator:** update the device firmware version when it changes ([5a7310c](https://github.com/janmilinds/ha-airfi/commit/5a7310cb014c76cd757b9edeb08b24ef20fcf105))
* **diagnostics:** list each device's entities in a fixed order ([79a0416](https://github.com/janmilinds/ha-airfi/commit/79a0416464fb360a296ae312655e2b99ecdc6897))
* **diagnostics:** list entities that are disabled by default ([a885575](https://github.com/janmilinds/ha-airfi/commit/a8855755e184459cf878e6448681f70f971d2759))
* **discovery:** close the socket when its setup fails ([433a906](https://github.com/janmilinds/ha-airfi/commit/433a9062aadcfc1de4f11730ff22890a0f5d850e))
* **discovery:** listen only to the multicast group ([3c59794](https://github.com/janmilinds/ha-airfi/commit/3c5979421bf21b585912bedd06ebe91553ca2094))
* **entity:** confirm writes promptly ([a3740ee](https://github.com/janmilinds/ha-airfi/commit/a3740ee17b85cf89fa294beabc3bc0ecfce13aab))
* **manifest:** declare the integration category ([181d8e2](https://github.com/janmilinds/ha-airfi/commit/181d8e234529467568f8387c6f74d22cf045f44b))
* **repairs:** open the address repair without an error ([14a8d49](https://github.com/janmilinds/ha-airfi/commit/14a8d4949d846593c6b6d1023f129966e5cd3918))
* **repairs:** set the entry up once after the address is fixed ([dc5a4fd](https://github.com/janmilinds/ha-airfi/commit/dc5a4fd220bf85352d1ed773a539eae5dc375004))
* **sensor:** swap the supply and extract air temperature icons ([a991494](https://github.com/janmilinds/ha-airfi/commit/a9914949e916b16eeab800d46f6794789bc043ec))
* **switch:** offer boosted cooling from register map 2.1 ([05cb949](https://github.com/janmilinds/ha-airfi/commit/05cb949c41ce1bb335be9d2ac042e894a8d1145d))

## [1.1.0](https://github.com/janmilinds/ha-airfi/compare/v1.0.0...v1.1.0) (2026-11-25)


### 🎉 What's new

* Airfi now requires Home Assistant 2026.11 or newer. On Home Assistant 2026.4 to 2026.10, Airfi stays on 1.0.0, which keeps working; this update is not offered there. ([b99544f](https://github.com/janmilinds/ha-airfi/commit/b99544f2c74fc81689b9d9aea3a97c8665e6c904))
* Each release now includes an `airfi.zip` file, which Home Assistant installs the update from.


### 🐛 Fixed

* The **Device connection** and **Supply air temperature** entities show their attribute names instead of raw keys: *Update interval*, *Connection type* with the value *Modbus TCP*, and *Current supply air temperature*. ([72c1ee5](https://github.com/janmilinds/ha-airfi/commit/72c1ee5730555a40c9fb3f9f776ec79e0008d9f8))

## [1.0.0] - 2026-04-26

### Added

- Airfi device integration for Home Assistant via Modbus TCP
- Automatic device discovery over UDP multicast, with manual host entry as fallback and reconfigure support
- Fan entity with 5-level speed control and at-home/away mode (on/off)
- Supply air temperature setting (number entity) with current supply air temperature shown as a state attribute
- Temperature sensors: supply air, extract air, outdoor air, exhaust air
- Relative humidity sensor
- Device connectivity binary sensor
- Function switches for fireplace, sauna and boosted cooling (when supported by device firmware)
- Diagnostic sensor entities for deeper device visibility
- Diagnostics snapshot with sensitive data redaction
- Repair flow for connection issues
- Localisation: English, Finnish, Swedish and Polish translations
- Local installation via HACS custom repository

---

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/commits/v1.0.0>

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

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/compare/v1.0.0-rc.1...v1.0.0-rc.2>

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

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.4...v1.0.0-rc.1>

## [1.0.0-beta.4] - 2026-04-11

### Added

- Supply air temperature setting
- Function switches for fireplace, sauna and boosted cooling functions (if supported by device firmware)
- Mock AHU device for development and testing purposes, simulating Modbus TCP communication and dynamic sensor values.

### Fixed

- Fan state UI bouncing when turning fan on/off; added optimistic state handling to update HA state immediately.

---

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.3...v1.0.0-beta.4>

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

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.2...v1.0.0-beta.3>

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

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/compare/v1.0.0-beta.1...v1.0.0-beta.2>

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

**Full Changelog**: <https://github.com/janmilinds/ha-airfi/commits/v1.0.0-beta.1>
