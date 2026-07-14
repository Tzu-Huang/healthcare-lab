## MODIFIED Requirements

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
- **AND** the resource type is one of `Patient`, `ServiceRequest`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, or `Provenance`
- **AND** the record stores a local source type and local source identifier

### Requirement: Healthcare Lab defines local-to-FHIR mapping coverage
Healthcare Lab SHALL define local-to-FHIR mapping metadata for the FHIR resources required by later Patient, Order, AP, and Result workflows.

#### Scenario: Mapping metadata is available
- **WHEN** a later workflow needs to create a FHIR resource
- **THEN** Healthcare Lab provides mapping metadata for `Patient`, `ServiceRequest`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance`
- **AND** each mapping identifies the local source record type
- **AND** each mapping identifies the deterministic FHIR identifier policy
- **AND** each mapping identifies required Medplum references to other resources

### Requirement: Healthcare Lab defines Medplum-backed FHIR source ownership
Healthcare Lab SHALL treat Medplum as the canonical source of truth for synced FHIR clinical resources while retaining local workflow ledger records for sync, retry, audit, and diagnostics.

#### Scenario: Synced resource is displayed from Medplum
- **WHEN** Healthcare Lab displays a FHIR resource inventory or patient-centered workflow view
- **AND** Medplum is reachable and authorized
- **THEN** Healthcare Lab uses Medplum FHIR API responses as the canonical resource data
- **AND** Healthcare Lab may join local ledger metadata such as sync status, deterministic identifier, Medplum reference, last sync time, and last error
- **AND** Healthcare Lab does not require a complete local shadow copy of the Medplum resource inventory

#### Scenario: Local ledger preserves unsynced workflow intent
- **WHEN** a Patient, Order, or Result workflow attempts to create or update FHIR resources
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
Healthcare Lab SHALL use Medplum live FHIR APIs as the default read path for synced Patient, Order, and Result resources.

#### Scenario: Patient inventory is loaded
- **WHEN** Healthcare Lab loads a FHIR Patient inventory
- **THEN** Healthcare Lab queries Medplum `Patient` resources using the configured FHIR API
- **AND** Healthcare Lab joins matching local ledger metadata when available
- **AND** local pending or failed Patient intents remain distinguishable from Medplum-sourced Patients

#### Scenario: Order inventory is loaded
- **WHEN** Healthcare Lab loads FHIR ECG orders for a patient
- **THEN** it uses Medplum `ServiceRequest` resources as the order representation
- **AND** it resolves or includes the referenced `Patient` context
- **AND** it does not require a FHIR `Task` worklist resource

#### Scenario: Result inventory is loaded
- **WHEN** Healthcare Lab loads FHIR result history for a patient or order
- **THEN** Healthcare Lab queries Medplum resources such as `DiagnosticReport`, `Observation`, `DocumentReference`, and referenced `Binary` resources
- **AND** Healthcare Lab uses local ledger rows only to show workflow intent, retry/error status, Medplum references, and diagnostic details

### Requirement: Healthcare Lab avoids full local FHIR shadow ownership
Healthcare Lab SHALL NOT require a complete local duplicate of Medplum Patient, Order, and Result resources for normal synced workflow operation.

#### Scenario: Later FHIR workflows define persistence
- **WHEN** a later FHIR Patient, Order, AP, Result, UI, or E2E ticket defines persistence behavior
- **THEN** it relies on the local FHIR ledger for workflow intent, sync status, retry/idempotency, request/response audit, OperationOutcome, and Medplum references
- **AND** it relies on Medplum APIs for canonical synced resource reads
- **AND** any offline cache or full local resource projection is explicitly scoped as separate behavior

### Requirement: Medplum page displays FHIR resource inventory
Healthcare Lab SHALL provide a Medplum page that displays supported FHIR workflow resources through a Patient-centered console with local sync metadata and the same primary layout rhythm as the other protocol server consoles.

#### Scenario: Medplum navigation opens the Patient-centered console
- **WHEN** a user selects the Medplum navigation item
- **THEN** Healthcare Lab displays a `Patient-Centered Console` heading
- **AND** the console includes a FHIR Patient list as its primary navigation surface
- **AND** the console includes distinct selected Patient summary and workflow regions
- **AND** the console includes a single full-width bottom JSON console for raw FHIR preview
- **AND** the page includes `Patient`, `ServiceRequest`, `DiagnosticReport`, `Observation`, and `DocumentReference` resources when records are available
- **AND** the page shows local ledger sync status and Medplum resource reference when available

#### Scenario: Pending and failed workflow records remain visible
- **WHEN** a local FHIR workflow record has sync status `Pending sync` or `Sync failed`
- **THEN** the Medplum page displays the record as local workflow intent
- **AND** the page can display the local submitted FHIR JSON in the bottom JSON console for that record
- **AND** the page does not present that local JSON as canonical Medplum live data

### Requirement: Medplum page supports Patient-centered resource filtering
Healthcare Lab SHALL let users select a Patient, independently disclose Patient rows, and inspect supported FHIR resources that directly reference that Patient through Patient-centered controls.

#### Scenario: Patient selection is independent from disclosure
- **WHEN** a user selects a Patient row
- **THEN** Healthcare Lab updates the selected Patient summary and workflow context
- **AND** Patient disclosure state does not change
- **WHEN** a user activates the Patient row disclosure control
- **THEN** Healthcare Lab expands or collapses that Patient's inline details
- **AND** the selected Patient does not change solely because disclosure changed

#### Scenario: Expanded Patient shows workflow rollups
- **WHEN** a user expands a Patient row
- **THEN** Healthcare Lab shows an inline FHIR Orders section containing directly related `ServiceRequest` records
- **AND** Healthcare Lab shows an inline FHIR Results section containing directly related `DiagnosticReport`, `Observation`, and `DocumentReference` records
- **AND** each resource row identifies its resource type, summary, sync state, reference, and available non-destructive actions

#### Scenario: Patient list drives the selected Patient workspace
- **WHEN** a user selects a Patient from the Medplum page Patient list
- **THEN** Healthcare Lab displays that Patient as the selected Patient
- **AND** the selected Patient summary shows sync status, Medplum reference, and last update when available
- **AND** the workflow region shows ServiceRequest choices for that Patient
- **AND** the workflow region shows DiagnosticReport choices and live result status for that Patient

#### Scenario: Patient-centered resources are shown by direct reference
- **WHEN** a user selects or expands a Patient in the Medplum page
- **THEN** Healthcare Lab shows supported resources that directly reference the selected `Patient/<id>`
- **AND** direct reference fields include `subject` and `patient` where those fields contain a FHIR reference
- **AND** resources without a direct reference to that Patient are not shown in its Patient context

#### Scenario: Related resource actions update the JSON console
- **WHEN** a user selects Preview for a displayed Patient, ServiceRequest, DiagnosticReport, Observation, or DocumentReference
- **THEN** Healthcare Lab updates the bottom JSON console to the selected resource
- **AND** Healthcare Lab does not open a separate rich viewer for that resource

### Requirement: Order page creates Medplum-backed FHIR ECG orders
Healthcare Lab SHALL create FHIR-mode ECG orders from the Order page through a local-first, Medplum-backed workflow that persists a local order anchor and one FHIR workflow ledger record for `ServiceRequest`.

#### Scenario: FHIR Order create requires a synced FHIR Patient
- **WHEN** a user creates an Order from the Order page with mode `FHIR`
- **AND** the selected local Patient does not have a synced FHIR ledger record with a Medplum `Patient/<id>` reference
- **THEN** Healthcare Lab rejects the FHIR Order create request
- **AND** the response explains that a synced FHIR Patient is required before FHIR Order creation
- **AND** no `ServiceRequest` resource is synced to Medplum

#### Scenario: FHIR Order creates ServiceRequest
- **WHEN** a user creates an Order from the Order page with mode `FHIR`
- **AND** the selected Patient has a synced Medplum `Patient/<id>` reference
- **THEN** Healthcare Lab creates a local order record for the FHIR order
- **AND** Healthcare Lab creates or updates a local FHIR workflow ledger record with resource type `ServiceRequest`
- **AND** the `ServiceRequest.subject.reference` is the selected Patient's Medplum reference
- **AND** Healthcare Lab syncs the `ServiceRequest` to Medplum
- **AND** Healthcare Lab does not create or sync a `Task` resource

#### Scenario: ServiceRequest sync failure preserves local workflow intent
- **WHEN** FHIR Order creation cannot sync the generated `ServiceRequest`
- **THEN** Healthcare Lab preserves the local order record
- **AND** Healthcare Lab preserves the ServiceRequest workflow ledger record
- **AND** the ServiceRequest ledger record records `Sync failed`
- **AND** Local Orders displays the ServiceRequest sync error

### Requirement: Local Orders displays FHIR order sync state
Healthcare Lab SHALL show FHIR Orders in Local Orders with ServiceRequest synchronization status.

#### Scenario: FHIR Order appears in Local Orders
- **WHEN** a FHIR Order has been created
- **THEN** Local Orders displays the local order identity, selected Patient, ServiceRequest order code, requested time, and created time
- **AND** Local Orders displays the ServiceRequest sync status and Medplum reference or sync error
- **AND** Local Orders marks the order accepted only when the ServiceRequest is synced with a valid Medplum reference

## REMOVED Requirements

### Requirement: Generated Task represents the ECG AP worklist item
**Reason**: Healthcare Lab does not manage a distinct Task assignment or execution lifecycle, so the generated Task duplicates ServiceRequest order state without providing an actual worklist workflow.

**Migration**: New and retried FHIR orders use ServiceRequest as the sole order resource. Existing local and remote Task resources remain historical data and are not deleted by this change.
