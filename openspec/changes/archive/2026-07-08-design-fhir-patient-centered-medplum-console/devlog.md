---
change: design-fhir-patient-centered-medplum-console
date: 2026-07-08
---

## Context

ZAC-31 changes the Healthcare Lab Medplum page from an inventory-first FHIR resource table into a GDT-console-like Patient-centered FHIR console. The agreed layout keeps the Patient list as the primary navigation surface, uses dropdowns for `ServiceRequest` and `DiagnosticReport`, shows lightweight workflow rows for related resources, and keeps raw FHIR JSON in a single bottom console.

## Implementation

- Added FHIR inventory metadata in `app.py` for resource summaries and referenced FHIR resources so the frontend can label dropdowns and group related rows without fetching full live JSON for every row.
- Reworked `frontend/templates/index.html` Medplum markup into a Patient list, selected Patient workspace, ServiceRequest/DiagnosticReport dropdowns, related-resource area, and bottom JSON console.
- Replaced the Medplum frontend table renderer with Patient-centered state and rendering helpers in `frontend/static/app.js`.
- Preserved live Medplum JSON preview, local submitted fallback behavior, and retry actions through the existing `/api/fhir/records/<id>/preview` and `/api/fhir/records/<id>/sync` paths.
- Added a follow-up fix so sync-status filtering recomputes the selected Patient before workspace rendering, and no-Patient states do not show all orders/reports.
- Updated template/script/API assertions in `tests/test_app.py`.

## Decisions

- Keep the console read-oriented and retry-oriented; do not add destructive Medplum operations.
- Do not add separate rich viewers for Task, Observation, or DocumentReference; selecting a row updates the bottom JSON console.
- Use local ledger metadata for grouping and labels, while keeping actual selected-resource JSON preview on the existing live/fallback preview endpoint.
- Keep backend changes scoped to inventory response metadata rather than changing persistence or Medplum sync behavior.

## Validation Plan

- Run JavaScript syntax validation for `frontend/static/app.js`.
- Compile `app.py`.
- Run focused unit suites for API/template/store coverage.
- Validate the OpenSpec change strictly.
- Review the branch against `main`.

## Follow-ups

- Add browser or DOM-level coverage for Medplum console state transitions, especially sync-status filter changes, no-Patient inventory states, dropdown selection, related-resource row clicks, and JSON console updates.

## Code Review

### Round 1 (2026-07-08)

- Verdict: changes requested.
- Findings: stale selected Patient after sync-status filtering; all ServiceRequest/DiagnosticReport records could appear when no Patient was selected.
- Result: fixed in `6968c8e fix(ZAC-31): keep Medplum patient selection consistent`.

### Round 2 (2026-07-08)

- Verdict: no issues found.
- Notes: prior P2 findings were addressed; residual risk remains around lack of browser/DOM-level state transition coverage.
