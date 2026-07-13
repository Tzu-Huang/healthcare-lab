---
change: add-dcm4chee-production-e2e-verification
date: 2026-07-13
---

## Context

ZAC-42 closes the Healthcare Lab to dcm4chee production-like verification gap by tying together DICOM patient precondition sync, MWL order creation/queryability, AP return, result reconciliation, and UI-visible result proof.

The change also adds a deterministic simulated AP-return path so Healthcare Lab can demonstrate returned PDF and DICOM-style result visibility without requiring a live AP for every UI verification run.

## Implementation

- Added deterministic dcm4chee E2E fixture/evidence APIs for creating a lab-safe demo patient/order, recording canonical identifiers, and exposing step-level verification state.
- Added simulated AP return support for PDF artifacts and DICOM-style metadata/object records, including source/mode labeling so simulated results are distinguishable from live dcm4chee evidence.
- Updated the Healthcare Lab UI to expose E2E verification actions, simulate AP PDF/DICOM returns, and render AP-returned PDF links, Study/Series/SOP identifiers, matched-order status, and diagnostics without requiring raw JSON inspection.
- Added an operator SOP at `docs/dcm4chee-production-e2e-verification.md` covering startup checks, ports, AE titles, MWL versus DICOMweb endpoints, live AP handoff values, simulated AP-return verification, evidence capture, and troubleshooting.
- Added automated coverage for fixture/evidence shape, simulated PDF and DICOM return exposure, response contracts, and sequential UI-exposed AP-return simulation behavior.

## Decisions

- Kept the live AP C-STORE path as a documented production-like manual verification because it depends on external dcm4chee/AP runtime interaction.
- Added a simulated AP-return path that records Healthcare Lab-visible result rows through the same patient/order DICOM result surface where practical, while clearly labeling those rows as simulated.
- Reused one simulated result generation for sequential PDF and DICOM fixture calls for the same order so the natural UI workflow keeps both returned results visible together.

## Validation Plan

- Validate the OpenSpec change strictly.
- Run frontend syntax validation for `frontend/static/app.js`.
- Run Python compilation checks for touched backend and test files.
- Run the relevant Healthcare Lab unit tests.
- Use the SOP for live AP/dcm4chee verification with exact identifiers when an AP runtime is available.

## Follow-ups

- Execute the live AP C-STORE reconciliation path in a production-like dcm4chee/AP environment before claiming live acceptance beyond the documented SOP path.
- When comparing live and simulated runs, use the evidence endpoint/SOP because the patient payload follows the existing latest result generation display behavior.

## Verification

### Round 1 (2026-07-13)

- `openspec validate add-dcm4chee-production-e2e-verification --strict`: passed.
- `node --check frontend\static\app.js`: passed.
- `python -m py_compile app.py backend\lab_store.py tests\test_app.py`: passed.
- `python -m unittest tests.test_app tests.test_lab_store`: passed, 135 tests.
- Live AP C-STORE reconciliation was not executed; the manual path and identifiers are documented in the SOP.

### Round 2 (2026-07-13)

- `openspec validate add-dcm4chee-production-e2e-verification --strict`: passed.
- `node --check frontend\static\app.js`: passed.
- `python -m py_compile app.py backend\lab_store.py tests\test_app.py`: passed.
- `python -m unittest tests.test_app tests.test_lab_store`: passed, 136 tests after the sequential simulated AP-return fix.
- Live AP C-STORE reconciliation remains environment-specific and documented for manual execution.

## Code Review

### Round 1 (2026-07-13)

- Source: `openspec/changes/add-dcm4chee-production-e2e-verification/review/2026-07-13_codex-review.md`.
- Finding: P1 issue where separate Simulate AP PDF and Simulate AP DICOM actions created separate refresh generations, causing the earlier simulated result row to disappear from the patient/order DICOM result browser.
- Result: Required fix before completion.

### Round 2 (2026-07-13)

- Source: `openspec/changes/add-dcm4chee-production-e2e-verification/review/2026-07-13_codex-review-r2.md`.
- Finding: No blocking issues found.
- Result: Prior P1 was addressed by reusing the same simulated generation for sequential PDF/DICOM calls and adding regression coverage.
- Residual risk: Live AP C-STORE reconciliation remains manual/environment-specific; simulated AP return can supersede live result refresh visibility under the existing latest-generation display behavior.
