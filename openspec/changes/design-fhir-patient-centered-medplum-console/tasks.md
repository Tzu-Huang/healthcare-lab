## 1. Frontend Layout

- [ ] 1.1 Replace the Medplum inventory-first page with a GDT-like Patient-centered console layout.
- [ ] 1.2 Add a left-side FHIR Patient list showing identity, sync status, ServiceRequest count, and DiagnosticReport count.
- [ ] 1.3 Add a selected Patient workspace with `ServiceRequest` and `DiagnosticReport` dropdown controls.
- [ ] 1.4 Add lightweight selected workflow context for related Task, Observation, and DocumentReference rows without separate rich viewers.
- [ ] 1.5 Move raw resource preview into a single bottom JSON console with copy support.

## 2. Data And Behavior

- [ ] 2.1 Group Medplum inventory records by selected Patient using direct FHIR references and existing ledger metadata.
- [ ] 2.2 Build clear dropdown labels for ServiceRequest and DiagnosticReport options.
- [ ] 2.3 Update JSON console selection when the user selects a Patient, ServiceRequest, DiagnosticReport, Task, Observation, or DocumentReference.
- [ ] 2.4 Preserve live Medplum JSON preview for synced resources and local submitted fallback for failed live fetches.
- [ ] 2.5 Preserve retry actions for Pending sync and Sync failed resources without adding destructive actions.

## 3. Verification

- [ ] 3.1 Add or update template/script tests for Patient-centered Medplum console structure and controls.
- [ ] 3.2 Add or update API/data tests if grouping metadata changes.
- [ ] 3.3 Run relevant unit tests.
