# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
