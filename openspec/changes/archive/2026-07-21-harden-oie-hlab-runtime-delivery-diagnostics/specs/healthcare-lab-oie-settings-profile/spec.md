## ADDED Requirements

### Requirement: Runtime port settings have unambiguous ownership

Healthcare Lab SHALL distinguish OIE container listener ports, HLAB container listener ports, Management API ports, and host-published ports so one setting does not configure two different delivery endpoints.

#### Scenario: Default Docker delivery contract is inspected
- **WHEN** the default managed runtime is configured
- **THEN** HLAB-to-OIE uses OIE container port `6600`, AP-to-OIE uses OIE container port `6661`, and OIE-to-HLAB uses `lab-app:6665`
- **AND** host-published ports are represented separately from those container endpoints

#### Scenario: A host-published port changes
- **WHEN** an operator changes a Compose host-published port
- **THEN** Healthcare Lab identifies that container recreation is required
- **AND** does not imply that Channel redeploy alone applies the mapping

### Requirement: Settings mutations are audited safely

Healthcare Lab SHALL append a bounded Settings audit record in the same local transaction as each successful profile mutation and MUST NOT store setting values, credentials, PHI, or complete payloads in that audit.

#### Scenario: Settings are updated
- **WHEN** a valid OIE Settings mutation commits
- **THEN** its audit records actor, operation, changed approved field paths, outcome, and timestamp
- **AND** contains neither old nor new field values

#### Scenario: Settings validation fails
- **WHEN** an invalid Settings mutation is rejected before persistence
- **THEN** the prior profile remains unchanged
- **AND** no successful mutation audit is recorded
