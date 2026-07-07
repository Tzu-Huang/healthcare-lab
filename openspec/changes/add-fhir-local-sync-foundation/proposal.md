## Why

Healthcare Lab needs a local-first FHIR foundation so Patient, Order, AP, and Result workflows can persist their intended FHIR resources before Medplum is reachable. This prevents data loss during Medplum, OAuth, or network failures and gives later workflow tickets a common sync contract instead of each flow inventing its own persistence and retry behavior.

## What Changes

- Add a durable local FHIR workflow ledger backed by SQLite.
- Track local source record, FHIR resource type, deterministic idempotency identifier, Medplum resource id/reference, sync status, last sync time, sync error, and raw OperationOutcome body.
- Define local-to-Medplum mapping coverage for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance`.
- Add shared sync helper/API behavior for idempotent create/update retry flows.
- Preserve Healthcare Lab's project boundary by implementing reusable persistence and sync infrastructure, not full AP result-packaging UI.

## Capabilities

### New Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Local-first FHIR persistence and Medplum sync tracking for Healthcare Lab workflow records.

### Modified Capabilities

- None.

## Impact

- Affected code: `backend/lab_store.py`, `app.py`, tests under `tests/`, and potentially small frontend/API display surfaces for sync status.
- Affected systems: local SQLite database and Medplum FHIR R4 API.
- No new external runtime dependency is expected.
- Later Healthcare Lab FHIR Patient, Order, AP, and Result workflow tickets should depend on this foundation.
