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
