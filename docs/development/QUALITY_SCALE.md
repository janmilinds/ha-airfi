# Integration Quality Scale — Airfi

> Assessed against [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale).
> Version: 1.0.0-beta.2 | Date: 2026-04-08

## Bronze

- [ ] `action-setup` — N/A: no service actions defined (services.yaml empty)
- [x] `appropriate-polling` — Default 10s, configurable 5–60s via options flow (`iot_class: local_polling`)
- [x] `brands` — Brand icons in `brand/` (icon.png, dark_icon.png, @2x variants)
- [x] `common-modules` — Shared code in `utils/`, `entity/base.py`, `coordinator/`
- [x] `config-flow-test-coverage` — Full test coverage (36 tests in test_config_flow.py)
- [x] `config-flow` — UI config flow with discovery, manual setup, reconfigure
  - [x] Uses `data_description` in translations/en.json
  - [x] `ConfigEntry.data` for connection, `.options` for poll interval
- [x] `dependency-transparency` — Single dependency: `pymodbus>=3.8.0,<4.0.0`
- [ ] `docs-actions` — N/A: no service actions defined
- [x] `docs-high-level-description` — GETTING_STARTED.md "What is Airfi?" section
- [x] `docs-installation-instructions` — GETTING_STARTED.md: HACS + manual install steps
- [x] `docs-removal-instructions` — GETTING_STARTED.md: "Removing the Integration" section
- [ ] `entity-event-setup` — N/A: no event subscriptions (CoordinatorEntity handles lifecycle)
- [x] `entity-unique-id` — `{entry_id}_{description.key}` in entity/base.py
- [x] `has-entity-name` — `_attr_has_entity_name = True` in entity/base.py
- [x] `runtime-data` — `AirfiData` dataclass stored as `entry.runtime_data`
- [x] `test-before-configure` — Config flow calls `validate_connection()` before creating entry
- [x] `test-before-setup` — `async_config_entry_first_refresh()` with `ConfigEntryNotReady` on failure
- [x] `unique-config-entry` — Serial number as unique ID via `async_set_unique_id()`

## Silver

- [ ] `action-exceptions` — N/A: no service actions defined
- [x] `config-entry-unloading` — `async_unload_entry()` calls `async_unload_platforms()`
- [x] `docs-configuration-parameters` — CONFIGURATION.md: all options with types, ranges, defaults
- [x] `docs-installation-parameters` — GETTING_STARTED.md: host, serial number, model
- [x] `entity-unavailable` — CoordinatorEntity auto-marks unavailable on update failures
- [x] `integration-owner` — `@janmilinds` in manifest.json codeowners
- [x] `log-when-unavailable` — Coordinator logs connection loss + recovery with outage timing
- [x] `parallel-updates` — `PARALLEL_UPDATES = 1` in const.py, re-exported in all platforms
- [ ] `reauthentication-flow` — N/A: Modbus TCP has no authentication (see DECISIONS.md)
- [x] `test-coverage` — Tests for all major modules (config flow, coordinator, API, entities, repairs)

## Gold

- [x] `devices` — DeviceInfo with manufacturer, model, serial, hw_version, sw_version
- [x] `diagnostics` — diagnostics.py with `async_redact_data()` for CONF_HOST, CONF_SERIAL_NUMBER
- [x] `discovery-update-info` — Coordinator rediscovers device IP and calls `async_update_entry()`
- [x] `discovery` — UDP multicast discovery with two-stage scan (5s quick + 10s fallback)
- [x] `docs-data-update` — CONFIGURATION.md: data update mechanism section
- [x] `docs-examples` — GETTING_STARTED.md: dashboard card + 2 automation examples
- [x] `docs-known-limitations` — CONFIGURATION.md: 5 documented limitations
- [x] `docs-supported-devices` — CONFIGURATION.md: full model table (19 families)
- [x] `docs-supported-functions` — CONFIGURATION.md: entity tables with device classes and features
- [x] `docs-troubleshooting` — GETTING_STARTED.md: troubleshooting section (4 scenarios + debug logging)
- [x] `docs-use-cases` — GETTING_STARTED.md: 4 use cases after automation examples
- [ ] `dynamic-devices` — N/A: `integration_type: device`, single device per entry
- [x] `entity-category` — Diagnostic entities use `EntityCategory.DIAGNOSTIC`, primary entities have none
- [x] `entity-device-class` — temperature, humidity, connectivity device classes used
- [x] `entity-disabled-by-default` — 3 diagnostic entities disabled by default (connectivity, firmware, modbus map)
- [x] `entity-translations` — All entities use `translation_key`, translations in en/fi/pl/sv
- [x] `exception-translations` — ConfigEntryNotReady and UpdateFailed use translation_domain/translation_key
- [x] `icon-translations` — icons.json with per-entity icons, fan state-based icons
- [x] `reconfiguration-flow` — `async_step_reconfigure()` with connection validation
- [x] `repair-issues` — device_unreachable issue after 10 min outage, auto-deleted on recovery
- [ ] `stale-devices` — N/A: single device per entry, device removed with config entry

## Platinum

- [ ] `async-dependency` — pymodbus sync client with `asyncio.to_thread()` wrapper; native async not used
- [ ] `inject-websession` — N/A: Modbus TCP, not HTTP
- [ ] `strict-typing` — Not implemented (no py.typed marker)
