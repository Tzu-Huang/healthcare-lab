---
change: add-dashboard-gdt-ecg-order-flow
date: 2026-07-06
---

## Context

ZAC-22 adds a Healthcare Lab dashboard-started flow for creating local 12-lead resting ECG GDT orders without requiring OpenEMR.

## Implementation

- Added local GDT ECG order persistence with patient snapshots, raw GDT payload, optional attachment URL, and refresh-safe order listing.
- Added `/api/gdt/orders` GET/POST for dashboard-created local GDT orders.
- Added fixed MVP `8402=EKG01` validation/rendering and rejection for non-MVP test codes such as `EKG04` and `ERGO01`.
- Added a dashboard OpenEMR/GDT `ECG Order` action that opens the Order page in GDT ECG mode.
- Enabled GDT ECG mode on the Order page while preserving the existing HL7 v2.3.1 ORM/OIE flow.
- Added a compact GDT patient creation path inside the Order flow.
- Updated project boundary notes to clarify Healthcare Lab owns local GDT order creation/status, not the full GDT AP Simulator workflow.

## Decisions

- Use a dedicated `/api/gdt/orders` path instead of overloading HL7-specific `/api/orders`.
- Persist GDT orders in a separate local table instead of reusing HL7 ORM ACK/send fields.
- Use GDT set type `6302` for the MVP local order request payload.
- Keep the MVP test type fixed at `8402=EKG01`; no dynamic test catalog in this change.
- Treat browser click-through as manual residual validation; automated coverage verifies API, template wiring, and JavaScript syntax.

## Validation Plan

- Run backend tests for GDT order creation without OpenEMR.
- Run backend tests for fixed `8402=EKG01` and rejection of non-MVP codes.
- Run API tests for listing created GDT orders after refresh.
- Run frontend structure checks and JavaScript syntax checks for dashboard GDT order action and Order page GDT mode.
- Run OpenSpec strict validation.

## Follow-ups

- Run a browser-level click-through smoke test before demo if UI ergonomics need visual confirmation.
- Re-check exact downstream GDT field expectations when connecting to a real bridge/device.

## Verification

### Round 1 (2026-07-06)

- pass: `python -m unittest discover -s tests -v` (51 tests)
- pass: `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`
- pass: `node --check frontend\static\app.js`
- pass: `openspec validate add-dashboard-gdt-ecg-order-flow --strict`
- skip: browser-level manual click-through smoke; no browser runtime was started for this verification round.

## Code Review

### Round 1 (2026-07-06)

- Source: `openspec/changes/add-dashboard-gdt-ecg-order-flow/review/2026-07-06_codex-review.md`
- Verdict: No blocking issues found.
- Findings: No blocking issues found in the current `main...HEAD` diff.
- Residual risk: browser-level manual smoke was not performed; GDT 6302 field selection should be re-checked for future real device/bridge integration.

