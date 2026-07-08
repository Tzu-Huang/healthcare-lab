---
change: add-fhir-order-servicerequest-task
date: 2026-07-08
---

## Context

ZAC-28 enables the Order page FHIR mode for ECG orders. The workflow creates a local FHIR order anchor, builds a `ServiceRequest`, syncs it to Medplum, then generates and syncs a dependent ECG worklist `Task`.

The implementation assumes the selected Patient is already a synced FHIR Patient with a Medplum `Patient/<id>` reference. Patient auto-create or auto-sync is intentionally out of scope.

## Implementation

- Added backend FHIR order validation and resource builders in `backend/lab_store.py` for `ServiceRequest` and generated `Task`.
- Added `/api/orders` FHIR mode handling in `app.py`, including ServiceRequest-first sync, Task creation after the ServiceRequest reference is known, and independent sync failure preservation.
- Enabled Order page FHIR mode in `frontend/templates/index.html` and added the requested full ServiceRequest field set directly on the Order page.
- Updated `frontend/static/app.js` for FHIR order presets, payload collection, synced Patient validation, ServiceRequest preview JSON, create submission, and Local Orders ServiceRequest/Task sync status display.
- Added store, API, and frontend regression coverage for FHIR order creation, Patient precondition validation, ServiceRequest/Task references, partial sync failure, field visibility, and the datetime-local validation fix.

## Decisions

- Use the existing local FHIR workflow ledger and sequential equivalent sync strategy instead of a FHIR transaction Bundle.
- Persist a local order anchor before Medplum sync so failed or partial sync attempts remain visible in Local Orders.
- Generate Task automatically with `status=requested`, `intent=order`, `focus=ServiceRequest/<id>`, and `for=Patient/<id>`; no manual Task form is included.
- Store FHIR ServiceRequest JSON in the local order payload field for FHIR mode while keeping HL7/GDT order paths mode-specific.
- Accept compact text inputs for advanced ServiceRequest list/reference fields in this ticket rather than building resource pickers for every field.

## Validation Plan

- Run `openspec validate add-fhir-order-servicerequest-task --strict`.
- Run `node --check frontend/static/app.js`.
- Run `python -m unittest discover -s tests`.
- Review the current branch after fixes and record review findings under the change review directory.

## Code Review

### Round 1 (2026-07-08)

- Review file: `openspec/changes/add-fhir-order-servicerequest-task/review/2026-07-08_codex-review.md`.
- Result: changes requested.
- Must-fix: FHIR `datetime-local` occurrence values were blocked by the shared HL7 `requestedAt` timestamp validator.

### Round 2 (2026-07-08)

- Review file: `openspec/changes/add-fhir-order-servicerequest-task/review/2026-07-08_codex-review-r2.md`.
- Result: approved.
- Findings: none. The prior datetime-local validation issue was fixed.
- Residual risk: manual browser smoke and real Medplum smoke remain unrun; automated tests mock Medplum sync.

## Follow-ups

- Run a manual browser smoke for the full Order page FHIR flow.
- Run a real Medplum smoke when credentials and environment are available.
- Consider richer pickers or validation for advanced ServiceRequest reference fields after the basic workflow lands.
