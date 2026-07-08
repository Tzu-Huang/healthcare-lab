## ADDED Requirements

### Requirement: Medplum page displays FHIR resource inventory
Healthcare Lab SHALL provide a Medplum page that displays a read-only inventory of supported FHIR workflow resources with local sync metadata.

#### Scenario: Medplum navigation opens the inventory page
- **WHEN** a user selects the Medplum navigation item
- **THEN** Healthcare Lab displays a Medplum resource inventory page
- **AND** the page includes `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference` resources when records are available
- **AND** the page shows each local ledger record's sync status and Medplum resource reference when available

#### Scenario: Pending and failed workflow records remain visible
- **WHEN** a local FHIR workflow record has sync status `Pending sync` or `Sync failed`
- **THEN** the Medplum page displays the record as local workflow intent
- **AND** the page displays the local submitted FHIR JSON as the raw preview for that record
- **AND** the page does not present that local JSON as canonical Medplum live data

### Requirement: Medplum page uses live JSON for synced resources
Healthcare Lab SHALL prefer Medplum live FHIR API responses when previewing synced FHIR resources from the Medplum page.

#### Scenario: Synced resource live fetch succeeds
- **GIVEN** a local FHIR workflow record has sync status `Synced`
- **AND** the record has a Medplum resource reference
- **WHEN** a user selects the resource in the Medplum page
- **AND** Medplum returns the resource successfully
- **THEN** Healthcare Lab displays the Medplum live JSON as the raw preview
- **AND** the page identifies the preview source as Medplum live data

#### Scenario: Synced resource live fetch fails
- **GIVEN** a local FHIR workflow record has sync status `Synced`
- **AND** the record has a Medplum resource reference
- **WHEN** a user selects the resource in the Medplum page
- **AND** Medplum cannot return the resource because the request fails, is unauthorized, or the resource is unavailable
- **THEN** Healthcare Lab displays the live fetch failure to the user
- **AND** Healthcare Lab falls back to the local submitted FHIR JSON when available
- **AND** the page identifies the preview source as local submitted JSON fallback

### Requirement: Medplum page supports Patient-centered resource filtering
Healthcare Lab SHALL let users select a Patient and inspect supported FHIR resources that directly reference that Patient.

#### Scenario: Patient-centered resources are shown by direct reference
- **WHEN** a user selects a Patient in the Medplum page
- **THEN** Healthcare Lab shows supported resources that directly reference the selected `Patient/<id>`
- **AND** direct reference fields include `subject`, `patient`, and `for` where those fields contain a FHIR reference
- **AND** resources without a direct reference to the selected Patient are not shown in the selected Patient context

### Requirement: Medplum page provides non-destructive retry
Healthcare Lab SHALL provide retry actions for unsynced local FHIR workflow records from the Medplum page without exposing destructive Medplum operations.

#### Scenario: Pending or failed resource can be retried
- **GIVEN** a local FHIR workflow record has sync status `Pending sync` or `Sync failed`
- **WHEN** the user chooses Retry from the Medplum page
- **THEN** Healthcare Lab attempts to sync the existing local ledger record to Medplum through the idempotent sync path
- **AND** the page refreshes the record's sync status, Medplum reference, and error display from the retry result

#### Scenario: Synced resources do not expose retry
- **WHEN** a local FHIR workflow record has sync status `Synced`
- **THEN** the Medplum page does not expose a Retry action for that record
- **AND** the page does not expose delete, arbitrary update, or destructive Medplum actions
