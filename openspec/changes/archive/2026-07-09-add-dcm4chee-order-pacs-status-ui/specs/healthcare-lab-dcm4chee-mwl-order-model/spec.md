## ADDED Requirements

### Requirement: DICOM order detail summarizes dcm4chee workflow status
Healthcare Lab SHALL show dcm4chee MWL/order and PACS result state from the selected DICOM order detail using operator-readable workflow statuses.

#### Scenario: User inspects selected DICOM order status
- **GIVEN** a local DICOM MWL order has dcm4chee mapping, verification, or result metadata
- **WHEN** the user selects the order in the Healthcare Lab order workspace
- **THEN** the UI shows MWL Sync status
- **AND** the UI shows MWL Queryable status
- **AND** the UI shows AP C-STORE Result status
- **AND** the UI shows Reconciliation status
- **AND** the UI keeps retry, verify, refresh, and attempt-history actions discoverable when applicable

#### Scenario: DICOM order diagnostics remain readable
- **GIVEN** dcm4chee sync, verification, result refresh, or reconciliation has failed or produced an ambiguous outcome
- **WHEN** the user inspects the selected order
- **THEN** Healthcare Lab shows the latest status, error type, error text, timestamps, and relevant identifiers without requiring the user to parse raw JSON
- **AND** raw request or response payloads remain available in expandable diagnostic sections when retained

### Requirement: Patient DICOM results use PACS-style hierarchical browsing
Healthcare Lab SHALL render patient dcm4chee DICOM results as a Study, Series, and Instance hierarchy while preserving Healthcare Lab visual styling.

#### Scenario: Matched results are grouped by order and study
- **GIVEN** a patient has dcm4chee DICOM result records matched to one or more local orders
- **WHEN** the patient DICOM results section is rendered
- **THEN** the UI groups matched results by local order
- **AND** each order group shows expandable Study rows
- **AND** each Study row can expose nested Series rows
- **AND** each Series row can expose nested Instance rows

#### Scenario: DICOM result tables use dcm4chee-style metadata labels
- **GIVEN** a DICOM Study, Series, or Instance row is visible
- **WHEN** the user reads the PACS result browser
- **THEN** the table labels use DICOM/dcm4chee-style field names such as Accession Number, Study Instance UID, Series Instance UID, SOP Instance UID, Modality, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID
- **AND** Healthcare Lab workflow status labels remain separate from the DICOM metadata labels

#### Scenario: Unresolved result diagnostics remain visible
- **GIVEN** result refresh produces no-result, query-failed, ambiguous, duplicate, wrong-patient, missing-accession, or unlinked diagnostics
- **WHEN** the patient DICOM results section is rendered
- **THEN** the UI shows those diagnostics in an unresolved group
- **AND** it does not hide diagnostics merely because Study, Series, or Instance identifiers are incomplete

### Requirement: DICOM result actions preserve viewer and retrieve access
Healthcare Lab SHALL expose dcm4chee viewer and retrieve actions from the PACS-style result browser when URLs are available.

#### Scenario: User opens a matched study
- **GIVEN** a matched Study row has a dcm4chee viewer URL
- **WHEN** the user activates the viewer action
- **THEN** Healthcare Lab opens the configured dcm4chee viewer link for that study

#### Scenario: User copies retrieve links
- **GIVEN** a Study, Series, or Instance row has a retrieve URL
- **WHEN** the user activates the copy/retrieve action
- **THEN** Healthcare Lab exposes the corresponding dcm4chee retrieve URL without changing the local reconciliation state
