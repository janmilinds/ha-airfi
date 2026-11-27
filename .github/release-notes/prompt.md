# How the release notes for Airfi read

Airfi is a Home Assistant integration for Airfi ventilation units. It talks to the unit over the local network
(Modbus TCP), finds units on its own, and gives them native Home Assistant entities: a fan for the ventilation,
temperature and humidity sensors, a supply air temperature setting, and switches for the unit's special functions. The
entities work with Apple Home through HomeKit Bridge and are designed for voice assistants.

## Who reads them

People who use Home Assistant and own an Airfi unit. Most know their unit and Home Assistant's UI, not Modbus. Some
are advanced users who read the unit's registers, set up entities for them, and want to know exactly what changed.

- Say first, in plain language, what changes for the user and what they need to do.
- Then add the technical detail an advanced user needs, where the change has one: the register address (such as
  `4x00051`), the register map or firmware version it depends on, the entity it affects. Keep it short, after the
  plain sentence, never instead of it.
- Leave out how the integration works inside: its classes, functions, tests and internal terms such as coordinator,
  config entry or listener. Network details (multicast, DHCP) only where a user has to act on them, for example to
  let discovery reach Home Assistant.

## Order

1. Anything a user must do **before or while updating** comes first, as numbered steps, with nothing above it but one
   sentence of context. A release that moves the integration to a new domain, or otherwise needs units deleted and added
   again, repeats the steps from the README's "Moving from version 1.x" section word for word, including what carries
   over and what must be set again.
2. Other changes that break something a user relies on: say what stops working and what to do instead.
3. What is new, grouped by what the user notices, not by code area.
4. Fixes.

## Rules

- Never mention, link or compare with any other Airfi integration or repository.
- Use Home Assistant's own names for its menus, in bold, with `>` between steps: **Settings** > **Devices & services**.
- "Unit" or "device" for the ventilation unit, never "air handling unit".
- No internal work: tests, refactoring, tooling, agent review.
