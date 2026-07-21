## Why

Healthcare Lab persists the intended OIE result-listener configuration, but the runtime still uses process configuration and requires an operator to start it manually. The application needs a safe single-process startup lifecycle so OIE can deliver ORU results after each lab-app restart without making a listener bind failure take down the web application.

## What Changes

- Read the listener host, port, MLLP framing, and auto-start intent from the persisted OIE Settings profile as the only runtime configuration source.
- Attempt listener startup once during lab-app composition when auto-start is enabled; preserve web availability and expose a degraded state with an actionable error when binding fails.
- Make Start and Retry apply the latest persisted Settings idempotently, retain explicit Stop and Status operations, and ensure Stop affects only the current process rather than changing auto-start intent.
- Keep Settings saves separate from runtime mutation. Mark successful listener-setting updates as requiring a listener retry or lab-app restart, and show a persistent UI reminder until the user reloads the running listener state.
- Preserve existing ORU parsing, ACK generation, persistence, duplicate detection, Patient/Order matching, and unmatched-result behavior.
- Document that listener ownership is limited to one lab-app process and is not coordinated across replicas.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-oie-settings-profile`: Report when saved listener intent has not been applied to runtime and require the Settings UI to remind the operator to retry or restart.
- `healthcare-lab-patient-centered-oie-console`: Add persisted-settings auto-start, idempotent Start/Retry, temporary Stop, degraded status, and single-process listener behavior.
- `healthcare-lab-modular-frontend`: Place the post-save listener reload reminder in the modular Settings owners without implementing unrelated managed-Channel UI.

## Impact

- Runtime and composition: `backend/runtime/oie_result_listener.py`, `backend/app_factory.py`, and narrow persisted-settings wiring.
- Services and HTTP: OIE listener lifecycle coordination plus Settings and listener status/start/retry/stop response contracts in `backend/services/` and `backend/api/oie.py`.
- Frontend: the modular Settings API, state, component, view, template, and style owners needed for the save reminder; the operational OIE console no longer supplies editable listener endpoints.
- Verification and documentation: focused runtime, service, API, composition, frontend interaction, regression, and single-process deployment coverage.
- No OIE Channel mutation, multi-replica coordination, HLAB pull/fetch workflow, or change to existing ORU processing semantics.
