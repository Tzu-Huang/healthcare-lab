## MODIFIED Requirements

### Requirement: MWL order payload includes Scheduled Procedure Step identifiers
Healthcare Lab SHALL include the agreed Scheduled Procedure Step and order attributes needed by AP MWL query and result reconciliation.

#### Scenario: Order fields are mapped to DICOM MWL fields
- **WHEN** Healthcare Lab creates a dcm4chee MWL/order
- **THEN** the payload includes `00400001 Scheduled Station AE Title`
- **AND** the payload includes `00400009 Scheduled Procedure Step ID`
- **AND** the payload includes `0020000D Study Instance UID` when Healthcare Lab pre-allocates the study UID
- **AND** the payload includes `00080050 Accession Number`
- **AND** the payload includes `00401001 Requested Procedure ID`
- **AND** the payload includes `00741202 Worklist Label`

#### Scenario: Order fields use the selected dcm4chee profile
- **WHEN** Healthcare Lab prepares a future dcm4chee MWL/order request
- **THEN** it uses the selected dcm4chee connection profile for server identity
- **AND** it uses the profile MWL AE title and default Scheduled Station AE Title unless the workflow selects a more specific AP station
- **AND** it uses the profile DICOMweb and viewer settings for future query, verification, reconciliation, and viewer-link behavior
