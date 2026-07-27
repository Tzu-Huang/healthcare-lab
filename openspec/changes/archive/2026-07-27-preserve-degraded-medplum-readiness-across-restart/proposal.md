## Why

Medplum Save-and-test failures currently exist only in process memory, so recreating `lab-app` can turn a previously degraded required integration into `ready` and incorrectly mark guided setup complete. ZAC-80 must preserve a bounded, secret-safe verification outcome across restart so ZAC-78 and its parent closure gate can rely on authoritative readiness.

## What Changes

- Persist the latest bounded Medplum verification outcome without credentials, tokens, FHIR bodies, or arbitrary upstream content.
- Bind each outcome to the effective Medplum configuration revision so a save, secret mutation, bootstrap change, or removal invalidates stale evidence.
- Derive Medplum readiness from both valid persisted configuration and its matching verification outcome after application restart or container recreation.
- Keep failed or not-yet-verified required Medplum setup incomplete until a matching Save-and-test succeeds.
- Add migration, repository, service, API/readiness, restart, and redaction coverage.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-medplum-settings-profile`: Require bounded Medplum verification outcomes to persist across restart and remain tied to the configuration revision they verified.
- `healthcare-lab-settings-workspace`: Require guided readiness to distinguish verified, degraded, stale, and not-yet-verified Medplum configuration across restart.

## Impact

- Affects SQLite schema migration and typed integration-settings persistence.
- Affects Medplum Save-and-test orchestration and readiness composition.
- Preserves the existing public Settings and readiness envelopes while tightening their state semantics.
- Adds focused automated restart/recreation and sensitive-value rejection tests; no new external dependency is required.
