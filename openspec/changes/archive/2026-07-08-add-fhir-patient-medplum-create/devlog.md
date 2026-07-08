---
change: add-fhir-patient-medplum-create
date: 2026-07-08
---

## Context

ZAC-26 connects the Patient page's FHIR mode to the existing Healthcare Lab FHIR ledger and Medplum sync foundation. Before this change, FHIR mode could preview a Patient resource and create a local Patient record, but it did not create a paired retryable FHIR workflow record or store Medplum sync identity/status on the Patient page.

## Implementation

- Added scoped FHIR Patient fields for active status, email, structured address, and optional managing organization context.
- Extended local Patient persistence and FHIR Patient resource generation to include the new fields.
- Added paired FHIR workflow ledger creation for FHIR-mode local Patient records.
- Updated `/api/patients` so FHIR Patient create stores local Patient first, creates/updates the ledger, and immediately attempts Medplum sync when a base URL is configured.
- Added `/api/patients/<id>/fhir-sync` for row-level retry of the paired FHIR ledger record.
- Enriched Patient list/detail responses with FHIR ledger metadata: record id, sync status, Medplum reference, last sync metadata, and error details.
- Updated the Patient UI to preview the new fields, show sync status/reference/error in Local Patients, and expose Retry for unsynced FHIR rows.
- Added store and API tests for field mapping, paired ledger creation, successful sync, failure preservation, and retry/idempotency.

## Decisions

- FHIR Patient create attempts Medplum sync in the same request after local persistence, matching the agreed UX for this ticket.
- Sync failure does not remove or hide the local Patient; the row remains visible with `Sync failed` and retry state.
- Patient table rows remain anchored on local Patient records and join FHIR ledger metadata instead of adding one-off Medplum columns for each sync field.
- The new FHIR Patient fields are intentionally scoped to common Patient properties and do not attempt full profile editing.

## Validation Plan

- Validate OpenSpec change syntax.
- Compile changed Python files.
- Check frontend JavaScript syntax.
- Run the Healthcare Lab unittest discovery suite.
- Treat live Medplum smoke as an environment-specific manual follow-up outside local automated verification.

## Follow-ups

- Run a live Medplum smoke test in the configured Healthcare Lab environment.
- Consider browser-level UI verification for the expanded Patient table and retry action.
- Future FHIR inventory tickets should add live Medplum Patient reads and join local ledger metadata for canonical resource display.

## Code Review

### Round 1 (2026-07-08)

- Review source: `openspec/changes/add-fhir-patient-medplum-create/review/2026-07-08_codex-review.md`.
- Verdict: no issues found.
- Residual risk: live Medplum smoke and browser-level Patient UI interaction were not run locally.
