---
change: reconcile-dcm4chee-c-store-results
date: 2026-07-09
---

## Context

ZAC-40 closes the loop after Healthcare Lab creates dcm4chee MWL orders. The AP is expected to C-STORE DICOM results into dcm4chee-arc while preserving deterministic identifiers: Study Instance UID when available, Accession Number, Patient ID/Issuer, Requested Procedure ID, and Scheduled Procedure Step ID.

The selected first-version workflow is explicit operator refresh. Background polling and callbacks stay out of scope so the UI can show current archive state and diagnostics without adding scheduler behavior.

## Implementation

- Added `local_dcm4chee_result_records` persistence for reconciled result rows and diagnostic refresh states, including study/series/SOP UIDs, modality, timestamps, source profile, QIDO query metadata, viewer/retrieve links, reconciliation status, and raw DICOM JSON.
- Added patient-level result refresh via `POST /api/patients/<id>/dcm4chee-results-refresh`.
- Implemented QIDO study refresh using the strongest available MWL mapping identifiers, with follow-up series and instance metadata queries for discovered studies.
- Implemented reconciliation precedence by Study Instance UID, Accession Number plus Patient ID/Issuer, Requested Procedure ID plus SPS ID, and explicit diagnostic states for no-result, ambiguous, duplicate, wrong-patient, missing-accession, unlinked, and query-failed cases.
- Added `refresh_generation` so patient DICOM result views show the latest refresh state and do not keep stale diagnostic rows visible after a later successful refresh.
- Derived archive QIDO/WADO/STOW defaults from configured dcm4chee DICOMweb host while replacing the AE segment with the archive called AE title.
- Surfaced DICOM results under the patient summary as an expandable `DICOM Results` section with refresh action, status, identifiers, timestamps, and viewer/retrieve actions.
- Updated README and `.env.example` with manual refresh workflow, archive DICOMweb configuration, and AP metadata expectations.

## Decisions

- Manual refresh is the first supported result-ingest mechanism; polling and AP callbacks are deferred.
- Patient-level display is the primary operator surface because the user wanted results shown under the patient in a dropdown-style section.
- Matching favors deterministic MWL identifiers. Weak patient/modality/time fallback is treated conservatively to avoid silently attaching AP results to the wrong local order.
- Diagnostic rows are persisted for audit/debugging, but patient display filters to the latest refresh generation so the UI reflects current archive state.

## Validation Plan

- Run `python -m unittest tests.test_app tests.test_lab_store`.
- Run `node --check frontend\static\app.js`.
- Run `openspec validate reconcile-dcm4chee-c-store-results --strict`.
- Manually verify against a live dcm4chee/AP flow before closing: create MWL order, have AP C-STORE a result, click patient refresh, confirm matched result and viewer/retrieve links.

## Code Review

### Round 1 (2026-07-09)

Codex review found two P2 issues: stale refresh diagnostics stayed visible after later successful refresh, and archive QIDO/WADO/STOW defaults ignored the configured dcm4chee host. Both were fixed with focused commits and regression tests.

### Round 2 (2026-07-09)

Codex post-fix review found no blocking findings. Residual risk remains live AP-to-dcm4chee acceptance coverage because automated tests mock QIDO responses.

## Follow-ups

- Add live environment acceptance coverage for real dcm4chee QIDO behavior and viewer URL behavior.
- Revisit background polling or callback ingestion only after manual refresh behavior is accepted.
- Coordinate with the AP engineer to confirm returned DICOM preserves the identifiers listed in the proposal.
