---
id: 20260407-reauthentication-not-applicable
status: accepted
migrated-from: docs/development/DECISIONS.md
---

# Reauthentication Flow Not Applicable

## Context

The Home Assistant Gold Quality Scale requires integrations to implement a reauthentication flow for handling expired or invalid credentials.

## Decision

Reauthentication is not applicable (N/A) for this integration.

## Rationale

- Airfi ventilation units communicate via Modbus TCP, which has no authentication mechanism
- There are no credentials to expire or become invalid
- The only connection parameter is the device IP address, which is handled by the reconfigure flow
- Implementing a reauth flow would be misleading — there is nothing to reauthenticate

## Consequences

- Quality Scale rule `reauthentication-flow` is marked N/A with justification
- If Airfi firmware ever adds authentication, this decision should be revisited
- Connection failures are handled by coordinator error recovery and device rediscovery
