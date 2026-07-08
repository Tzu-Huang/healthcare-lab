## Why

Healthcare Lab's Medplum page already exposes the local FHIR workflow ledger as an inventory, with retry actions and raw JSON preview. As more Medplum resources appear, a flat inventory-first layout makes it hard to understand the actual clinical workflow for one patient.

ZAC-31 changes the Medplum page into a GDT-console-like, Patient-centered FHIR console. The user should pick a Patient first, then use compact dropdown controls to switch between that Patient's `ServiceRequest` orders and `DiagnosticReport` results, with one bottom console showing raw JSON for the selected resource.

## What Changes

- Replace the inventory-first Medplum page layout with a Patient-centered console layout inspired by the existing GDT console.
- Show a left-side FHIR Patient list with patient identity, sync status, ServiceRequest count, and DiagnosticReport count.
- Show a selected Patient workspace with dropdown controls for `ServiceRequest` and `DiagnosticReport`.
- Show lightweight workflow context for the selected Patient, including related `Task`, `Observation`, and `DocumentReference` references, without introducing separate rich viewers.
- Keep raw FHIR inspection in a single bottom console JSON area.
- Let selecting a Patient, ServiceRequest, DiagnosticReport, Task, Observation, or DocumentReference update the bottom JSON console.
- Preserve existing sync status, Medplum reference, last sync/update time, live Medplum preview, local submitted fallback, and non-destructive retry behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Refine the Medplum page from a resource inventory into a Patient-centered FHIR console with dropdown-driven workflow navigation and a single bottom JSON console.

## Impact

- Affected code: `app.py`, `frontend/templates/index.html`, `frontend/static/app.js`, `frontend/static/styles.css`, and tests under `tests/`.
- Potentially affected code: `backend/lab_store.py` if additional grouping metadata is needed for Patient-centered counts and dropdown labels.
- Affected systems: local FHIR workflow ledger and Medplum FHIR R4 read/preview paths.
- No new runtime dependency is expected.
- The page remains read-oriented and retry-oriented; it must not expose destructive Medplum operations.
