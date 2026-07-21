## MODIFIED Requirements

### Requirement: The ORU destination survives temporary lab-app downtime

The canonical and compiled `HLAB_ORU_TO_HLAB` destination definitions SHALL enable OIE queueing, retry indefinitely at 10-second intervals, retain a queue buffer of 1000, queue connection and response-timeout delivery failures, use 5000 ms send and response timeouts, and validate HL7 ACK outcomes before considering delivery successful.

#### Scenario: Render resilient ORU delivery settings

- **WHEN** the canonical ORU export is imported or the ORU template is compiled
- **THEN** its destination queue is enabled with the required retry, buffer, timeout, MLLP, and ACK-validation values

#### Scenario: lab-app is temporarily unavailable

- **WHEN** OIE accepts an AP ORU but cannot connect to `lab-app:6665` or times out awaiting its ACK
- **THEN** the destination retains the message as queued or retryable rather than discarding it
- **AND** delivery is retried after lab-app returns

#### Scenario: Keep ORM queue behavior outside the ORU guarantee

- **WHEN** the default ORM template is compiled
- **THEN** its destination queue remains disabled
