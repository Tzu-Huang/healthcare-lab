## Why

Healthcare Lab's Order page currently disables FHIR order entry even though the project already has a local FHIR workflow ledger, Medplum sync support, and mapping coverage for `ServiceRequest` and `Task`. ECG FHIR ordering needs to express both the clinical order and the AP/worklist execution item.

ZAC-28 enables FHIR ECG order entry from the Order page by creating a Medplum-backed `ServiceRequest` and an automatically generated `Task`.

## What Changes

- Enable Order page FHIR mode and add a FHIR ECG order demo preset.
- Show the full `ServiceRequest` field set in Order page FHIR mode, including required status, intent, subject, priority, code, occurrence/authoredOn, requester, reason, note, and advanced reference/list fields.
- Require the selected Patient to be a FHIR Patient already synced to Medplum so `ServiceRequest.subject` and `Task.for` can reference `Patient/<id>`.
- Persist a local order anchor for FHIR orders so Local Orders can display FHIR order identity and sync state.
- Create a local FHIR ledger record for `ServiceRequest`, sync it to Medplum, then create and sync a generated `Task` whose `focus` points to the synced `ServiceRequest`.
- Display FHIR order and per-resource sync status in Local Orders and expose both resources through the Medplum inventory.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Add Order-page Medplum-backed FHIR ECG ordering using `ServiceRequest` plus generated AP/worklist `Task`.

## Impact

- Affected code: `backend/lab_store.py`, `app.py`, `frontend/templates/index.html`, `frontend/static/app.js`, `frontend/static/styles.css`, and tests under `tests/`.
- Affected systems: local SQLite order records, local FHIR workflow ledger, Medplum FHIR R4 API, Order page UI, Medplum inventory UI.
- No new runtime dependency is expected.
- FHIR order creation performs Medplum sync requests in dependency order and preserves local intent when sync fails.

