---
change: retrieve-ecg-instances-through-wado-rs
date: 2026-07-28
---

## Context

ZAC-94 adds result-ID-scoped retrieval of reconciled DICOM ECG instances
through the configured dcm4chee WADO-RS profile and exposes safe metadata and
SVG APIs.

## Implementation

- Added bounded authenticated WADO-RS retrieval for bare and single-instance
  multipart DICOM responses.
- Added an application service that resolves persisted results, decodes and
  normalizes ECG waveforms, and renders SVG without exposing arbitrary fetch
  targets.
- Added disclosure-safe result APIs and controlled 404, 409, 415, 422, and 502
  errors.
- Added focused transport, service, API, integration, security, and regression
  coverage.

## Decisions

- Public callers select only a persisted integer result ID.
- WADO targets are reconstructed from the authoritative profile and stored
  study, series, and instance UIDs.
- DICOM responses are size-bounded before parsing and raw DICOM metadata does
  not cross the API boundary.

## Validation Plan

- Run focused ECG transport, service, parser, renderer, API, repository, and
  dcm4chee regression suites.
- Compile affected Python modules and enforce architecture contracts.
- Validate the OpenSpec change strictly and run the complete automated suite.

## Follow-ups

- Initial code review is required before closure.

## Verification

### Round 1 (2026-07-28 11:28:59 +08:00)

- Tested head: `917c6b4469ace2ae9bb6ca6ef69731ab4e8654fa`
- Status: `pass`
- Checks:
  - `.\.venv\Scripts\python.exe -m unittest tests.clients.test_dcm4chee_wado tests.services.test_dcm4chee_ecg tests.domain.test_ecg_waveform tests.presentation.test_ecg_renderer` — pass, 38 tests.
  - `.\.venv\Scripts\python.exe -m unittest tests.api.test_dcm4chee_ecg tests.integration.test_dcm4chee_ecg_api tests.integration.test_dcm4chee_api tests.api.test_integration_settings tests.repositories.test_patients_orders` — pass, 60 tests.
  - `.\.venv\Scripts\python.exe -m py_compile ...` for five affected backend modules — pass.
  - Architecture composition-root checks — pass, 2 tests.
  - `openspec validate retrieve-ecg-instances-through-wado-rs --strict` and `git diff --check` — pass.
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests` — pass, 916 tests with 1 optional local-fixture compatibility skip.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-28 11:50:17 +08:00)

- Tested head: `21dc0c78a6a3382f01fa303bef25935510a89b7d`
- Status: `pass`
- Checks:
  - `.\.venv\Scripts\python.exe -m unittest tests.clients.test_dcm4chee_wado tests.services.test_dcm4chee_ecg tests.domain.test_ecg_waveform tests.presentation.test_ecg_renderer tests.domain.test_dcm4chee_settings tests.test_config` — pass, 55 tests.
  - `.\.venv\Scripts\python.exe -m unittest tests.api.test_dcm4chee_ecg tests.integration.test_dcm4chee_ecg_api tests.integration.test_dcm4chee_api tests.api.test_integration_settings tests.repositories.test_patients_orders tests.repositories.test_integration_settings` — pass, 76 tests.
  - `.\.venv\Scripts\python.exe -m py_compile` for all seven changed backend Python modules — pass.
  - Composition-root architecture checks — pass, 2 tests.
  - `openspec validate retrieve-ecg-instances-through-wado-rs --strict` and `git diff --check` — pass.
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests` — pass, 918 tests with 1 optional local-fixture compatibility skip.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 3 (2026-07-28 12:05:28 +08:00)

- Tested head: `174c83a613197289024ddd662c602e8ac70601e4`
- Status: `pass`
- Checks:
  - `.\.venv\Scripts\python.exe -m unittest tests.repositories.test_integration_settings tests.domain.test_dcm4chee_settings tests.api.test_integration_settings tests.clients.test_dcm4chee_wado` — pass, 57 tests including persisted dcm4chee v1-to-v2 migration.
  - `.\.venv\Scripts\python.exe -m unittest tests.api.test_dcm4chee_ecg tests.integration.test_dcm4chee_ecg_api tests.integration.test_dcm4chee_api tests.repositories.test_patients_orders` — pass, 40 tests.
  - `.\.venv\Scripts\python.exe -m py_compile` for all nine changed backend Python modules — pass.
  - Composition-root architecture checks — pass, 2 tests.
  - `openspec validate retrieve-ecg-instances-through-wado-rs --strict` and `git diff --check` — pass.
  - `.\.venv\Scripts\python.exe -m unittest discover -s tests` — pass, 919 tests with 1 optional local-fixture compatibility skip.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-28 11:35:00 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-94_retrieve-ecg-instances-through-wado-rs_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `917c6b4469ace2ae9bb6ca6ef69731ab4e8654fa`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-94_retrieve-ecg-instances-through-wado-rs_codex-review-r1.md"`

### Round 2 (2026-07-28 11:52:24 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-94_retrieve-ecg-instances-through-wado-rs_codex-review-r2.md`
- Mode: `closure`
- Verdict: `changes-requested`
- Reviewed head: `21dc0c78a6a3382f01fa303bef25935510a89b7d`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 open`
- Open blockers: `REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-94_retrieve-ecg-instances-through-wado-rs_codex-review-r2.md"`

### Round 3 (2026-07-28 12:06:50 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-94_retrieve-ecg-instances-through-wado-rs_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `174c83a613197289024ddd662c602e8ac70601e4`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: `/dev-done`
