# Codex Review - add-dcm4chee-order-pacs-status-ui - 2026-07-13

## Findings

### P2 - dcm4chee console omits DICOM orders for non-DICOM patients

- File: `frontend/static/app.js:1110`
- `dcm4cheeConsolePatients()` only seeds the console from patients whose `protocolVersion` is `DICOM` or whose patient row already has `dcm4chee.patient`. The same console then filters orders through `selectedDcm4cheePatientId` in `dcm4cheeConsoleOrders()`. Healthcare Lab supports DICOM MWL orders for non-DICOM local patients via the DICOMweb Patient preflight path documented in this change; those patients may not satisfy either predicate. In that supported flow, the dcm4chee sidebar can render no selected patient/orders, hiding the MWL sync/query/result status that ZAC-41 is meant to expose. Seed the console from the union of DICOM patients, dcm4chee-synced patients, and any patient referenced by a DICOM order, or render unassigned DICOM orders independently.

## Open Questions / Assumptions

- Assumption: DICOM MWL orders for non-DICOM local patients remain supported in this project; this is reflected in the ZAC-41 devlog and prior backend test coverage.
- Manual browser click-through was not repeated as part of this review; `/dev-test` verified Docker-served HTML/API and unit coverage.

## Verification Context

- Latest `/dev-test` passed Docker `tests.test_app` (109 tests), JS syntax, OpenSpec strict validation, dcm4chee profile diagnostics, and Docker-served HTML marker checks.
