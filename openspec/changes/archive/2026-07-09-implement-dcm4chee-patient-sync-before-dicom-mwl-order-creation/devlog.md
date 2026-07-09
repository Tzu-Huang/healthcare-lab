---
change: implement-dcm4chee-patient-sync-before-dicom-mwl-order-creation
date: 2026-07-09
---

## Context

Healthcare Lab DICOM MWL creation against dcm4chee can fail when the referenced Patient does not already exist in the archive. dcm4chee accepts Patient master updates through its HL7 ADT receiver, while STOW-RS is not appropriate for Patient master upsert. This change makes local DICOM Patient sync an explicit precondition before dcm4chee MWL creation.

## Implementation

- Added dcm4chee HL7 receiver profile settings and exposed Docker port `2575`.
- Added local dcm4chee Patient sync persistence with per-Patient mapping/status and append-only sync attempts.
- Added HL7 ADT Patient payload generation, MLLP send/ACK parsing, and DICOM Patient create-time sync.
- Added MWL Patient preflight sync before MWL REST creation, preserving local orders and recording Patient precondition failures without POSTing MWL.
- Surfaced dcm4chee Patient sync state and MWL Patient precondition diagnostics in API/UI responses.
- Documented the ADT sync flow, defaults, and STOW-RS non-goal.
- Fixed review finding `ed38faf` by treating `patient_sync_failed` as a non-retryable MWL precondition state and covering it with an assertion.

## Decisions

- Use HL7 ADT A04 for initial DICOM Patient creation and preflight Patient sync before MWL creation.
- Use the same Patient ID and issuer namespace for ADT Patient sync and MWL payloads.
- Keep MWL REST create/read-back/verify behavior, but gate create with Patient sync.
- Preserve local Patient/order records when dcm4chee sync fails so operators can retry after fixing connectivity or ADT rejection causes.
- Keep manual live dcm4chee Docker E2E outside automated verification for now; automated tests mock MLLP and DICOMweb calls.

## Validation Plan

- Validate OpenSpec change strictly.
- Run frontend JavaScript syntax check for `frontend/static/app.js`.
- Run Python syntax checks for touched backend modules.
- Run relevant Healthcare Lab Python test suite: `tests.test_lab_store` and `tests.test_app`.
- Manually run live dcm4chee Docker ADT/MWL E2E before production-like use if needed.

## Code Review

### Round 1 (2026-07-09)

- Review file: `openspec/changes/implement-dcm4chee-patient-sync-before-dicom-mwl-order-creation/review/2026-07-09_feature-zac-44-dcm4chee-patient-sync_codex-review.md`
- Verdict: changes requested.
- Finding: `patient_sync_failed` MWL Patient precondition failures were initially reported as retryable MWL sync failures.
- Resolution: fixed in `ed38faf` by adding `patient_sync_failed` to non-retryable MWL error types and asserting `mwl["retryable"]` is false in the precondition failure test.

## Follow-ups

- Run a live Docker dcm4chee ADT/MWL end-to-end check when the lab environment is available.
- Consider a dedicated Patient sync retry endpoint or UI action if operators need to recover Patient ADT failures without creating another MWL order.
