## ADDED Requirements

### Requirement: dcm4chee MWL queryability is explicitly verifiable
Healthcare Lab SHALL provide an explicit verification path that proves whether a Healthcare Lab-created dcm4chee MWL order is queryable from the configured dcm4chee MWL surface.

#### Scenario: Client verifies a dcm4chee MWL order
- **GIVEN** a local Healthcare Lab DICOM MWL order has a canonical PACS/MWL mapping
- **WHEN** a client requests MWL queryability verification for that order
- **THEN** Healthcare Lab queries the configured dcm4chee MWL endpoint using identifiers from the canonical mapping
- **AND** Healthcare Lab records a verification attempt separate from create, read-back, and retry attempts
- **AND** the local Healthcare Lab order remains available regardless of verification outcome

#### Scenario: Verification uses the configured MWL application
- **GIVEN** the selected dcm4chee profile exposes a MWL AE title and DICOMweb/MWL REST base URL
- **WHEN** Healthcare Lab runs automated MWL verification
- **THEN** it uses the configured MWL REST target for MWL item queries
- **AND** the local Docker profile can target the dcm4chee `WORKLIST` MWL web application
- **AND** profile or endpoint failures are reported as verification diagnostics rather than generic sync failures

### Requirement: MWL verification records proof metadata
Healthcare Lab SHALL retain enough metadata to prove which dcm4chee MWL item was found during verification.

#### Scenario: Verification finds the expected order
- **GIVEN** dcm4chee returns one or more MWL items for the verification query
- **WHEN** Healthcare Lab identifies an item matching the local order by strong identifiers
- **THEN** Healthcare Lab records verification status as verified
- **AND** it records the verification method, request target, query criteria, HTTP or tool status, verification timestamp, and selected match metadata
- **AND** the proof metadata includes available Patient ID, Issuer of Patient ID, Accession Number, Scheduled Station AE Title, Scheduled Procedure Step ID, Requested Procedure ID, Study Instance UID, and Worklist Label

#### Scenario: Verification response is non-empty but mismatched
- **GIVEN** dcm4chee returns MWL items for the verification query
- **WHEN** no returned item matches the expected local order identifiers strongly enough
- **THEN** Healthcare Lab records verification failure as an identifier mismatch
- **AND** it retains enough returned metadata to explain which fields did not match

#### Scenario: Verification response is ambiguous
- **GIVEN** dcm4chee returns multiple MWL items that match only weak criteria
- **WHEN** Healthcare Lab cannot identify exactly one expected order
- **THEN** Healthcare Lab records the result as ambiguous
- **AND** it does not mark the order as verified

### Requirement: MWL verification diagnostics are actionable
Healthcare Lab SHALL classify MWL verification failures into operator-actionable diagnostics.

#### Scenario: dcm4chee cannot be reached
- **GIVEN** the configured dcm4chee MWL endpoint is unavailable
- **WHEN** Healthcare Lab runs MWL verification
- **THEN** it records a dcm4chee connectivity diagnostic
- **AND** it preserves the request target and error detail needed to troubleshoot networking or service startup

#### Scenario: dcm4chee patient precondition is missing
- **GIVEN** dcm4chee indicates the MWL order cannot be created or queried because the referenced patient does not exist
- **WHEN** Healthcare Lab records verification or sync status
- **THEN** the diagnostic identifies the missing patient precondition
- **AND** the state is not presented as retryable unless patient data changes or patient creation/sync is completed

#### Scenario: MWL query returns no matching order
- **GIVEN** the configured dcm4chee MWL endpoint is reachable
- **WHEN** Healthcare Lab runs MWL verification and no MWL item is returned for the expected identifiers
- **THEN** it records an empty-result diagnostic
- **AND** it includes the query criteria and endpoint used for troubleshooting
