## Why

The demo Patient preset currently reuses a fixed MRN, allowing multiple local Patient records to represent different people with the same identifier and making downstream HL7 result matching ambiguous. Order worklists also expose different identifier columns across Local Orders and the patient-centered OIE console, so operators cannot consistently verify the patient, visit, order, and creation context requested for a work item.

## What Changes

- Allow Patient creation to allocate a stable sequential demo MRN in the format `MRN-000001` when no MRN is supplied.
- Keep explicit MRN entry available for integration testing while rejecting duplicate local MRNs with a clear validation error.
- Show a generated-on-create placeholder in Patient previews instead of predicting the next MRN in the browser.
- Preserve the selected Patient MRN and visit number as immutable snapshots on each created Order.
- Standardize Local Orders and patient-centered OIE Orders around Order ID, MRN, Visit Number, order code, status, and an unambiguous Taipei creation timestamp.
- Name the HL7 visit identifier as Visit Number and map it to `PV1-19`; retain `PV1-1` as the segment Set ID.
- Keep the current Patient-associated visit model for this change; creating a separate Encounter/Visit aggregate is deferred.

## Capabilities

### New Capabilities

- `healthcare-lab-patient-mrn-allocation`: Automatic and explicit local Patient MRN allocation, uniqueness, preview behavior, and identifier persistence across protocol modes.

### Modified Capabilities

- `healthcare-lab-order-hl7-orm-mvp`: Require persisted Orders and Local Orders presentation to expose the placer Order ID, Patient MRN, Visit Number, and creation time with their HL7 v2.5.1 mappings.
- `healthcare-lab-patient-centered-oie-console`: Require each patient-scoped OIE Order row to expose sufficient patient, visit, order, and creation context for independent operator verification.

## Impact

- Patient creation and validation in `backend/lab_store.py` and the Patient API in `app.py`.
- SQLite initialization/migration and duplicate-MRN handling for existing local data.
- Patient preset and preview behavior in `frontend/static/app.js` and `frontend/templates/index.html`.
- Local Orders and OIE Orders rendering, labels, and Taipei timestamp formatting.
- Store, API, frontend contract, and regression tests for generated and manually supplied MRNs.
- Existing HL7 PID-3, PV1-19, ORC-2, and OBR-2 payload generation and ORU matching behavior.
