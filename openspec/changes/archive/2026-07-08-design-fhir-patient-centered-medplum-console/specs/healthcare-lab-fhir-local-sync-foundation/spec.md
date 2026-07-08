## MODIFIED Requirements

### Requirement: Medplum page displays FHIR resource inventory
Healthcare Lab SHALL provide a Medplum page that displays supported FHIR workflow resources through a Patient-centered console with local sync metadata.

#### Scenario: Medplum navigation opens the Patient-centered console
- **WHEN** a user selects the Medplum navigation item
- **THEN** Healthcare Lab displays a FHIR Patient-centered console
- **AND** the console includes a FHIR Patient list
- **AND** the console includes a selected Patient workspace
- **AND** the console includes a single bottom JSON console for raw FHIR preview
- **AND** the page includes `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference` resources when records are available
- **AND** the page shows local ledger sync status and Medplum resource reference when available

#### Scenario: Pending and failed workflow records remain visible
- **WHEN** a local FHIR workflow record has sync status `Pending sync` or `Sync failed`
- **THEN** the Medplum page displays the record as local workflow intent
- **AND** the page can display the local submitted FHIR JSON in the bottom JSON console for that record
- **AND** the page does not present that local JSON as canonical Medplum live data

### Requirement: Medplum page supports Patient-centered resource filtering
Healthcare Lab SHALL let users select a Patient and inspect supported FHIR resources that directly reference that Patient through Patient-centered controls.

#### Scenario: Patient list drives the selected Patient workspace
- **WHEN** a user selects a Patient from the Medplum page Patient list
- **THEN** Healthcare Lab displays that Patient as the selected Patient
- **AND** the selected Patient workspace shows ServiceRequest choices for that Patient
- **AND** the selected Patient workspace shows DiagnosticReport choices for that Patient
- **AND** the Patient row and workspace summarize sync status, Medplum reference, and last sync or update time when available

#### Scenario: Patient-centered resources are shown by direct reference
- **WHEN** a user selects a Patient in the Medplum page
- **THEN** Healthcare Lab shows supported resources that directly reference the selected `Patient/<id>`
- **AND** direct reference fields include `subject`, `patient`, and `for` where those fields contain a FHIR reference
- **AND** resources without a direct reference to the selected Patient are not shown in the selected Patient context

#### Scenario: ServiceRequest dropdown selects an order workflow
- **WHEN** a selected Patient has one or more ServiceRequest resources
- **THEN** Healthcare Lab shows a ServiceRequest dropdown in the selected Patient workspace
- **AND** each option label identifies the order code or display, status, and Medplum reference when available
- **AND** selecting a ServiceRequest updates the bottom JSON console to that ServiceRequest
- **AND** the workspace shows related Task resources as lightweight rows when they reference the selected Patient or selected ServiceRequest

#### Scenario: DiagnosticReport dropdown selects a result workflow
- **WHEN** a selected Patient has one or more DiagnosticReport resources
- **THEN** Healthcare Lab shows a DiagnosticReport dropdown in the selected Patient workspace
- **AND** each option label identifies the report title or code, status, and Medplum reference when available
- **AND** selecting a DiagnosticReport updates the bottom JSON console to that DiagnosticReport
- **AND** the workspace shows related Observation and DocumentReference resources as lightweight rows when they reference the selected Patient, selected ServiceRequest, or selected DiagnosticReport

#### Scenario: Related resource rows update the JSON console
- **WHEN** a user selects a displayed Task, Observation, or DocumentReference row
- **THEN** Healthcare Lab updates the bottom JSON console to the selected resource
- **AND** Healthcare Lab does not open a separate rich viewer for that resource

### Requirement: Medplum page uses live JSON for synced resources
Healthcare Lab SHALL prefer Medplum live FHIR API responses when previewing synced FHIR resources from the Medplum page bottom JSON console.

#### Scenario: Synced resource live fetch succeeds
- **GIVEN** a local FHIR workflow record has sync status `Synced`
- **AND** the record has a Medplum resource reference
- **WHEN** a user selects the resource in the Medplum page
- **AND** Medplum returns the resource successfully
- **THEN** Healthcare Lab displays the Medplum live JSON in the bottom JSON console
- **AND** the page identifies the console source as Medplum live data

#### Scenario: Synced resource live fetch fails
- **GIVEN** a local FHIR workflow record has sync status `Synced`
- **AND** the record has a Medplum resource reference
- **WHEN** a user selects the resource in the Medplum page
- **AND** Medplum cannot return the resource because the request fails, is unauthorized, or the resource is unavailable
- **THEN** Healthcare Lab displays the live fetch failure to the user
- **AND** Healthcare Lab falls back to the local submitted FHIR JSON when available
- **AND** the page identifies the console source as local submitted JSON fallback
