## ADDED Requirements

### Requirement: Medplum page fetches live DiagnosticReports by Patient
Healthcare Lab SHALL fetch live `DiagnosticReport` resources from Medplum for the selected FHIR Patient without requiring those reports to already exist as local ledger records.

#### Scenario: Selecting a Patient fetches live DiagnosticReports
- **GIVEN** the Medplum page has a selected FHIR Patient with a Medplum `Patient/<id>` reference
- **WHEN** the user selects that Patient
- **THEN** Healthcare Lab queries Medplum for `DiagnosticReport` resources whose subject is that Patient
- **AND** the Medplum page displays the returned live reports in the selected Patient workspace
- **AND** the response preserves the raw FHIR Bundle JSON for preview and troubleshooting

#### Scenario: Empty DiagnosticReport search is not an outage
- **GIVEN** Medplum is reachable and authorized
- **WHEN** the selected Patient DiagnosticReport search returns an empty Bundle
- **THEN** Healthcare Lab displays that no reports were found for the selected Patient
- **AND** the Medplum connection or smoke/check status is not marked failed solely because the Bundle is empty

#### Scenario: Patient-level DiagnosticReports remain visible
- **GIVEN** a selected Patient has a live DiagnosticReport whose `basedOn` does not reference a ServiceRequest
- **WHEN** Healthcare Lab displays that Patient's report results
- **THEN** the report remains visible under a patient-level result grouping
- **AND** the UI labels it as patient-level rather than order-linked

### Requirement: Medplum page narrows live DiagnosticReports by ServiceRequest
Healthcare Lab SHALL narrow displayed live DiagnosticReports to a selected `ServiceRequest` when possible while retaining clear patient-level results.

#### Scenario: ServiceRequest selection uses based-on search
- **GIVEN** the Medplum page has a selected Patient and selected ServiceRequest
- **WHEN** Healthcare Lab fetches live DiagnosticReports for the selected order context
- **THEN** it prefers a Medplum search using `DiagnosticReport?based-on=ServiceRequest/<id>`
- **AND** it displays reports linked to the selected ServiceRequest as order-linked results

#### Scenario: Unsupported based-on search falls back safely
- **GIVEN** Medplum does not support or rejects the `DiagnosticReport?based-on=ServiceRequest/<id>` search
- **WHEN** Healthcare Lab needs to narrow reports by ServiceRequest
- **THEN** it fetches DiagnosticReports by the selected Patient
- **AND** filters the returned reports server-side by `DiagnosticReport.basedOn[]`
- **AND** surfaces a successful result state when fallback filtering succeeds

### Requirement: Medplum page summarizes DiagnosticReport relationships
Healthcare Lab SHALL parse useful live DiagnosticReport relationship metadata for UI rendering while treating Medplum as the canonical read source.

#### Scenario: DiagnosticReport summaries include scan-friendly fields
- **WHEN** Healthcare Lab returns live DiagnosticReports to the Medplum page
- **THEN** each report summary includes report code or display, status, effective or issued date, linked order reference when available, result count, and attachment or reference count
- **AND** each summary identifies whether the report is order-linked or patient-level

#### Scenario: Related FHIR references are listed
- **WHEN** a live DiagnosticReport contains `result`, `media`, `presentedForm`, or related references
- **THEN** Healthcare Lab exposes lightweight related rows for `Observation`, `DocumentReference`, and `Binary` references when available
- **AND** selecting a related row fetches and previews the related live Medplum JSON lazily

#### Scenario: Live fetch failure is distinguished from local fallback
- **WHEN** live DiagnosticReport fetch fails because Medplum is unauthorized, unavailable, returns an HTTP error, or returns a malformed response
- **THEN** Healthcare Lab surfaces the fetch failure to the user
- **AND** local submitted fallback is used only when tied to a known local workflow record
- **AND** the UI labels live Medplum data, local submitted fallback, local-only workflow intent, and fetch failed states distinctly

### Requirement: Medplum DiagnosticReport console follows the GDT patient-rollup pattern
Healthcare Lab SHALL present the DiagnosticReport read experience in a Patient-centered console layout that follows the existing GDT console pattern as closely as practical.

#### Scenario: DiagnosticReport console shows patient rollup and raw payload
- **WHEN** a user opens the Medplum page and selects a FHIR Patient
- **THEN** the page shows a Patient list as the primary navigation surface
- **AND** the selected Patient workspace includes expandable order/result rollup sections
- **AND** the page includes a selected Patient summary panel
- **AND** the page includes a related artifact/resource list
- **AND** the bottom raw payload panel displays live FHIR JSON for the selected report or related resource

#### Scenario: DiagnosticReport read does not create or mirror reports
- **WHEN** Healthcare Lab fetches live DiagnosticReports for display
- **THEN** it does not create, submit, import, or mirror full live DiagnosticReport resources into the local ledger
- **AND** it may join local ledger metadata only for known workflow status, retry error, local submitted fallback, or locally-created references

