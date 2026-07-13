## MODIFIED Requirements

### Requirement: Medplum page displays FHIR resource inventory
Healthcare Lab SHALL provide a Medplum page that displays supported FHIR workflow resources through a Patient-centered console with local sync metadata and the same primary layout rhythm as the other protocol server consoles.

#### Scenario: Medplum navigation opens the Patient-centered console
- **WHEN** a user selects the Medplum navigation item
- **THEN** Healthcare Lab displays a `Patient-Centered Console` heading
- **AND** the console includes a FHIR Patient list as its primary navigation surface
- **AND** the console includes distinct selected Patient summary and workflow regions
- **AND** the console includes a single full-width bottom JSON console for raw FHIR preview
- **AND** the page includes `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference` resources when records are available
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
- **THEN** Healthcare Lab shows an inline FHIR Orders section containing directly related `ServiceRequest` and `Task` records
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
- **AND** direct reference fields include `subject`, `patient`, and `for` where those fields contain a FHIR reference
- **AND** resources without a direct reference to that Patient are not shown in its Patient context

#### Scenario: Related resource actions update the JSON console
- **WHEN** a user selects Preview for a displayed Patient, ServiceRequest, Task, DiagnosticReport, Observation, or DocumentReference
- **THEN** Healthcare Lab updates the bottom JSON console to the selected resource
- **AND** Healthcare Lab does not open a separate rich viewer for that resource

### Requirement: Medplum DiagnosticReport console follows the GDT patient-rollup pattern
Healthcare Lab SHALL present the DiagnosticReport read experience in a Patient-centered console layout that follows the existing GDT and other protocol console patterns as closely as practical.

#### Scenario: DiagnosticReport console shows patient rollup and raw payload
- **WHEN** a user opens the Medplum page and selects a FHIR Patient
- **THEN** the page shows a Patient list as the primary navigation surface
- **AND** each Patient row provides an independent disclosure control for inline Order and Result rollups
- **AND** the page includes a selected Patient summary panel
- **AND** the page includes a separate workflow panel for ServiceRequest, live DiagnosticReport, and related-resource controls
- **AND** the bottom raw payload panel displays live or correctly labelled fallback FHIR JSON for the selected report or related resource

#### Scenario: DiagnosticReport read does not create or mirror reports
- **WHEN** Healthcare Lab fetches live DiagnosticReports for display
- **THEN** it does not create, submit, import, or mirror full live DiagnosticReport resources into the local ledger
- **AND** it may join local ledger metadata only for known workflow status, retry error, local submitted fallback, or locally-created references
