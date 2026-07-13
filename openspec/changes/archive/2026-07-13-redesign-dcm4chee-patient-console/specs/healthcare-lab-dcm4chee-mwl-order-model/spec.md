## ADDED Requirements

### Requirement: dcm4chee console is patient-centered
Healthcare Lab SHALL present the dcm4chee console around a dominant Patient list with independent Patient selection and Order/Result disclosure.

#### Scenario: Patient list uses the OIE-style workspace proportions
- **WHEN** the dcm4chee console is displayed at a supported desktop width
- **THEN** the Patient list occupies the dominant console area
- **AND** the list provides sufficient vertical space to review multiple Patients without appearing as a short summary card
- **AND** the page retains Healthcare Lab styling and responsive behavior

#### Scenario: User selects a Patient row
- **GIVEN** one or more DICOM Patients are listed
- **WHEN** the user activates a Patient row outside its disclosure control or row actions
- **THEN** Healthcare Lab selects that Patient
- **AND** it updates one Patient preview below the complete Patient list
- **AND** it does not expand or collapse the Patient's Order and Result sections

#### Scenario: User expands a Patient row
- **GIVEN** a DICOM Patient row is visible
- **WHEN** the user activates the leading disclosure control
- **THEN** Healthcare Lab expands or collapses that Patient's inline detail independently of Patient selection
- **AND** the control exposes its expanded state through accessible semantics
- **AND** expanded detail contains an Order section and a Result section for that Patient

#### Scenario: Patient Orders have one list presentation
- **WHEN** the dcm4chee Patient workspace is rendered
- **THEN** Orders are listed inside the expanded Patient detail
- **AND** applicable send, retry, verify, preview, or inspection actions remain discoverable from the Patient/order workflow
- **AND** the UI does not render a separate `MWL Selected Patient Orders` section

## MODIFIED Requirements

### Requirement: Patient DICOM results use PACS-style hierarchical browsing
Healthcare Lab SHALL render patient dcm4chee DICOM results as structured DICOM-field tables with Study, Series, and Instance hierarchy where identifiers support it, while preserving Healthcare Lab visual styling.

#### Scenario: Matched results are grouped by order and study
- **GIVEN** a patient has dcm4chee DICOM result records matched to one or more local orders
- **WHEN** the Patient's inline Result section is rendered
- **THEN** the UI groups matched results by local order
- **AND** each order group shows expandable Study rows
- **AND** each Study row can expose nested Series rows
- **AND** each Series row can expose nested Instance rows

#### Scenario: DICOM result tables use dcm4chee-style metadata labels
- **GIVEN** a DICOM Study, Series, Instance, or diagnostic result row is visible
- **WHEN** the user reads the Patient's inline Result section
- **THEN** the result is presented through labeled table columns rather than a serialized object or raw JSON dump
- **AND** the table labels use DICOM/dcm4chee-style field names such as Accession Number, Study Instance UID, Series Instance UID, SOP Instance UID, Modality, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID
- **AND** Healthcare Lab workflow status labels remain separate from the DICOM metadata labels
- **AND** long values remain contained within the result-table region

#### Scenario: Unresolved result diagnostics remain visible
- **GIVEN** result refresh produces no-result, query-failed, ambiguous, duplicate, wrong-patient, missing-accession, or unlinked diagnostics
- **WHEN** the Patient's inline Result section is rendered
- **THEN** the UI shows those diagnostics as structured rows in an unresolved group
- **AND** it does not hide diagnostics merely because Study, Series, or Instance identifiers are incomplete
- **AND** it does not use raw object printing as the primary diagnostic presentation
