## ADDED Requirements

### Requirement: Patient page creates Medplum-backed FHIR Patients
Healthcare Lab SHALL create FHIR-mode Patients through a local-first, Medplum-backed workflow that preserves local intent and records Medplum sync state.

#### Scenario: FHIR Patient create succeeds in Medplum
- **WHEN** a user creates a Patient from the Patient page with mode `FHIR`
- **THEN** Healthcare Lab creates a local Patient record
- **AND** Healthcare Lab creates or updates a paired local FHIR workflow ledger record with resource type `Patient`
- **AND** Healthcare Lab immediately attempts to sync the FHIR Patient to Medplum
- **AND** Healthcare Lab stores the returned Medplum Patient id and `Patient/<id>` reference in the ledger when sync succeeds
- **AND** the Local Patients table displays the Patient with sync status `Synced` and the Medplum reference

#### Scenario: FHIR Patient create fails to sync
- **WHEN** a user creates a Patient from the Patient page with mode `FHIR`
- **AND** Medplum is unavailable, unauthorized, rejects the resource, or the request fails
- **THEN** Healthcare Lab keeps the local Patient record visible in Local Patients
- **AND** Healthcare Lab keeps the paired FHIR workflow ledger record with the submitted Patient resource JSON
- **AND** Healthcare Lab records sync status `Sync failed`
- **AND** Healthcare Lab displays a human-readable sync error for the Patient row
- **AND** the Patient row remains eligible for retry

#### Scenario: FHIR Patient retry is idempotent
- **GIVEN** a FHIR-mode Patient has a paired FHIR workflow ledger record that is not `Synced`
- **WHEN** the user retries sync from the Local Patients table
- **THEN** Healthcare Lab attempts to sync the existing ledger record to Medplum
- **AND** Healthcare Lab uses the deterministic Patient identifier to avoid duplicate Medplum Patients
- **AND** Healthcare Lab updates the row sync status, Medplum reference, and error display from the retry result

### Requirement: Patient page supports common FHIR Patient fields
Healthcare Lab SHALL support a scoped set of common Medplum/FHIR Patient fields in FHIR mode while preserving existing Patient modes.

#### Scenario: FHIR Patient preview includes common fields
- **WHEN** a user selects FHIR mode on the Patient page
- **AND** enters Patient demographics, active status, contact information, address fields, and optional managing organization context
- **THEN** the preview shows a FHIR R4 `Patient` resource
- **AND** the resource includes `active` when supplied
- **AND** the resource includes MRN identifier, name, gender, birth date, phone, and email where supplied
- **AND** the resource includes structured address fields where supplied
- **AND** the resource includes managing organization reference or display where supplied

#### Scenario: FHIR Demo Preset is syncable
- **WHEN** a user selects FHIR mode and applies the Demo Preset
- **THEN** the Patient form is populated with values that produce a valid FHIR R4 `Patient` preview
- **AND** creating the Patient uses the same local-first Medplum sync workflow as manually entered FHIR Patients

