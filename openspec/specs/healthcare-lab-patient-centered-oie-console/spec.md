# healthcare-lab-patient-centered-oie-console Specification

## Purpose
Define the Healthcare Lab OIE console workflow for local ADT patient selection, ORM send/resend, ORU result listener lifecycle, ORU persistence, matching, preview, and ACK handling.
## Requirements
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

Healthcare Lab SHALL show the selected patient's local orders and received results in one workspace, while keeping each Order row independently identifiable.

#### Scenario: User selects a patient

- **WHEN** a user selects a patient from the ADT Patients list
- **THEN** the Selected Patient workspace shows that patient's Orders section
- **AND** it shows that patient's Results section
- **AND** each Order row shows Order ID, MRN, Visit Number, order code, status, and an unambiguous Taipei Order Created At timestamp

#### Scenario: User selects an ADT, ORM, or ORU item

- **WHEN** a user selects an ADT patient row, order row, or result row
- **THEN** the shared HL7 preview updates to the selected ADT, ORM, or ORU raw payload
- **AND** the preview includes a parsed summary when parsing succeeds

#### Scenario: Operator verifies an HL7 Order row

- **WHEN** an operator compares an OIE Order row with its persisted ORM payload
- **THEN** the displayed MRN matches `PID-3`
- **AND** the displayed Visit Number matches `PV1-19`
- **AND** the displayed Order ID matches both `ORC-2` and `OBR-2`

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

Healthcare Lab SHALL provide a local, single-process MLLP result listener for OIE -> lab-app ORU messages, configured only from persisted OIE Settings and controllable through explicit Start, Stop, Retry, and Status APIs.

#### Scenario: Auto-start is enabled

- **WHEN** lab-app starts with persisted listener auto-start enabled
- **THEN** Healthcare Lab attempts once to bind the persisted host and port with the persisted MLLP framing value
- **AND** the default persisted configuration listens on `0.0.0.0:6665`

#### Scenario: Auto-start is disabled

- **WHEN** lab-app starts with persisted listener auto-start disabled
- **THEN** Healthcare Lab leaves the listener stopped without attempting to bind

#### Scenario: Auto-start cannot bind

- **WHEN** the persisted listener endpoint cannot be bound during lab-app startup
- **THEN** Healthcare Lab keeps the web application available
- **AND** listener Status reports `degraded`, the attempted configuration, and an actionable error summary

#### Scenario: User starts the listener

- **WHEN** the user invokes Start while the listener is stopped
- **THEN** Healthcare Lab loads the latest persisted listener Settings and starts listening for result messages
- **AND** the Start API does not accept host, port, or MLLP runtime overrides

#### Scenario: User repeats Start

- **WHEN** Start is invoked repeatedly while the listener is already running with the same persisted configuration
- **THEN** Healthcare Lab returns the existing running status without creating another listener socket or thread

#### Scenario: User retries a degraded listener

- **WHEN** the listener is degraded and the user invokes Retry after correcting the conflict or persisted configuration
- **THEN** Healthcare Lab reloads the latest persisted Settings and attempts to start the listener
- **AND** a successful retry clears the prior error and reports `running`

#### Scenario: User stops the listener

- **WHEN** the listener is running and the user invokes Stop
- **THEN** Healthcare Lab stops accepting new listener connections and reports `stopped`
- **AND** it does not change the persisted auto-start value
- **AND** a later lab-app restart reapplies the persisted auto-start intent

#### Scenario: Runtime settings differ while listener is running

- **WHEN** Start or Retry loads persisted settings that differ from the configuration of an already-running listener
- **THEN** Healthcare Lab rejects the transition with an actionable instruction to Stop before applying the changed configuration

#### Scenario: More than one process attempts ownership

- **WHEN** another lab-app process already owns the configured endpoint
- **THEN** this process reports degraded listener status without preventing its web application from starting

### Requirement: ORU result messages are persisted and acknowledged

Healthcare Lab SHALL idempotently accept, persist, and ACK supported ORU result messages received from OIE using a non-empty HL7 `MSH-10` message-control identifier as the redelivery key.

#### Scenario: Supported ORU is received

- **WHEN** the result listener receives an `ORU^R01` or `ORU^W01` message with a usable `MSH-10`
- **THEN** Healthcare Lab parses and persists the raw ORU payload
- **AND** it returns a successful HL7 ACK only after persistence succeeds

#### Scenario: The same ORU is redelivered

- **WHEN** a supported ORU repeats an already persisted `MSH-10`
- **THEN** Healthcare Lab does not insert another result record
- **AND** returns a successful ACK identifying the delivery as already accepted

#### Scenario: Supported ORU lacks an idempotency key

- **WHEN** a supported ORU has an empty or missing `MSH-10`
- **THEN** Healthcare Lab returns an appropriate failure ACK so OIE can retain the delivery visibly
- **AND** records bounded diagnostic information without a successful result

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
