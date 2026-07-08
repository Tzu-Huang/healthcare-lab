## MODIFIED Requirements

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
