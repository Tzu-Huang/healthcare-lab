## ADDED Requirements

### Requirement: Order page creates Medplum-backed FHIR ECG orders
Healthcare Lab SHALL create FHIR-mode ECG orders from the Order page through a local-first, Medplum-backed workflow that persists a local order anchor and paired FHIR workflow ledger records for `ServiceRequest` and `Task`.

#### Scenario: FHIR Order create requires a synced FHIR Patient
- **WHEN** a user creates an Order from the Order page with mode `FHIR`
- **AND** the selected local Patient does not have a synced FHIR ledger record with a Medplum `Patient/<id>` reference
- **THEN** Healthcare Lab rejects the FHIR Order create request
- **AND** the response explains that a synced FHIR Patient is required before FHIR Order creation
- **AND** no `ServiceRequest` or `Task` resource is synced to Medplum

#### Scenario: FHIR Order creates ServiceRequest and Task
- **WHEN** a user creates an Order from the Order page with mode `FHIR`
- **AND** the selected Patient has a synced Medplum `Patient/<id>` reference
- **THEN** Healthcare Lab creates a local order record for the FHIR order
- **AND** Healthcare Lab creates or updates a local FHIR workflow ledger record with resource type `ServiceRequest`
- **AND** the `ServiceRequest.subject.reference` is the selected Patient's Medplum reference
- **AND** Healthcare Lab syncs the `ServiceRequest` to Medplum
- **AND** Healthcare Lab creates or updates a local FHIR workflow ledger record with resource type `Task`
- **AND** the `Task.for.reference` is the selected Patient's Medplum reference
- **AND** the `Task.focus.reference` is the synced `ServiceRequest/<id>` reference
- **AND** Healthcare Lab syncs the `Task` to Medplum

#### Scenario: Task sync failure preserves local workflow intent
- **WHEN** FHIR Order creation syncs the `ServiceRequest` successfully
- **AND** the generated `Task` sync fails
- **THEN** Healthcare Lab preserves the local order record
- **AND** Healthcare Lab preserves both FHIR workflow ledger records
- **AND** the `ServiceRequest` ledger record remains `Synced`
- **AND** the `Task` ledger record records `Sync failed`
- **AND** Local Orders displays the order with independent ServiceRequest and Task sync status

### Requirement: Order page FHIR mode exposes a full ServiceRequest form
Healthcare Lab SHALL expose the full requested ServiceRequest-oriented field set when the Order page protocol mode is `FHIR`.

#### Scenario: FHIR Order form displays ServiceRequest fields
- **WHEN** a user selects FHIR mode on the Order page
- **THEN** the page displays FHIR ServiceRequest fields for resource type, id, identifier, instantiates canonical, instantiates URI, based on, replaces, requisition, status, intent, category, priority, do not perform, code, order detail, quantity, subject, encounter, occurrence, as needed, authored on, requester, performer type, performer, location code, location reference, reason code, reason reference, insurance, supporting info, specimen, body site, note, patient instruction, and relevant history
- **AND** the `resourceType` value is `ServiceRequest`
- **AND** `status`, `intent`, and `subject` are required for create
- **AND** `subject` can only select a Patient with a synced Medplum `Patient/<id>` reference

#### Scenario: FHIR Order preview renders ServiceRequest JSON
- **WHEN** a user enters valid FHIR Order form values
- **THEN** the Order page preview displays a FHIR R4 `ServiceRequest` JSON resource
- **AND** the preview includes deterministic identifiers for the local order source
- **AND** the preview includes the selected Patient reference in `subject.reference`
- **AND** the preview includes ECG code and priority when supplied

#### Scenario: FHIR Order demo preset is syncable
- **WHEN** a user selects FHIR mode and applies the Demo Preset
- **THEN** the Order form is populated with values that produce a valid FHIR R4 `ServiceRequest` preview
- **AND** creating the Order uses the same local-first Medplum sync workflow as manually entered FHIR Orders

### Requirement: Generated Task represents the ECG AP worklist item
Healthcare Lab SHALL generate a FHIR `Task` resource for each FHIR ECG order to represent the AP/worklist execution item.

#### Scenario: Generated Task has required worklist references
- **WHEN** Healthcare Lab generates the Task for a FHIR ECG order
- **THEN** the `Task.status` is `requested`
- **AND** the `Task.intent` is `order`
- **AND** the `Task.for.reference` matches the selected Patient Medplum reference
- **AND** the `Task.focus.reference` matches the synced ServiceRequest Medplum reference
- **AND** the Task includes an ECG worklist code
- **AND** the Task has a deterministic identifier derived from the local order source

### Requirement: Local Orders displays FHIR order sync state
Healthcare Lab SHALL show FHIR Orders in Local Orders with ServiceRequest and Task synchronization status.

#### Scenario: FHIR Order appears in Local Orders
- **WHEN** a FHIR Order has been created
- **THEN** Local Orders displays the local order identity, selected Patient, ServiceRequest order code, requested time, and created time
- **AND** Local Orders displays the ServiceRequest sync status and Medplum reference or sync error
- **AND** Local Orders displays the Task sync status and Medplum reference or sync error

