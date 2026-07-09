---
change: add-dcm4chee-order-pacs-status-ui
date: 2026-07-09
---

## Context

ZAC-41 adds a frontend-focused OpenSpec proposal for making dcm4chee MWL/order and PACS result state easier to inspect from Healthcare Lab. Exploration found that the backend already has most required dcm4chee capabilities: MWL sync, retry, attempt history, MWL verification, manual AP C-STORE result refresh, result reconciliation, and viewer/retrieve link metadata.

The user preference is to keep Healthcare Lab as the primary visual system while borrowing dcm4chee-arc-like dropdown/table interaction for PACS Study, Series, and Instance browsing.

## Implementation

- Created OpenSpec proposal artifacts for `add-dcm4chee-order-pacs-status-ui`.
- Added spec requirements for selected DICOM order status summaries, PACS-style patient result hierarchy, unresolved diagnostics, and viewer/retrieve actions.
- Added task plan for DICOM order detail, PACS-style result browser, refresh actions, and verification coverage.
- Wrote Linear mapping for ZAC-41.
- Added Codex review artifacts for proposal review and post-fix review.
- During verification, fixed a dcm4chee MWL regression by restoring DICOMweb Patient preflight for non-DICOM local patients before MWL read-back/create.

## Decisions

- Treat this change as frontend presentation/completion work rather than a new backend foundation.
- Keep manual result refresh in scope and leave polling, callbacks, websocket updates, and local DICOM object viewing out of scope.
- Use Healthcare Lab styling for colors, panels, buttons, and status pills.
- Use dcm4chee-style metadata vocabulary and Study -> Series -> Instance hierarchy inside the DICOM result browser.
- Keep DICOM patient HL7 ADT sync and non-DICOM local patient DICOMweb preflight as distinct patient precondition paths.

## Validation Plan

- Validate the OpenSpec change with `openspec validate add-dcm4chee-order-pacs-status-ui --strict`.
- Run Python syntax checks for touched backend files.
- Run the full Python unittest discovery suite.
- Add or update frontend static tests when the ZAC-41 UI implementation lands.
- Add grouping-helper tests if Study/Series/Instance hierarchy is implemented as a pure helper.

## Code Review

### Round 1 (2026-07-09)

- Review source: `openspec/changes/add-dcm4chee-order-pacs-status-ui/review/2026-07-09_codex-review-r2.md`
- Verdict: no code-review findings in the post-fix branch diff.
- Notes: the scoped `app.py` fix restores DICOMweb Patient preflight for non-DICOM local patients before dcm4chee MWL read-back/create.
- Verification context: OpenSpec validation passed, Python compile passed, and `python -m unittest discover -s tests` passed 141 tests.
- Residual risk: ZAC-41 frontend implementation tasks remain pending by design.

### Round 2 (2026-07-09)

- Review source: `openspec/changes/add-dcm4chee-order-pacs-status-ui/review/2026-07-09_codex-review-r3.md`
- Verdict: no blocking code-review findings in the implemented frontend diff.
- Notes: selected DICOM order detail, PACS-style Study/Series/Instance browsing, refresh actions, viewer links, and retrieve-copy actions are implemented within the existing Healthcare Lab frontend.
- Verification context: JS syntax check passed, `python -m unittest tests.test_app` passed 109 tests, and OpenSpec strict validation passed.
- Residual risk: static frontend tests do not execute browser DOM expansion behavior or a live dcm4chee/AP refresh workflow.

## Follow-ups

- Implement the frontend DICOM order status detail.
- Implement the patient DICOM result browser grouped by matched order and unresolved diagnostics.
- Add result refresh action close to the patient/order DICOM result browser.
- Add frontend coverage for status labels, result browser hooks, and any grouping helper.
