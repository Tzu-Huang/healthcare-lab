## Modified Requirements

### Requirement: Result reconciliation uses strongest available identifiers first
Healthcare Lab SHALL define deterministic matching precedence for reconciling AP C-STORE results stored in dcm4chee-arc back to local MWL orders.

#### Scenario: Returned DICOM study is matched to a local MWL order
- **WHEN** Healthcare Lab reconciles a returned DICOM study from dcm4chee-arc
- **THEN** it first matches by `0020000D Study Instance UID` when available
- **AND** otherwise matches by `00080050 Accession Number` within the dcm4chee server namespace
- **AND** otherwise matches by `00401001 Requested Procedure ID` and `00400009 Scheduled Procedure Step ID`
- **AND** weak fallback matching by Patient ID, issuer, Scheduled Station AE Title, modality/time window, and order status is treated as ambiguous unless exactly one active candidate exists

#### Scenario: Returned DICOM result validates patient identity
- **GIVEN** Healthcare Lab finds a result candidate by Accession Number, Requested Procedure ID, or Scheduled Procedure Step ID
- **WHEN** the returned DICOM metadata includes Patient ID or Issuer of Patient ID
- **THEN** Healthcare Lab compares those values with the canonical PACS/MWL ledger values
- **AND** it does not mark the result as matched when the patient identity conflicts
- **AND** it records a wrong-patient or identifier-mismatch diagnostic instead

### Requirement: Result reconciliation can find local orders from stored dcm4chee identifiers
Healthcare Lab SHALL provide deterministic local lookup behavior that can match future dcm4chee studies or AP C-STORE results back to the original Healthcare Lab order using the PACS/MWL ledger.

#### Scenario: Study is matched by strongest identifiers
- **WHEN** Healthcare Lab receives or queries dcm4chee study/result identifiers
- **THEN** it first matches by Study Instance UID when available
- **AND** otherwise matches by Accession Number within the dcm4chee profile/server namespace
- **AND** otherwise matches by Requested Procedure ID and Scheduled Procedure Step ID
- **AND** weak fallback matching by Patient ID, issuer, station, modality, or time window is treated as ambiguous unless exactly one active candidate exists

#### Scenario: Weak result candidates remain inspectable
- **GIVEN** Healthcare Lab queries dcm4chee and finds result candidates that cannot be matched by strong identifiers
- **WHEN** the candidates only match by weak patient, modality, station, or time-window signals
- **THEN** Healthcare Lab records the candidates as ambiguous or unlinked
- **AND** it exposes the relevant candidate metadata for operator debugging
- **AND** it does not update the local order as reconciled unless a deterministic match is established

## New Requirements

### Requirement: dcm4chee result refresh is manually triggered
Healthcare Lab SHALL provide an explicit operator-triggered refresh path for querying dcm4chee-arc for AP C-STORE results.

#### Scenario: Operator refreshes DICOM results for a patient
- **GIVEN** a Healthcare Lab patient has one or more local dcm4chee MWL orders or DICOM identifiers
- **WHEN** an operator triggers dcm4chee result refresh for that patient
- **THEN** Healthcare Lab queries the configured dcm4chee archive result surface for relevant studies, series, and instances
- **AND** it runs reconciliation against the canonical PACS/MWL ledger
- **AND** it returns updated matched and unresolved DICOM result state for that patient

#### Scenario: Refresh failure preserves existing local state
- **GIVEN** Healthcare Lab has existing local orders or previously reconciled results
- **WHEN** the dcm4chee result refresh query fails
- **THEN** Healthcare Lab preserves existing local order and result state
- **AND** it records query-failure diagnostics with the target endpoint and error details when available

### Requirement: dcm4chee result metadata is persisted locally
Healthcare Lab SHALL persist enough metadata about reconciled and unresolved dcm4chee results to support patient display and debugging without storing full DICOM object bytes locally.

#### Scenario: Result metadata is saved after refresh
- **WHEN** Healthcare Lab discovers a dcm4chee study, series, or instance during result refresh
- **THEN** it stores available Study Instance UID, Series Instance UID, SOP Instance UID, Accession Number, Patient ID, Issuer of Patient ID, Requested Procedure ID, Scheduled Procedure Step ID, modality, and timestamps
- **AND** it stores profile/server source identity and refresh timestamps
- **AND** it stores reconciliation status, match method, matched order or mapping identity when available, and diagnostic payload when relevant

#### Scenario: Viewer and retrieval links are saved when derivable
- **WHEN** Healthcare Lab has enough dcm4chee profile and DICOM identifier data to construct viewer or retrieval links
- **THEN** it stores or returns links for opening the study in the configured viewer
- **AND** it stores or returns DICOMweb retrieval links for study, series, or instance metadata when available

### Requirement: Patient view exposes refreshed DICOM results
Healthcare Lab SHALL expose dcm4chee AP C-STORE result state under the patient view so operators can inspect matched and unresolved returned results.

#### Scenario: Patient shows expandable DICOM results
- **GIVEN** a patient has matched or unresolved dcm4chee result records
- **WHEN** the user opens the patient detail or order workspace
- **THEN** the UI presents a patient-level expandable DICOM results section
- **AND** matched results are grouped by local order when possible
- **AND** unresolved, ambiguous, duplicate, wrong-patient, missing-accession, and query-failed diagnostics remain visible for debugging

#### Scenario: Result row shows actionable identifiers
- **WHEN** a DICOM result appears in the patient result section
- **THEN** the row includes reconciliation status, modality, relevant timestamps, Study Instance UID, Accession Number, and patient identity when available
- **AND** it offers viewer/open actions when configured links are available
