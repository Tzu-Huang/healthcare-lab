---
change: add-fhir-local-sync-foundation
date: 2026-07-08
---

## Context

ZAC-25 adds a local-first FHIR foundation for Healthcare Lab so Patient, Order, AP, and Result workflows can persist intended FHIR resources before Medplum is reachable. The change keeps the scope at reusable persistence, mapping, retry, and sync-status infrastructure rather than implementing the later workflow UIs.

## Implementation

- Added SQLite-backed local FHIR workflow records and sync attempts to `backend/lab_store.py`.
- Added deterministic identifier and mapping metadata for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance`.
- Added store methods for FHIR record create/list/get, dependency ordering, status transitions, Medplum id/reference preservation, and sync attempt history.
- Added FHIR APIs in `app.py` for mappings, records, record detail, sync attempts, and per-record Medplum sync.
- Implemented Medplum identifier search before create, create-on-miss, retry reuse of existing local Medplum ids, and PUT update for changed local resources that already have a Medplum id.
- Preserved sync failure details, including request method, URL, request payload, HTTP status, response payload, error text, and OperationOutcome where available.
- Added regression coverage for local persistence/status display, mapping coverage, failure capture, existing-resource reuse, create-on-miss, retry without duplicate create, validation failure handling, and changed-resource PUT update.

## Decisions

- Keep the sync API local-first: failures return a persisted record with `success: false` and `Sync failed` instead of dropping local state.
- Use deterministic FHIR identifiers from resource type, local source type, and local source id for idempotent Medplum search-before-create behavior.
- Preserve an existing Medplum id/reference across local payload changes so retries can update rather than create a duplicate.
- Treat unchanged already-synced retries as successful when the local ledger already has a Medplum id, even if identifier search returns empty.
- Treat changed already-synced records as update candidates and issue `PUT /<resourceType>/<id>` before marking them `Synced`.
- Keep live Medplum/OIE checks outside automated local verification; current tests use mocked Medplum responses.

## Validation Plan

- Run `python -m unittest discover -s tests`.
- Run `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`.
- Run `node --check frontend\static\app.js`.
- Run `openspec validate --changes add-fhir-local-sync-foundation`.
- Record live Medplum/OIE/manual checks as skipped unless a configured environment is available.

## Verification

### Round 1 (2026-07-08)

- `python -m unittest discover -s tests`: passed, 86 tests.
- `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`: passed.
- `node --check frontend\static\app.js`: passed.
- `openspec validate --changes add-fhir-local-sync-foundation`: passed.
- Live Medplum/OIE/manual environment checks: skipped; local verification uses mocked Medplum responses.

## Code Review

### Round 1 (2026-07-08)

- Review source: `openspec/changes/add-fhir-local-sync-foundation/review/2026-07-08_codex-review-round5.md`.
- Verdict: no findings.
- Reviewed FHIR sync search/create/retry/update/failure paths, local ledger status transitions, duplicate create guard, changed payload `PUT` update behavior, failure attempt details, and regression tests.
- Residual risk: live Medplum/OIE/manual environment checks remain unrun locally.

## Follow-ups

- Run live Medplum/OIE smoke or manual checks in an environment with valid Medplum OAuth configuration.
- Later workflow tickets should build Patient, Order, AP, and Result-specific FHIR resource creation on top of this ledger and sync contract.
