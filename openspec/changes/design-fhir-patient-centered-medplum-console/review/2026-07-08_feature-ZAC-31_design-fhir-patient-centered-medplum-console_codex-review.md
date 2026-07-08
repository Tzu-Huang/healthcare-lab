# Codex Review: feature/ZAC-31_design-fhir-patient-centered-medplum-console

## Findings

### P2 - Recompute selected Patient before rendering filtered workspace

[frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:1177)

`renderMedplumConsole()` captures `const patient = selectedMedplumPatient()` before `renderMedplumPatientList()`. But `renderMedplumPatientList()` calls `filteredMedplumPatients()`, which can mutate `selectedMedplumPatientId` when the current Patient is excluded by the sync-status filter or when no Patients match. The rest of `renderMedplumConsole()` still uses the stale `patient`, so after changing the status filter the left table can select or clear one Patient while the selected Patient summary, ServiceRequest dropdown, DiagnosticReport dropdown, related rows, and JSON fallback still render the previously selected Patient. This makes the filter visually inconsistent and can show resources for a Patient that is no longer in the filtered list.

Fix by normalizing `selectedMedplumPatientId` before reading `patient`, or by recomputing `patient = selectedMedplumPatient()` after `renderMedplumPatientList()` updates the selection.

### P2 - Avoid showing all orders/reports when no Patient is selected

[frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:1180)

`renderMedplumConsole()` calls `medplumRecordsForPatient(patient, "ServiceRequest")` and `medplumRecordsForPatient(patient, "DiagnosticReport")` even when `patient` is `null`. Because `medplumRecordMatchesPatient(item, patient)` returns `true` for a null Patient, the selected Patient workspace can show all ServiceRequests and DiagnosticReports while the title says "No patient selected." This violates the Patient-centered layout contract and is reachable when inventory has non-Patient records but no Patient records, or when the sync-status filter leaves no visible Patients.

Fix by returning empty resource lists when there is no selected Patient, or by making the call sites guard on `patient` before populating dropdowns and related rows.

## Residual Risk

The automated tests cover template presence and inventory metadata, but they do not exercise the Medplum console state transitions in a browser-like DOM. A small JS/DOM test or Playwright check for status-filter changes and no-Patient inventory would catch both issues above.
