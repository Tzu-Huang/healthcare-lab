## ADDED Requirements

### Requirement: OIE console is patient-centered

Healthcare Lab SHALL present the OIE page around selected local ADT patients instead of a topbar protocol mode selector.

#### Scenario: User opens the OIE page

- **WHEN** the OIE page loads
- **THEN** it does not show the previous topbar mode selector
- **AND** it shows an ADT Patients list
- **AND** it shows a Selected Patient workspace
- **AND** it shows a shared HL7 preview area

#### Scenario: Patient list is displayed

- **WHEN** local ADT patients exist
- **THEN** each patient row shows MRN, name, created time, order count, and result count
- **AND** created time is displayed as an unambiguous Taipei-time timestamp

### Requirement: Selected patient workspace shows orders and results

Healthcare Lab SHALL show the selected patient's local orders and received results in one workspace.

#### Scenario: User selects a patient

- **WHEN** a user selects a patient from the ADT Patients list
- **THEN** the Selected Patient workspace shows that patient's Orders section
- **AND** it shows that patient's Results section

#### Scenario: User selects an ADT, ORM, or ORU item

- **WHEN** a user selects an ADT patient row, order row, or result row
- **THEN** the shared HL7 preview updates to the selected ADT, ORM, or ORU raw payload
- **AND** the preview includes a parsed summary when parsing succeeds

### Requirement: Orders can be sent from the patient workspace

Healthcare Lab SHALL allow ORM send and resend actions from the selected patient's Orders section.

#### Scenario: User sends an order

- **WHEN** a user sends an ORM from the selected patient's Orders section
- **THEN** Healthcare Lab sends the selected order payload to the configured OIE endpoint
- **AND** it updates the order row with send status, ACK code when available, and sent time

#### Scenario: User previews an order

- **WHEN** a user previews an order
- **THEN** the shared HL7 preview displays the persisted ORM payload for that order

### Requirement: Lab app receives OIE-routed ORU results

Healthcare Lab SHALL provide a local MLLP result listener for OIE -> lab-app ORU messages.

#### Scenario: User starts the listener

- **WHEN** the listener is configured with host, port, and MLLP framing
- **AND** the user starts the listener
- **THEN** Healthcare Lab starts listening for result messages
- **AND** the default port is `6665`
- **AND** the UI can display listener status

#### Scenario: User stops the listener

- **WHEN** the listener is running
- **AND** the user stops the listener
- **THEN** Healthcare Lab stops accepting new listener connections
- **AND** the UI can display stopped status

### Requirement: ORU result messages are persisted and acknowledged

Healthcare Lab SHALL accept, persist, and ACK supported ORU result messages received from OIE.

#### Scenario: Supported ORU is received

- **WHEN** the result listener receives an `ORU^R01` or `ORU^W01` message
- **THEN** Healthcare Lab parses and persists the raw ORU payload
- **AND** it returns a successful HL7 ACK after persistence succeeds

#### Scenario: Unsupported or invalid message is received

- **WHEN** the result listener receives an unsupported message type or an invalid HL7 payload
- **THEN** Healthcare Lab returns an appropriate failure ACK
- **AND** it records diagnostic information without fabricating a successful result

### Requirement: ORU messages are matched to patients and orders

Healthcare Lab SHALL match received ORU messages to local patients and orders when possible.

#### Scenario: ORU matches a local order by placer order number

- **WHEN** an ORU contains `PID-3` matching a local patient
- **AND** `OBR-2` matches a local ORM order identifier for that patient
- **THEN** the result is listed under the matched patient and matched order

#### Scenario: ORU matches a local order by filler order number

- **WHEN** an ORU contains `PID-3` matching a local patient
- **AND** `OBR-3` matches a known local order identifier for that patient
- **THEN** the result is listed under the matched patient and matched order

#### Scenario: ORU matches only a patient

- **WHEN** an ORU contains `PID-3` matching a local patient
- **AND** no local order identifier matches
- **THEN** the result remains visible under that patient as an unmatched-order result

#### Scenario: ORU cannot be matched to a patient

- **WHEN** an ORU lacks a known `PID-3`
- **THEN** the result remains visible in an Unmatched Results area

### Requirement: Unmatched results remain visible

Healthcare Lab SHALL keep unmatchable ORU messages visible for review.

#### Scenario: User reviews unmatched results

- **WHEN** unmatched ORU messages exist
- **THEN** the OIE page shows an Unmatched Results area
- **AND** selecting an unmatched result displays its raw ORU payload in the shared preview

