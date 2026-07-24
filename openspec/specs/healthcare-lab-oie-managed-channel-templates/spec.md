# healthcare-lab-oie-managed-channel-templates Specification

## Purpose
TBD - created by archiving change define-managed-hlab-channel-templates. Update Purpose after archive.
## Requirements
### Requirement: Healthcare Lab compiles two constrained managed OIE Channels

Healthcare Lab SHALL compile complete OIE 4.5.2 Channel payloads for exactly `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB` without exposing arbitrary connector, destination, filter, transformer, script, or raw payload editing.

#### Scenario: Compile the ORM route

- **WHEN** a caller supplies a valid private-network AP host and otherwise accepts defaults
- **THEN** `HLAB_ORM_TO_AP` listens on `0.0.0.0:6600`
- **AND** it sends HL7 v2 over MLLP with UTF-8 encoding to that host on port `6671`
- **AND** its complete payload matches the sanitized OIE 4.5.2 canonical structure

#### Scenario: Compile the ORU route

- **WHEN** a caller compiles the default result route
- **THEN** `HLAB_ORU_TO_HLAB` listens on `0.0.0.0:6661`
- **AND** it sends HL7 v2 over MLLP with UTF-8 encoding to `lab-app:6665`
- **AND** its complete payload matches the sanitized OIE 4.5.2 canonical structure

#### Scenario: Reject an unsupported extension

- **WHEN** a caller attempts to add an arbitrary destination, connector type, filter, transformer, script, or raw payload field
- **THEN** the constrained template interface does not accept that input

### Requirement: Managed templates have stable logical identity

Each template SHALL include a stable logical type, template version `1`, and a machine-readable `Managed by Healthcare Lab` marker independently of its OIE Channel ID or revision.

#### Scenario: Identify an uncreated managed Channel

- **WHEN** a template is compiled before it has been created in OIE
- **THEN** its logical identity and ownership marker are complete without an OIE Channel ID

#### Scenario: A display name is not sufficient ownership evidence

- **WHEN** an external Channel has the same display name but lacks the expected logical type and managed marker
- **THEN** it is not classified as a Healthcare Lab-managed Channel

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

### Requirement: Template inputs are validated before OIE transport

Healthcare Lab SHALL reject invalid hosts, ports, timeouts, booleans, states, and conflicting listener ports through a persistence- and transport-neutral validation boundary.

#### Scenario: Accept common private-network host forms

- **WHEN** an AP host is a valid IPv4 address or internal DNS hostname without a scheme, path, credentials, or embedded port
- **THEN** the ORM template accepts it

#### Scenario: Reject an invalid endpoint

- **WHEN** a host is empty or contains a URL scheme, path, credentials, or embedded port, or a port is outside `1-65535`
- **THEN** compilation fails with an actionable field-specific validation error before any OIE call

#### Scenario: Reject conflicting listener ports

- **WHEN** route overrides assign both managed Channels the same listener port
- **THEN** managed route-set validation rejects the conflict before any OIE call

### Requirement: Normalized desired state is deterministic and secret-free

Healthcare Lab SHALL project each template into a deterministic normalized representation containing only Healthcare Lab-owned identity, endpoint, protocol, charset, timeout, queue, enabled, and initial-state values.

#### Scenario: Ignore OIE-managed metadata during normalization

- **WHEN** two otherwise equivalent Channel payloads have different OIE IDs, revisions, export timestamps, or user IDs
- **THEN** their normalized desired states are equal

#### Scenario: Detect an owned-field change

- **WHEN** an approved destination, timeout, queue, enabled, or initial-state value changes
- **THEN** normalized comparison identifies the exact changed owned field

#### Scenario: Keep credentials out of template output

- **WHEN** a template payload, normalized state, validation error, or object representation is inspected
- **THEN** it contains no Management API username, password, cookie, authorization value, or credential-bearing URL
