---
change: fetch-display-fhir-diagnosticreport-results
date: 2026-07-08
---

## Context

ZAC-43 adds read/display support for live Medplum `DiagnosticReport` resources in Healthcare Lab. The existing Medplum console could show local FHIR workflow inventory and per-record live previews, but it did not search live DiagnosticReports that existed only in Medplum.

This change keeps Medplum as the canonical read source. It does not add a DiagnosticReport submit/create/import/mirroring workflow.

## Implementation

- Added a read-only backend DiagnosticReport fetch path for selected FHIR Patients.
- Added ServiceRequest narrowing through `DiagnosticReport?based-on=ServiceRequest/<id>`.
- Added fallback behavior for unsupported `based-on` search using Patient search plus server-side `basedOn[]` filtering.
- Added parsed DiagnosticReport summaries and relationship extraction for `subject`, `basedOn`, `result`, `media`, `presentedForm`, and related `Observation`, `DocumentReference`, and `Binary` references.
- Added a generic read-only live FHIR resource preview route for related resource lazy preview.
- Updated Medplum smoke/check behavior with an optional DiagnosticReport fetch step that treats empty Bundles as a healthy no-results state.
- Reworked the Medplum console DiagnosticReport area toward the GDT patient-rollup pattern with live result grouping, patient-level labels, raw JSON preview, and lazy related-reference preview.
- Added state invalidation so live DiagnosticReport results from an in-flight request cannot remain selectable after Patient or ServiceRequest changes.

## Decisions

- Patient selection auto-fetches live DiagnosticReports.
- ServiceRequest selection auto-narrows reports and the backend now tries `based-on` first for selected order context.
- Patient-level reports remain visible and clearly labeled instead of being hidden by order selection.
- Related `Observation`, `DocumentReference`, and `Binary` resources are previewed lazily.
- Local FHIR ledger rows are used only for workflow metadata or explicit local fallback, not as a full live DiagnosticReport mirror.

## Validation Plan

- Validate OpenSpec with `openspec validate fetch-display-fhir-diagnosticreport-results --strict`.
- Check frontend syntax with `node --check frontend\static\app.js`.
- Run automated tests with `python -m unittest discover tests`.
- Keep live Medplum/manual browser verification as an environment-specific follow-up.

## Follow-ups

- Run a live Medplum/manual browser check against the target environment to confirm actual `DiagnosticReport.subject` and `DiagnosticReport.based-on` search behavior.
- Consider browser-level or jsdom coverage for rapid Patient/ServiceRequest switching if the Medplum console gains more async live-read surfaces.

## Code Review

### Round 1 (2026-07-08)

- Source: `review/2026-07-08_codex-review.md`
- Findings: P2 stale live DiagnosticReports could remain selectable during in-flight selection changes; P3 selected-ServiceRequest fetch could fail on Patient subject search before trying preferred `based-on`.
- Resolution: Fixed with `fix(ZAC-43): prefer based-on DiagnosticReport search` and `fix(ZAC-43): invalidate stale DiagnosticReport selections`.

### Round 2 (2026-07-08)

- Source: `review/2026-07-08_codex-review-r2.md`
- Verdict: no open findings.
- Prior P2/P3 findings were rechecked and marked resolved.
