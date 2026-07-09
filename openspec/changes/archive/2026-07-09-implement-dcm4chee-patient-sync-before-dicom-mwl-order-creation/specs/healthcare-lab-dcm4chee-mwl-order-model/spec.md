## MODIFIED Requirements

### Requirement: Patient precondition failures are explicit
Healthcare Lab SHALL ensure the referenced Patient exists in dcm4chee before creating a dcm4chee MWL item, or clearly report that the Patient precondition failed.

#### Scenario: Patient is synced before MWL create
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **WHEN** the referenced local Patient is already synced to dcm4chee
- **THEN** Healthcare Lab may POST the MWL item to dcm4chee
- **AND** it records normal MWL create, read-back, and verification diagnostics

#### Scenario: Patient preflight sync succeeds
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **AND** the referenced local Patient is not yet synced to dcm4chee
- **WHEN** Healthcare Lab successfully syncs the Patient during MWL preflight
- **THEN** it may POST the MWL item to dcm4chee
- **AND** it records both the Patient sync attempt and the MWL create attempt

#### Scenario: Patient precondition fails
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **WHEN** the referenced Patient cannot be confirmed or synced in dcm4chee
- **THEN** Healthcare Lab does not POST the MWL item
- **AND** the local order remains available
- **AND** the MWL sync state identifies Patient sync or Patient missing as the root cause
- **AND** later MWL verification does not replace the Patient precondition failure with an empty-query diagnosis
