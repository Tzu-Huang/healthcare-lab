## Why

Healthcare Lab currently models every Medplum-backed FHIR ECG order as a paired `ServiceRequest` and generated worklist `Task`, even though this lab only needs the clinical order and does not manage a separate Task lifecycle. Removing the redundant Task path makes `ServiceRequest` the single order resource and eliminates misleading frontend acceptance and worklist behavior.

## What Changes

- Stop generating, storing, or synchronizing a FHIR `Task` when an Order-page FHIR order is created; create and synchronize only its `ServiceRequest`.
- Remove `Task` from supported FHIR mappings, Medplum inventory/read paths, order response composition, patient order grouping, related-resource navigation, summaries, and retry/preview UI.
- Make FHIR order acceptance depend only on a successfully synchronized `ServiceRequest` reference.
- Update active tests, documentation, and workflow diagrams to describe the ServiceRequest-only order flow.
- Preserve existing local ledger rows and remote Medplum Task resources as historical data; this change performs no destructive data migration or remote deletion.
- **BREAKING** Remove the generated `fhir.task` member from FHIR order API responses and remove `Task` from the supported resource-type and inventory contracts.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Replace the paired ServiceRequest/Task order workflow with ServiceRequest-only creation, synchronization, inventory, status, and patient-console behavior.

## Impact

- FHIR resource support, order orchestration, inventory, preview, and response composition in `app.py` and `backend/lab_store.py`.
- Medplum patient console and Local Orders rendering in `frontend/templates/index.html` and `frontend/static/app.js`.
- Backend, API, and frontend contract tests under `tests/`.
- Active OpenSpec requirements, README guidance, workflow documentation, and generated diagram assets.
- No dependency, database-schema, authentication, Medplum server configuration, or destructive historical-data changes.
