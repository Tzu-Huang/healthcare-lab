---
change: add-medplum-resource-inventory
date: 2026-07-08
---

## Context

ZAC-27 adds the first Healthcare Lab Medplum/FHIR inventory page. Before this change, Healthcare Lab had a disabled Medplum sidebar entry and a reusable local FHIR workflow ledger, but no Medplum-centered view for inspecting synced resources, viewing raw FHIR JSON, or retrying unsynced local workflow records.

The work builds on the existing local-first FHIR sync foundation and Patient-page Medplum-backed FHIR Patient create flow.

## Implementation

- Added `/api/fhir/inventory` to expose supported FHIR ledger records with resource type, sync status, Medplum reference, retryability, and direct Patient reference metadata.
- Added `/api/fhir/records/<id>/preview` to return Medplum live JSON for synced resources and local submitted JSON for pending, failed, or live-fetch-fallback cases.
- Enabled the Medplum sidebar entry and added a Medplum inventory page.
- Added resource-type, sync-status, and Patient-centered filtering for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference`.
- Added raw JSON preview, preview source labeling, live-fetch fallback messaging, and copy action.
- Added retry from the Medplum page for `Pending sync` and `Sync failed` records through the existing idempotent FHIR sync endpoint.
- Added backend and frontend/API regression coverage for inventory metadata, Patient filtering, live preview, fallback preview, and UI exposure.

## Decisions

- Synced resources prefer Medplum live JSON as the canonical preview source.
- If live Medplum fetch fails, the page falls back to local submitted JSON and labels it as fallback data.
- Pending and failed records show local submitted JSON because the resource may not exist in Medplum yet.
- Patient-centered filtering is intentionally scoped to direct Patient references through `subject`, `patient`, and `for`.
- Retry is available for `Pending sync` and `Sync failed`, but no delete, arbitrary edit, or destructive Medplum action is exposed.

## Validation Plan

- Validate the OpenSpec change.
- Check frontend JavaScript syntax.
- Run focused Medplum inventory API/UI regression tests.
- Run the Healthcare Lab Python test suite.
- Treat live Medplum browser/manual smoke as an environment-specific follow-up.

## Follow-ups

- Run a live Medplum browser smoke in the configured lab environment.
- Consider adding sync attempt history to the Medplum page if operators need inline request/response diagnostics.
- Expand Patient-centered filtering beyond direct references only if later workflows require indirect relationship traversal.

## Code Review

### Round 1 (2026-07-08)

- Review source: `openspec/changes/add-medplum-resource-inventory/review/2026-07-08_codex-review.md`.
- Verdict: no issues found.
- Residual risk: live Medplum browser/manual smoke was not run locally; behavior is covered with mocked Medplum API responses.
