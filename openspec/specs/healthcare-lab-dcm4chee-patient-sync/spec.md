# healthcare-lab-dcm4chee-patient-sync Specification

## Purpose
TBD - created by archiving change implement-dcm4chee-patient-sync-before-dicom-mwl-order-creation. Update Purpose after archive.
## Requirements
### Requirement: Local DICOM Patients sync to dcm4chee through HL7 ADT
Healthcare Lab SHALL sync local DICOM Patient records to the configured dcm4chee archive using the dcm4chee HL7 ADT receiver.

#### Scenario: DICOM Patient creation triggers dcm4chee Patient sync
- **WHEN** Healthcare Lab creates a local Patient in DICOM mode
- **THEN** it creates or updates a dcm4chee Patient sync mapping for that local Patient
- **AND** it sends an HL7 ADT create message to the configured dcm4chee HL7 receiver
- **AND** the ADT Patient identifier uses the same Patient ID and issuer namespace used by dcm4chee MWL payloads
- **AND** the local Patient remains available regardless of dcm4chee sync success or failure

#### Scenario: dcm4chee accepts the Patient sync
- **WHEN** dcm4chee returns an accepted HL7 ACK for the Patient sync message
- **THEN** Healthcare Lab marks the dcm4chee Patient sync status as synced
- **AND** it records the ACK details and sync timestamp

#### Scenario: dcm4chee Patient sync fails
- **WHEN** Healthcare Lab cannot reach dcm4chee or receives a rejected/error ACK
- **THEN** it marks the dcm4chee Patient sync status as failed
- **AND** it records an actionable error type and error text
- **AND** it does not delete or invalidate the local Patient record

### Requirement: dcm4chee Patient sync attempts are auditable
Healthcare Lab SHALL retain dcm4chee Patient sync attempt history separately from dcm4chee MWL attempt history.

#### Scenario: Patient sync attempt is recorded
- **WHEN** Healthcare Lab attempts to sync a Patient to dcm4chee
- **THEN** it records the operation type
- **AND** it records the target endpoint
- **AND** it records the outbound HL7 payload
- **AND** it records the ACK or response details when available
- **AND** it records status, error details, and attempt timestamps

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

