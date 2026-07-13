---
change: unify-medplum-patient-console
date: 2026-07-13
---

## Context

The Medplum page exposed the required FHIR workflows but did not follow the Patient-centered selection, disclosure, workflow, and payload-preview rhythm used by the OIE, GDT, and dcm4chee pages.

## Implementation

- Reorganized the Medplum template into a dominant Patient list, selected Patient summary, workflow panel, and full-width JSON console.
- Added independent Patient selection and disclosure state.
- Added inline FHIR Order and Result rollups with Preview and non-destructive Retry actions.
- Preserved ServiceRequest and DiagnosticReport selection, live report reads, related resources, source labels, and local fallback behavior.
- Added nested-table containment and responsive desktop-to-single-column layout rules.
- Added frontend contract coverage for the new DOM, state, rendering, and style hooks.

## Decisions

- Keep live-only DiagnosticReports in the workflow panel instead of mirroring them into the local-ledger inline Results table.
- Keep selection and disclosure as separate state so expanding one Patient does not change the active workflow Patient.
- Reuse existing preview, retry, reference-matching, and live-fetch functions rather than introduce a second Medplum data path.

## Validation Plan

- Run JavaScript syntax validation.
- Run the complete Python test suite.
- Run strict OpenSpec validation.
- Exercise desktop and narrow-screen layout, disclosure independence, and JSON Preview through browser smoke testing.

## Follow-ups

- Consider retaining the Playwright browser smoke as a permanent regression test if browser tooling becomes a project dependency.
- Exercise the console against an authenticated live Medplum environment during deployment-level verification.

## Verification

### Round 1 (2026-07-13)

- `node --check frontend/static/app.js`: pass.
- `python -m unittest discover -s tests -p "test*.py"`: pass, 154 tests.
- `openspec validate unify-medplum-patient-console --strict`: pass.
- Browser smoke: pass for desktop two-column layout, 700px single-column reflow, selection/disclosure independence, inline rollups, JSON Preview, and console errors.

## Code Review

### Round 1 (2026-07-13)

- Verdict: Pass; no blocking findings.
- Must-fix items: None.
- Residual risks: live-only DiagnosticReports remain in the workflow panel, browser smoke is not a permanent test, and an authenticated live Medplum environment was not exercised.
- Full review: `openspec/changes/unify-medplum-patient-console/review/2026-07-13_codex-review.md`.
