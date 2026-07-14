---
change: remove-medplum-task-workflow
date: 2026-07-14
---

## Context

Healthcare Lab previously created a paired FHIR `ServiceRequest` and generated `Task` for every Medplum-backed ECG order. The application does not manage a distinct Task assignment or execution lifecycle, so this change makes ServiceRequest the sole order resource while retaining existing Task data as non-destructive history.

## Implementation

- Removed Task from supported FHIR mappings, identifiers, dependency ordering, Medplum inventory/read allowlists, summaries, and Patient reference handling.
- Removed the ECG Task builder, order-to-Task ledger creation, and Task synchronization from FHIR Order creation.
- Removed `fhir.task` from local order responses and made frontend acceptance depend only on a synced `ServiceRequest/<id>` reference.
- Removed Task from Medplum Patient order rollups, related-resource navigation, preview copy, and frontend contract text.
- Preserved historical Task rows for audit materialization while excluding or rejecting them in active list, inventory, record read, preview, retry, sync, and new-record creation paths.
- Updated store/API/frontend tests, README guidance, workflow documentation, SVG sources, and rendered PNG diagrams.

## Decisions

- ServiceRequest is the only FHIR order resource created and synchronized by Healthcare Lab.
- Existing local Task rows and remote Medplum Task resources are not deleted or migrated.
- Removing `fhir.task` and Task from supported resource lists is an intentional breaking API change.
- Archived OpenSpec changes remain unchanged as historical implementation records.
- Patient, DiagnosticReport, Observation, DocumentReference, Binary, and Provenance workflows remain supported; Task was removed from Provenance dependency metadata.

## Validation Plan

- Run the full Python test suite with `python -m unittest discover -s tests`.
- Run `node --check frontend/static/app.js` and compile `app.py` plus `backend/lab_store.py`.
- Run `git diff --check` and strict OpenSpec validation.
- Scan active frontend, README, Markdown documentation, and SVG files for residual Task workflow references.
- Confirm remaining backend/test Task references are limited to historical-data rejection and negative coverage.

Completed result: 155 tests passed; JavaScript syntax, Python compile, diff check, Task-reference classification, and strict OpenSpec validation passed.

## Follow-ups

- Run a live Medplum smoke test when an authorized environment is available.
- Notify external API consumers that `fhir.task` and Task resource support were removed.
- Scope any future deletion of historical local or remote Task data as a separate, explicitly authorized retention migration.

## Code Review

### Round 1 (2026-07-14 10:48 +08:00)

- Reviewer: Codex in-session review.
- Verdict: No findings; ready for `/dev-done` from a code-review perspective.
- Must-fix items: None.
- Suggestions: None.
- Residual risks: Live Medplum smoke not run; breaking `fhir.task` removal requires consumer awareness; historical Task cleanup remains separately scoped.
- Source: `openspec/changes/remove-medplum-task-workflow/review/2026-07-14_codex-review.md`.
