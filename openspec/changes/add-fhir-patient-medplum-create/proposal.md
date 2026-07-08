## Why

Healthcare Lab's Patient page can already preview FHIR R4 Patient JSON and the project has a reusable local FHIR workflow ledger with Medplum sync support. The Patient create flow still stops at a local Patient record, so FHIR mode does not yet produce a Medplum-backed Patient resource with visible sync status, retry, or Medplum reference.

ZAC-26 closes that gap by wiring Patient FHIR mode into the existing ledger and Medplum sync foundation.

## What Changes

- Extend the Patient FHIR form and demo preset with common Medplum/FHIR Patient fields such as active status, email, structured address fields, and optional managing organization context.
- Keep FHIR Patient creation local-first: create the local Patient record, create or update the paired FHIR workflow ledger record, then immediately attempt Medplum sync.
- Preserve local Patient and FHIR ledger records when Medplum sync fails, including sync error and retryable request payload.
- Display FHIR sync status, Medplum reference, and sync error in Local Patients.
- Add row-level retry for FHIR Patients that are not yet synced.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Add Patient-page Medplum-backed FHIR Patient create behavior on top of the existing local ledger and sync contract.

## Impact

- Affected code: `backend/lab_store.py`, `app.py`, `frontend/templates/index.html`, `frontend/static/app.js`, and tests under `tests/`.
- Affected systems: local SQLite Patient records, local FHIR workflow ledger, Medplum FHIR R4 API.
- No new external runtime dependency is expected.
- The create path will perform a Medplum request for FHIR mode when Medplum is configured, while still succeeding locally when sync fails.

