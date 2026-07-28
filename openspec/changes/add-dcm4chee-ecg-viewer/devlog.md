---
change: add-dcm4chee-ecg-viewer
date: 2026-07-28
---

## Context

ZAC-95 connects persisted, explicitly supported dcm4chee ECG instance results to the existing result-scoped metadata and SVG APIs through a dedicated Healthcare Lab viewer.

## Implementation

- Projected `capabilities.ecgGraph` only for complete instance identity with a supported ECG Waveform Storage SOP Class.
- Added a capability-gated `View ECG Graph` action while preserving artifact, generic viewer, and retrieve actions.
- Added `/viewer/ecg/<result-id>` with modular metadata/SVG loading, accessible status regions, display summary, controlled failures, and scoped responsive styling.
- Added mapper, frontend characterization, API/service, route, and end-to-end mocked retrieval coverage.

## Decisions

- ECG eligibility uses explicit SOP Class capability rather than patient/order association or modality inference.
- The browser uses only application-owned result-ID routes and never receives raw WADO-RS targets or credentials.
- Metadata and SVG loading have independent failure states so a graph failure cannot masquerade as successful rendering.

## Validation Plan

- Run mapper, ECG service/API, viewer route, frontend viewer/action, and dcm4chee API module tests.
- Run JavaScript syntax checks for the viewer API, viewer state module, and result action module.
- Run OpenSpec strict validation, Python compile checks, and committed-diff hygiene checks.
- Treat live AP/dcm4chee browser exercise as environment follow-up; automated WADO-RS integration remains mocked.

## Follow-ups

- Run the initial `/dev-review` quality gate.
- Exercise one live supported ECG result in the local dcm4chee/AP lab when that environment is available.

## Verification

### Round 1 (2026-07-28 13:21:40 +08:00)

- Tested head: `2745f748c689c266a6707709a47b02d2115cff1f`
- Status: `pass`
- Checks:
  - `.\.venv\Scripts\python.exe -m unittest tests.mappers.test_dicom tests.services.test_dcm4chee_ecg tests.api.test_dcm4chee_ecg tests.integration.test_dcm4chee_ecg_api tests.integration.test_ecg_viewer_route` — pass, 18 tests.
  - `node --check` for `frontend/static/js/api/ecg-viewer.js`, `frontend/static/js/views/ecg-viewer.js`, and `frontend/static/js/views/dcm4chee.js` — pass.
  - `.\.venv\Scripts\python.exe -m unittest tests.frontend.test_ecg_viewer tests.frontend.test_dcm4chee_view_module tests.frontend.test_dcm4chee_api_module` — pass, 13 tests.
  - `openspec validate add-dcm4chee-ecg-viewer --strict` — pass.
  - `.\.venv\Scripts\python.exe -m py_compile backend/api/home.py backend/mappers/dicom.py` — pass; generated caches are ignored.
  - `git diff --check HEAD^..HEAD` and pre/post-test worktree checks — pass; no tracked mutation.
  - Live AP/dcm4chee browser exercise — skip, optional environment follow-up and not required for this automated round.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-28 13:28:21 +08:00)

- Tested head: `ba8304a59f81d3c2c2e76177e53e690d145cde91`
- Status: `pass`
- Checks:
  - `node --experimental-vm-modules --test tests/frontend/ecg_viewer_behavior.mjs` — pass, 4 executable behavior tests covering action gating/URL/`noopener`, loading-to-success, controlled metadata failure, and independent SVG failure.
  - `.\.venv\Scripts\python.exe -m unittest tests.frontend.test_ecg_viewer_behavior tests.frontend.test_ecg_viewer tests.frontend.test_dcm4chee_view_module tests.frontend.test_dcm4chee_api_module tests.mappers.test_dicom tests.services.test_dcm4chee_ecg tests.api.test_dcm4chee_ecg tests.integration.test_dcm4chee_ecg_api tests.integration.test_ecg_viewer_route` — pass, 32 tests.
  - `openspec validate add-dcm4chee-ecg-viewer --strict` — pass.
  - JavaScript syntax checks for the behavior harness and three production modules — pass.
  - Python compile checks for `backend/api/home.py` and `backend/mappers/dicom.py` — pass; caches remain ignored.
  - `git diff --check 2745f748c689c266a6707709a47b02d2115cff1f..HEAD` and pre/post-test worktree checks — pass; no tracked mutation.
  - Live AP/dcm4chee browser exercise — skip, optional environment follow-up and not required for this automated round.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-28 13:21:40 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-95_add-dcm4chee-ecg-viewer_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `2745f748c689c266a6707709a47b02d2115cff1f`
- Transitions: `REV-001 open`
- Open blockers: `REV-001`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-95_add-dcm4chee-ecg-viewer_codex-review-r1.md"`

### Round 2 (2026-07-28 13:30:06 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-95_add-dcm4chee-ecg-viewer_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `ba8304a59f81d3c2c2e76177e53e690d145cde91`
- Transitions: `REV-001 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only the review and devlog workflow records, then run `/dev-done`
