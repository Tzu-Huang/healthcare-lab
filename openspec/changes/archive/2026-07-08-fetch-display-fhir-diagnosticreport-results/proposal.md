## Why

Healthcare Lab already has a Patient-centered Medplum console and local FHIR workflow ledger coverage for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, and `Binary`.

The current Medplum read path is still centered on local inventory records and per-record previews. Users need to fetch existing live `DiagnosticReport` resources from Medplum by selected Patient and selected ServiceRequest, then inspect result relationships in a GDT-style console layout.

ZAC-43 adds read/display support only. It must not add a `DiagnosticReport` submit/create workflow.

## What Changes

- Add a backend API that searches live Medplum `DiagnosticReport` resources for a selected `Patient/<id>`.
- Support selected `ServiceRequest/<id>` narrowing with `DiagnosticReport?based-on=...` when available, falling back to Patient search plus server-side `basedOn[]` filtering when needed.
- Return raw FHIR Bundle JSON and parsed DiagnosticReport summary metadata for UI rendering.
- Surface relationships from `DiagnosticReport.subject`, `basedOn`, `result`, `media`, `presentedForm`, and related `Observation`, `DocumentReference`, and `Binary` references.
- Rework the Medplum DiagnosticReport experience toward the existing GDT console pattern: Patient list, expandable patient result rollup, selected Patient summary, related artifact/resource list, and bottom raw JSON panel.
- Auto-fetch DiagnosticReports when a Patient or ServiceRequest is selected.
- Treat Medplum as the canonical read source and keep local ledger records only as workflow metadata or explicit local fallback.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Add live Medplum DiagnosticReport read/display support in the Patient-centered Medplum console.

## Impact

- Affected code: `app.py`, `frontend/templates/index.html`, `frontend/static/app.js`, `frontend/static/styles.css`, and tests under `tests/`.
- Affected systems: Medplum FHIR R4 API, Medplum console UI, backend smoke/check behavior, local FHIR workflow ledger metadata joins.
- No new runtime dependency is expected.
- Empty DiagnosticReport results should display as "no reports found" and must not be treated as Medplum outage.
- This change does not create, submit, mirror, or import live DiagnosticReport resources into the local ledger.

