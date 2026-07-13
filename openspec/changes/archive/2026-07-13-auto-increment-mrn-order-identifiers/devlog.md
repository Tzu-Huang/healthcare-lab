---
change: auto-increment-mrn-order-identifiers
date: 2026-07-13
---

## Context

The Patient demo preset reused one fixed MRN, which allowed different local Patient records to share an identifier and made downstream result matching ambiguous. Local Orders and patient-centered OIE Orders also exposed different subsets of the patient, visit, order, and creation identifiers needed for operator verification.

## Implementation

- Added a persistent local identifier sequence that allocates monotonic demo MRNs beginning with `MRN-000001`, survives restarts, avoids reuse after deletion, and skips manually occupied candidates.
- Preserved explicit MRN entry and reject new exact duplicates before Patient payload creation or downstream synchronization.
- Updated Patient presets and HL7, FHIR, GDT, and DICOM previews to show `Generated on create` before persistence and the allocated MRN afterward.
- Verified that generated MRNs propagate through all Patient protocol payloads and remain stable in Order snapshots.
- Added `visitNumber` to Order API views while preserving the existing `visitId` alias.
- Standardized Local Orders and patient-centered OIE Orders around Order ID, MRN, Visit Number, code, status, and Taipei creation time, retaining OIE ACK/send operations.
- Documented identifier allocation, uniqueness scope, and PID-3/PV1-19/ORC-2/OBR-2 mappings.

## Decisions

- Kept MRN allocation server-authoritative instead of predicting the next value in the browser.
- Enforced new exact duplicate rejection at the application store/transaction boundary rather than adding a SQLite unique index that could prevent legacy duplicate demo databases from initializing.
- Preserved existing duplicate MRNs instead of silently rewriting persisted clinical identifiers and payloads.
- Deferred a separate Encounter/Visit aggregate; this change retains the current Patient-associated Visit Number model.

## Validation Plan

- Run Python compilation checks for application, backend, and tests.
- Run JavaScript syntax validation for `frontend/static/app.js`.
- Run the complete Python automated test suite.
- Validate the OpenSpec change strictly and run `git diff --check`.

## Follow-ups

- Introduce an Encounter-focused model when the demo needs multiple visits per Patient.
- Add a deliberate legacy duplicate-MRN migration before considering a database unique index.
- Exercise live OIE, Medplum, and dcm4chee paths when an external integration environment is available.

## Verification

### Round 1 (2026-07-13)

- `python -m py_compile app.py backend\\lab_store.py backend\\dashboard_services.py backend\\lab_operations.py backend\\gdt_adapter.py tests\\test_app.py tests\\test_lab_store.py tests\\test_b64_pdf.py tests\\test_gdt_adapter.py`: passed.
- `node --check frontend\\static\\app.js`: passed.
- `python -m unittest discover -s tests -v`: passed, 149 tests.
- `openspec validate auto-increment-mrn-order-identifiers --strict`: passed.
- `git diff --check`: passed.
- Live OIE, Medplum, and dcm4chee verification was not required for this local identifier and presentation change.

## Code Review

### Round 1 (2026-07-13)

- Source: `openspec/changes/auto-increment-mrn-order-identifiers/review/2026-07-13_codex-review.md`.
- Finding: No actionable correctness, data-integrity, compatibility, or test-coverage issues found.
- Result: PASS.
- Residual risk: Existing duplicate MRNs remain unchanged; uniqueness is enforced at the application store boundary; external service and browser-layout smoke tests remain environment-specific.
