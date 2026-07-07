## 1. Persistence

- [x] 1.1 Add SQLite tables for local FHIR workflow records and sync attempts.
- [x] 1.2 Add additive migration helpers for new FHIR sync columns and indexes.
- [x] 1.3 Implement store methods to create, list, fetch, and update local FHIR workflow records.
- [x] 1.4 Implement store methods to record sync attempts with request payload, response body, HTTP status, error text, and OperationOutcome JSON.

## 2. Mapping and Idempotency

- [x] 2.1 Define deterministic identifier policy for each supported FHIR resource type.
- [x] 2.2 Add mapping helpers for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance` local record metadata.
- [x] 2.3 Ensure mapped resources include stable identifiers suitable for Medplum search-before-create retry behavior.
- [x] 2.4 Define workflow dependency ordering for Patient, Order, Result, artifact, and Provenance resources.

## 3. Sync Helper/API

- [ ] 3.1 Implement Medplum search-by-identifier before create/update.
- [ ] 3.2 Implement resource sync status transitions for `Pending sync`, `Syncing`, `Synced`, and `Sync failed`.
- [ ] 3.3 Preserve Medplum resource id/reference and last successful sync time after success.
- [ ] 3.4 Preserve sync error and OperationOutcome body after failure.
- [ ] 3.5 Add minimal API endpoints or response fields needed for later workflows to inspect FHIR sync status.

## 4. Verification

- [x] 4.1 Add unit tests for local FHIR workflow record persistence and status display fields.
- [x] 4.2 Add unit tests for failure capture, including raw OperationOutcome preservation.
- [ ] 4.3 Add unit tests proving retry does not create duplicate resources when a Medplum identifier match exists.
- [ ] 4.4 Run the Healthcare Lab Python test suite and syntax checks.
