## 1. Patient FHIR Mapping

- [x] 1.1 Extend Patient form payload validation/storage for common FHIR Patient fields: active status, email, structured address fields, and optional managing organization context.
- [x] 1.2 Update FHIR Patient preview/building logic to include the new fields while preserving current MRN, name, DOB, sex, phone, and visit-number behavior.
- [x] 1.3 Keep Demo Preset capable of producing a valid, syncable FHIR Patient.

## 2. Local Create And Medplum Sync

- [x] 2.1 When `/api/patients` creates a FHIR-mode Patient, create or update the paired local FHIR workflow ledger record for resource type `Patient`.
- [x] 2.2 Immediately attempt Medplum sync for that ledger record using the configured Medplum FHIR base URL.
- [x] 2.3 Return Patient response metadata that includes the paired FHIR record id, sync status, Medplum reference, last sync time, and sync error.
- [x] 2.4 Preserve the local Patient and ledger record when Medplum sync fails.

## 3. Patient UI

- [x] 3.1 Add scoped FHIR-only fields to the Patient form.
- [x] 3.2 Show FHIR sync status and Medplum reference in Local Patients.
- [x] 3.3 Show sync failure text for failed FHIR rows.
- [x] 3.4 Add row-level retry for FHIR Patients that are not `Synced`.

## 4. Verification

- [x] 4.1 Add store tests for FHIR Patient payload mapping and paired ledger creation.
- [x] 4.2 Add app tests for successful create-and-sync, sync failure preservation, and retry/idempotency.
- [x] 4.3 Add frontend/API regression coverage where practical for status/reference display.
- [x] 4.4 Run OpenSpec validation and the Healthcare Lab Python test suite.
