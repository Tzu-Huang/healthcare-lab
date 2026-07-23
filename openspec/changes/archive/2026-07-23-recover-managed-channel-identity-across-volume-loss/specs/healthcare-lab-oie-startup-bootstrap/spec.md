## ADDED Requirements

### Requirement: Startup bootstrap recovers asymmetric persistence loss

Healthcare Lab SHALL reconcile the two canonical managed Channel identities across independently retained or reset local settings and OIE appdata, and SHALL converge idempotently without duplicating managed Channels.

#### Scenario: Both persistence volumes are retained

- **WHEN** local mappings and their exact live OIE Channels are retained
- **THEN** bootstrap performs no mapping or OIE Channel mutation

#### Scenario: Only OIE appdata is reset

- **WHEN** a retained mapping identifies a Channel absent from the complete live OIE inventory
- **THEN** bootstrap creates, binds, deploys, and verifies exactly that missing approved Channel

#### Scenario: Only local settings are reset

- **WHEN** a canonical mapping has empty identity and exactly one valid recoverable live Channel exists for its logical type
- **THEN** bootstrap atomically rebinds that Channel without creating, updating, or changing its deployment state

#### Scenario: Both persistence volumes are reset

- **WHEN** canonical mapping intent exists with empty identities and neither managed Channel exists in OIE
- **THEN** bootstrap creates, binds, deploys, and verifies exactly two new managed Channels

#### Scenario: Recovery is repeated

- **WHEN** bootstrap runs again after successful creation or rebinding
- **THEN** it performs no further mapping or OIE Channel mutation

### Requirement: Startup recovery is independently bounded and auditable

Healthcare Lab SHALL process recovery per logical type and SHALL record bounded secret- and PHI-safe evidence for successful, blocked, stale, and failed recovery outcomes.

#### Scenario: One logical type is blocked

- **WHEN** recovery evidence for one managed logical type is unsafe but the other logical type can be reconciled safely
- **THEN** bootstrap blocks the unsafe type and continues bounded reconciliation for the safe type

#### Scenario: Recovery evidence is recorded

- **WHEN** bootstrap rebinds or blocks rebinding a managed Channel
- **THEN** durable evidence identifies actor `startup-bootstrap`, logical type, bounded outcome, Channel identity when safely known, revision, and safe error category without credentials, complete payloads, HL7, or PHI
