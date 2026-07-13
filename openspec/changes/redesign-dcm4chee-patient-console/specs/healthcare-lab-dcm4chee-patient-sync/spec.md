## MODIFIED Requirements

### Requirement: dcm4chee Patient sync status is visible to operators
Healthcare Lab SHALL expose readable dcm4chee Patient sync status in Patient-facing and DICOM order-facing views without allowing long sync metadata to escape its containing card.

#### Scenario: Patient page displays dcm4chee sync status
- **WHEN** a local DICOM Patient has a dcm4chee Patient sync mapping or attempt
- **THEN** Healthcare Lab shows whether the Patient is synced, pending, retryable, or failed
- **AND** it shows the latest actionable error when sync is not successful

#### Scenario: DICOM order page displays Patient precondition status
- **WHEN** a DICOM MWL order references a Patient with missing or failed dcm4chee sync
- **THEN** Healthcare Lab shows that MWL creation depends on dcm4chee Patient existence
- **AND** it preserves the Patient sync failure as the root cause

#### Scenario: Patient sync metadata remains inside its card
- **GIVEN** the dcm4chee Patient Sync card contains Status, Retryable, HL7 endpoint, ACK, Last Sync, Error Type, or Error values
- **WHEN** a value is wider than its available field or the card is shown at a narrower supported width
- **THEN** the value wraps or the field layout reflows within the card
- **AND** timestamps and error details remain readable
- **AND** the card does not cause page-level horizontal overflow
