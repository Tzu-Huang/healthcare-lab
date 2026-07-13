## Why

The Medplum page exposes the required FHIR workflows, but its composition differs from the patient-centered OIE, GDT, and dcm4chee consoles: Patient rows cannot disclose their Orders and Results inline, the selected Patient panel carries too many concerns, and the resource preview feels detached from the common server workflow. A consistent console pattern will reduce navigation cost while preserving the existing Medplum live-read and local-sync behavior.

## What Changes

- Rename the Medplum workspace heading to `Patient-Centered Console` and align its Patient list, selected Patient, workflow, and raw preview hierarchy with the other server pages.
- Add independent Patient-row disclosure that renders FHIR Orders and Results inline without changing the currently selected Patient.
- Summarize `ServiceRequest` and `Task` records as Orders, and `DiagnosticReport`, `Observation`, and `DocumentReference` records as Results, with Preview and Retry actions where applicable.
- Separate the selected Patient summary from ServiceRequest/DiagnosticReport workflow controls and related-resource navigation.
- Retain the single full-width bottom JSON console, live Medplum DiagnosticReport fetch, sync-status filter, non-destructive retry, and responsive single-column fallback.
- Preserve all backend APIs, persistence, Medplum synchronization, and canonical live-read behavior.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Clarify the Medplum console's common patient-centered layout, independent Patient selection/disclosure, inline Order/Result rollups, workflow panel, and bottom JSON preview behavior.

## Impact

- Frontend structure in `frontend/templates/index.html`.
- Medplum Patient selection, disclosure, resource grouping, preview, and retry rendering in `frontend/static/app.js`.
- Medplum patient table, nested rollup, workflow, preview, and responsive rules in `frontend/static/styles.css`.
- Static frontend and behavior-contract tests in `tests/test_app.py`.
- No backend API, database, dependency, authentication, or Medplum resource changes.
