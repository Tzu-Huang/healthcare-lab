## ADDED Requirements

### Requirement: dcm4chee MWL sync exposes retry and attempt APIs
Healthcare Lab SHALL expose explicit backend APIs that allow clients to retry dcm4chee MWL sync for a local Healthcare Lab order and inspect the dcm4chee sync attempt history for that order.

#### Scenario: Client retries a failed dcm4chee MWL sync
- **GIVEN** a local Healthcare Lab dcm4chee order has a failed or pending dcm4chee MWL sync state
- **WHEN** a client requests dcm4chee sync retry for that order
- **THEN** Healthcare Lab invokes the dcm4chee MWL sync workflow for the existing local order
- **AND** the retry reuses the canonical PACS/MWL mapping identifiers for that order
- **AND** the response includes the updated local order, latest dcm4chee mapping, latest attempt, and retryable metadata

#### Scenario: Retry does not duplicate confirmed dcm4chee orders
- **GIVEN** a local Healthcare Lab dcm4chee order already has a successful canonical PACS/MWL mapping
- **WHEN** a client requests dcm4chee sync retry for that order
- **THEN** Healthcare Lab does not POST a duplicate dcm4chee MWL item
- **AND** it returns the current successful mapping and order state

#### Scenario: Client inspects dcm4chee sync attempts
- **GIVEN** a local Healthcare Lab order has one or more dcm4chee MWL sync attempts
- **WHEN** a client requests the dcm4chee attempt history for that order
- **THEN** Healthcare Lab returns the attempts in a deterministic newest-first order
- **AND** each attempt includes operation type, status, request target, HTTP status when available, timestamps, error details, and retained response payload when available

### Requirement: dcm4chee MWL sync status is inspectable and action-oriented
Healthcare Lab SHALL expose dcm4chee MWL status metadata that is suitable for user inspection and retry decisions while preserving stored ledger status compatibility.

#### Scenario: Failed dcm4chee sync is visible and inspectable
- **GIVEN** dcm4chee MWL creation, read-back, or retry fails
- **WHEN** a client reads the local order or dcm4chee attempt history
- **THEN** Healthcare Lab exposes the current sync status
- **AND** it exposes the latest error type, error text, HTTP status, response payload, retry count, and relevant timestamps when available
- **AND** the local Healthcare Lab order remains available

#### Scenario: Retryable status is explicit
- **GIVEN** a dcm4chee MWL sync state can be retried
- **WHEN** a client reads the local order status
- **THEN** Healthcare Lab marks the dcm4chee MWL status as retryable
- **AND** it provides display-oriented status metadata that can be rendered as pending, synced, failed, retry needed, or reconciled without requiring clients to parse raw error text

#### Scenario: Non-retryable status remains explicit
- **GIVEN** dcm4chee MWL sync fails because of a patient precondition or invalid local/profile configuration
- **WHEN** a client reads the local order status
- **THEN** Healthcare Lab exposes the failure reason and retained diagnostics
- **AND** it does not present the state as retryable unless the local/profile data changes or the backend can safely retry the same request

### Requirement: DICOM order workspace supports dcm4chee retry and inspection
Healthcare Lab SHALL let users retry and inspect dcm4chee MWL sync from the DICOM order workspace.

#### Scenario: Retry action is shown for retryable dcm4chee orders
- **GIVEN** a DICOM MWL order has retryable dcm4chee sync metadata
- **WHEN** the order appears in the DICOM order list
- **THEN** the UI shows a retry action for that order
- **AND** activating the action calls the dcm4chee retry API
- **AND** the UI refreshes the order status after the retry completes

#### Scenario: User inspects latest sync details
- **GIVEN** a user selects a DICOM MWL order
- **WHEN** the order has dcm4chee MWL mapping or attempt metadata
- **THEN** the UI shows the latest dcm4chee sync status, retry count, timestamps, key identifiers, HTTP status, and latest error details when available

#### Scenario: User inspects attempt history
- **GIVEN** a user selects a DICOM MWL order
- **WHEN** dcm4chee attempt history is available
- **THEN** the UI shows each attempt with operation type, status, request target, HTTP status, timestamps, error details, and retained response payload when available
