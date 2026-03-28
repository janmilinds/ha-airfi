# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
