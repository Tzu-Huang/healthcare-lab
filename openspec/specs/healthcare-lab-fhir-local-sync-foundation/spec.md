# healthcare-lab-fhir-local-sync-foundation Specification

## Purpose
Define Healthcare Lab's local-first FHIR workflow ledger, Medplum sync status contract, retry/idempotency behavior, and mapping coverage for later Patient, Order, AP, and Result workflows.
## Requirements
### Requirement: Healthcare Lab persists local FHIR workflow records before sync
Healthcare Lab SHALL persist intended FHIR workflow resources locally before attempting to sync them to Medplum.

#### Scenario: Local FHIR record is created while Medplum is unavailable
- **WHEN** Healthcare Lab creates a local FHIR workflow record for a supported resource type
- **AND** Medplum is unavailable or not configured
- **THEN** the local record remains persisted in SQLite
- **AND** the record exposes a sync status of `Pending sync` or `Sync failed`
- **AND** the original FHIR resource JSON remains available for retry

#### Scenario: Supported resource type is recorded
- **WHEN** Healthcare Lab creates a local FHIR workflow record
- **THEN** the record stores the FHIR `resourceType`
- **AND** the resource type is one of `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, or `Provenance`
- **AND** the record stores a local source type and local source identifier

### Requirement: Healthcare Lab tracks Medplum sync state per FHIR resource
Healthcare Lab SHALL track Medplum synchronization state for each local FHIR workflow record.

#### Scenario: Resource is waiting for sync
- **WHEN** a local FHIR workflow record has not been successfully synced
- **THEN** Healthcare Lab exposes the resource sync status as `Pending sync`
- **AND** no Medplum resource id is required

#### Scenario: Resource sync succeeds
- **WHEN** Medplum accepts or returns an existing matching FHIR resource
- **THEN** Healthcare Lab stores the Medplum resource id
- **AND** Healthcare Lab stores the Medplum resource reference
- **AND** Healthcare Lab stores the last successful sync time
- **AND** Healthcare Lab exposes the resource sync status as `Synced`

#### Scenario: Resource sync fails
- **WHEN** Medplum rejects a sync request or the request fails
- **THEN** Healthcare Lab exposes the resource sync status as `Sync failed`
- **AND** Healthcare Lab stores a human-readable sync error
- **AND** Healthcare Lab preserves the raw response body when available
- **AND** Healthcare Lab preserves the FHIR `OperationOutcome` body when available

### Requirement: Healthcare Lab records sync attempts
Healthcare Lab SHALL preserve sync attempt history for FHIR workflow records.

#### Scenario: Sync attempt is recorded
- **WHEN** Healthcare Lab attempts to sync a local FHIR workflow record
- **THEN** Healthcare Lab records the attempt timestamp
- **AND** Healthcare Lab records the HTTP method and request URL
- **AND** Healthcare Lab records the request payload
- **AND** Healthcare Lab records the HTTP status and response payload when available
- **AND** Healthcare Lab links the attempt to the local FHIR workflow record

### Requirement: Medplum sync is idempotent
Healthcare Lab SHALL avoid duplicate Medplum resources when retrying local FHIR workflow sync.

#### Scenario: Retry finds an existing Medplum resource
- **WHEN** a local FHIR workflow record has a deterministic FHIR identifier
- **AND** Medplum search by that identifier returns an existing resource
- **THEN** Healthcare Lab stores the existing Medplum resource id and reference
- **AND** Healthcare Lab does not create a duplicate resource
- **AND** Healthcare Lab marks the local record as `Synced`

#### Scenario: Retry creates missing resource once
- **WHEN** Medplum search by deterministic identifier returns no matching resource
- **THEN** Healthcare Lab creates the resource in Medplum
- **AND** Healthcare Lab stores the returned Medplum resource id and reference
- **AND** a later retry with the same deterministic identifier does not create another copy

### Requirement: Healthcare Lab defines local-to-FHIR mapping coverage
Healthcare Lab SHALL define local-to-FHIR mapping metadata for the FHIR resources required by later Patient, Order, AP, and Result workflows.

#### Scenario: Mapping metadata is available
- **WHEN** a later workflow needs to create a FHIR resource
- **THEN** Healthcare Lab provides mapping metadata for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance`
- **AND** each mapping identifies the local source record type
- **AND** each mapping identifies the deterministic FHIR identifier policy
- **AND** each mapping identifies required Medplum references to other resources

### Requirement: Healthcare Lab syncs dependent FHIR resources in safe order
Healthcare Lab SHALL sync FHIR workflow resources in dependency order when syncing a multi-resource workflow.

#### Scenario: Patient-dependent workflow is synced
- **WHEN** a workflow contains a `Patient` resource and resources that reference that patient
- **THEN** Healthcare Lab syncs or resolves the `Patient` Medplum reference before syncing dependent resources

#### Scenario: Result workflow is synced
- **WHEN** a workflow contains result resources such as `Binary`, `Observation`, `DocumentReference`, `DiagnosticReport`, and `Provenance`
- **THEN** Healthcare Lab syncs resources in an order that allows references to point to known Medplum resources
- **AND** Healthcare Lab records any blocked dependent resources as not successfully synced when a required prior resource cannot be resolved

### Requirement: Healthcare Lab defines Medplum-backed FHIR source ownership
Healthcare Lab SHALL treat Medplum as the canonical source of truth for synced FHIR clinical resources while retaining local workflow ledger records for sync, retry, audit, and diagnostics.

#### Scenario: Synced resource is displayed from Medplum
- **WHEN** Healthcare Lab displays a FHIR resource inventory or patient-centered workflow view
- **AND** Medplum is reachable and authorized
- **THEN** Healthcare Lab uses Medplum FHIR API responses as the canonical resource data
- **AND** Healthcare Lab may join local ledger metadata such as sync status, deterministic identifier, Medplum reference, last sync time, and last error
- **AND** Healthcare Lab does not require a complete local shadow copy of the Medplum resource inventory

#### Scenario: Local ledger preserves unsynced workflow intent
- **WHEN** a Patient, Order, Task, or Result workflow attempts to create or update FHIR resources
- **AND** Medplum is unavailable, unauthorized, rejects the request, or returns an error
- **THEN** Healthcare Lab preserves the local workflow intent and request payload in the FHIR ledger
- **AND** Healthcare Lab exposes the record as local `Pending sync` or `Sync failed` workflow data
- **AND** Healthcare Lab does not present the unsynced local record as canonical Medplum clinical data

#### Scenario: Successful write reconciles Medplum identity
- **WHEN** Medplum accepts or returns an existing matching FHIR resource
- **THEN** Healthcare Lab stores the Medplum resource id and reference in the local ledger
- **AND** Healthcare Lab stores sync attempt details needed for audit and troubleshooting
- **AND** future inventory reads prefer Medplum live data for the canonical resource representation

### Requirement: Healthcare Lab reads FHIR workflow resources through Medplum live APIs
Healthcare Lab SHALL use Medplum live FHIR APIs as the default read path for synced Patient, Order, Task, and Result resources.

#### Scenario: Patient inventory is loaded
- **WHEN** Healthcare Lab loads a FHIR Patient inventory
- **THEN** Healthcare Lab queries Medplum `Patient` resources using the configured FHIR API
- **AND** Healthcare Lab joins matching local ledger metadata when available
- **AND** local pending or failed Patient intents remain distinguishable from Medplum-sourced Patients

#### Scenario: AP worklist is loaded
- **WHEN** Healthcare Lab or an AP-facing adapter loads a FHIR ECG worklist
- **THEN** it queries Medplum `Task` resources using the agreed worklist criteria
- **AND** it resolves or includes the referenced `ServiceRequest` and `Patient` context
- **AND** Healthcare Lab records AP pull/update audit data locally without treating the audit trail as the canonical Task resource

#### Scenario: Result inventory is loaded
- **WHEN** Healthcare Lab loads FHIR result history for a patient or order
- **THEN** Healthcare Lab queries Medplum resources such as `DiagnosticReport`, `Observation`, `DocumentReference`, and referenced `Binary` resources
- **AND** Healthcare Lab uses local ledger rows only to show workflow intent, retry/error status, Medplum references, and diagnostic details

### Requirement: Healthcare Lab avoids full local FHIR shadow ownership
Healthcare Lab SHALL NOT require a complete local duplicate of Medplum Patient, Order, Task, and Result resources for normal synced workflow operation.

#### Scenario: Later FHIR workflows define persistence
- **WHEN** a later FHIR Patient, Order, AP, Result, UI, or E2E ticket defines persistence behavior
- **THEN** it relies on the local FHIR ledger for workflow intent, sync status, retry/idempotency, request/response audit, OperationOutcome, and Medplum references
- **AND** it relies on Medplum APIs for canonical synced resource reads
- **AND** any offline cache or full local resource projection is explicitly scoped as separate behavior

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

