## ADDED Requirements

### Requirement: Healthcare Lab creates dcm4chee MWL orders through MWL REST
Healthcare Lab SHALL create dcm4chee MWL/order records from Healthcare Lab ECG orders using the selected dcm4chee connection profile and the dcm4chee MWL REST creation path.

#### Scenario: Order creation posts a MWL item to dcm4chee
- **GIVEN** the selected dcm4chee profile is valid
- **AND** the Healthcare Lab order contains required patient and order data
- **WHEN** Healthcare Lab creates the dcm4chee MWL/order
- **THEN** it sends an `application/dicom+json` request to `POST /dcm4chee-arc/aets/{AETitle}/rs/mwlitems`
- **AND** `{AETitle}` is derived from the selected dcm4chee profile
- **AND** the request does not depend on manual dcm4chee UI entry

### Requirement: dcm4chee MWL creation records audit metadata
Healthcare Lab SHALL retain enough local metadata to debug and reconcile every dcm4chee MWL creation attempt.

#### Scenario: Creation attempt is recorded
- **WHEN** Healthcare Lab attempts to create a dcm4chee MWL/order
- **THEN** it records the local Healthcare Lab order identity
- **AND** it records the selected dcm4chee profile name and server identity
- **AND** it records generated Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, and Study Instance UID
- **AND** it records the outbound DICOM JSON request payload
- **AND** it records the dcm4chee response status, response body, attempt status, timestamps, and error details when available

### Requirement: dcm4chee MWL creation preserves local orders on failure
Healthcare Lab SHALL keep the local Healthcare Lab order even when dcm4chee MWL creation fails.

#### Scenario: dcm4chee creation fails after local order creation
- **GIVEN** Healthcare Lab has created a local order
- **WHEN** the dcm4chee MWL creation attempt fails
- **THEN** the local order remains available in Healthcare Lab
- **AND** the dcm4chee sync state is marked failed or pending separately from the local order
- **AND** the failure reason is visible through backend response metadata or a related status endpoint

### Requirement: Patient precondition failures are explicit
Healthcare Lab SHALL distinguish dcm4chee patient precondition failures from generic MWL creation failures.

#### Scenario: dcm4chee rejects MWL creation because the patient is missing
- **GIVEN** the dcm4chee MWL REST endpoint rejects the request because the patient does not exist
- **WHEN** Healthcare Lab records the creation attempt
- **THEN** the attempt status identifies the missing-patient or patient-precondition failure
- **AND** the dcm4chee response body is retained for debugging
- **AND** the local Healthcare Lab order is not deleted

### Requirement: Study Instance UID generation is configurable at runtime
Healthcare Lab SHALL generate valid DICOM Study Instance UIDs for dcm4chee MWL orders using a configured UID root.

#### Scenario: Runtime generates a Study Instance UID
- **WHEN** Healthcare Lab creates a dcm4chee MWL/order
- **THEN** it generates `0020000D Study Instance UID` using a configured dcm4chee UID root plus a unique suffix
- **AND** the generated UID is included in the MWL REST payload
- **AND** the generated UID is recorded in the local dcm4chee mapping/audit metadata
