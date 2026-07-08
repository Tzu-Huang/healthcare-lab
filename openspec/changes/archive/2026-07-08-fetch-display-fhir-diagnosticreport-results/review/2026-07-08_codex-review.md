## Findings

### P2 - Stale live DiagnosticReports can remain selectable after changing Patient or ServiceRequest

[frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:1403) returns early whenever `medplumDiagnosticReports.loading` is true, so a Patient or ServiceRequest change made while a previous live report request is still in flight does not start a new request or invalidate the old `requestId`. When that older request resolves, [frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:1427) still accepts it because the request id is unchanged, and [frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:1175) renders `medplumDiagnosticReports.reports` into the dropdown without checking that the reports match the currently selected Patient/ServiceRequest key.

This can temporarily show and preview DiagnosticReports for the previous Patient or previous ServiceRequest under the new selection, which is risky for a patient-centered clinical console. Increment the request id or clear/cancel live report state whenever selection changes, and only render live reports when `medplumDiagnosticReports.key` matches `currentMedplumDiagnosticReportKey()`.

### P3 - ServiceRequest fetch can fail before trying the preferred based-on search

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:566) always performs the Patient `subject` search before entering the ServiceRequest branch at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:577). If the local Medplum target supports `DiagnosticReport?based-on=ServiceRequest/<id>` but rejects or does not support `DiagnosticReport?subject=Patient/<id>`, the selected-ServiceRequest fetch fails before the preferred `based-on` search is attempted.

The proposal says ServiceRequest narrowing should prefer `based-on`, with Patient search used as the fallback when `based-on` is unavailable. Reorder the selected-ServiceRequest path so `based-on` is attempted first, then optionally fetch Patient reports to append patient-level results or fallback-filter when `based-on` fails.

## Residual Risk / Test Gaps

- Automated tests cover backend search URLs, empty Bundle handling, upstream errors, malformed Bundle handling, relationship parsing, Binary preview, smoke behavior, and frontend/template contract strings.
- No browser-level or jsdom test exercises rapid Patient/ServiceRequest switching while a live DiagnosticReport fetch is in flight; that is the gap behind the P2 finding.
- Live Medplum/manual browser verification was not run in this local review cycle.

## Verification Reviewed

- `openspec validate fetch-display-fhir-diagnosticreport-results --strict`
- `node --check frontend\static\app.js`
- `python -m unittest discover tests` (102 tests)

