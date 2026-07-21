## MODIFIED Requirements

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
