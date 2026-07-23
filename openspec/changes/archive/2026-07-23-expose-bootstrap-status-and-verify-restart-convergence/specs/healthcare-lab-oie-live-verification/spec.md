## ADDED Requirements

### Requirement: Live OIE verification proves bootstrap convergence

Healthcare Lab SHALL provide repeatable, non-PHI verification against the supported OIE 4.5.2 Docker Compose lab for clean startup, normal restart, partial repair, delayed readiness, and supported local/OIE persistence-reset combinations.

#### Scenario: Clean deployment starts

- **WHEN** the lab starts with clean supported application and OIE persistence
- **THEN** bootstrap creates and starts exactly the two approved managed Channels
- **AND** recorded evidence shows their distinct logical types, identities, deployment state, and successful completion without complete Channel payloads

#### Scenario: Normal restart converges as a no-op

- **WHEN** lab-app and OIE restart with both persistence volumes retained
- **THEN** bootstrap creates no duplicate Channels
- **AND** existing Channel identities and revisions remain unchanged unless OIE itself documents a non-semantic revision change

#### Scenario: One managed Channel is absent

- **WHEN** exactly one approved managed Channel is safely absent while the other remains unchanged
- **THEN** bootstrap repairs only the missing logical type and preserves the existing Channel identity and revision

#### Scenario: OIE readiness is delayed

- **WHEN** lab-app starts before OIE becomes ready but OIE becomes available within the configured timeout
- **THEN** status records multiple readiness attempts and bootstrap converges once

#### Scenario: OIE readiness exceeds the timeout

- **WHEN** OIE remains unavailable beyond the configured timeout
- **THEN** lab-app remains available, status reports a bounded timeout, and an eligible Retry converges after OIE becomes ready

#### Scenario: Supported persistence reset is verified

- **WHEN** the runbook resets only local settings, only OIE appdata, or both according to its safety procedure
- **THEN** bootstrap follows the specified recover-or-create behavior without duplicates or unauthorized adoption
- **AND** the report identifies which persistence target was reset

### Requirement: Live verification is isolated and secret-safe

Live bootstrap verification SHALL resolve and exclusively control the intended Compose project, containers, ports, and volumes, and SHALL record only bounded non-PHI evidence.

#### Scenario: Another lab execution owns shared resources

- **WHEN** the required Compose project, fixed host ports, or target volumes are in active use by another worktree or verification run
- **THEN** the runbook stops before mutation and instructs the operator to obtain exclusive ownership

#### Scenario: Verification evidence is recorded

- **WHEN** a live scenario completes or fails
- **THEN** its report includes versions, timestamps, scenario, bounded outcomes, counts, and safe identity or revision evidence
- **AND** excludes credentials, cookies, exported Channel payloads, HL7 messages, and PHI
