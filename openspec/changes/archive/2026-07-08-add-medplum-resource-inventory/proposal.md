## Why

Healthcare Lab already has a Medplum sidebar entry, a reusable local FHIR workflow ledger, and Patient-page Medplum sync for FHIR Patients. The Medplum entry is still disabled, so users cannot inspect the FHIR resources that local workflows create or retry failed sync work from a Medplum-centered view.

ZAC-27 adds the first Medplum resource inventory page for read-only FHIR inspection and retry-oriented operations.

## What Changes

- Enable the Medplum navigation entry and add a Medplum/FHIR inventory page.
- List supported FHIR resources: `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference`.
- Use a hybrid read model: synced resources prefer Medplum live API JSON, while pending or failed local records show the local submitted JSON.
- If Medplum live fetch fails for a synced resource, show the fetch failure and fall back to local submitted JSON with clear labeling.
- Support Patient-centered filtering for resources that directly reference a selected `Patient`.
- Show local ledger sync status, Medplum reference, last error, and retry actions for `Pending sync` and `Sync failed` records.
- Provide raw JSON preview for the selected resource, using Medplum live JSON when available.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Add Medplum resource inventory read behavior, Patient-centered resource grouping, raw JSON preview, and retry entry points on top of the existing local ledger and Medplum sync contract.

## Impact

- Affected code: `app.py`, `frontend/templates/index.html`, `frontend/static/app.js`, `frontend/static/styles.css`, and tests under `tests/`.
- Potentially affected code: `backend/lab_store.py` if the UI needs additional ledger query helpers for efficient joins.
- Affected systems: local FHIR workflow ledger and Medplum FHIR R4 API.
- No new external runtime dependency is expected.
- The page will perform Medplum read requests when viewing synced resources and must keep local pending/failed workflow intent visually distinct from canonical Medplum data.
