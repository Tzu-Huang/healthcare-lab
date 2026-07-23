## ADDED Requirements

### Requirement: Settings aggregates dcm4chee-owned readiness and diagnostics
Healthcare Lab SHALL register the dcm4chee module's readiness and bounded diagnostic providers with the Settings workspace without moving dcm4chee-specific validation or protocol logic into the shell.

#### Scenario: Enabled profile is healthy
- **WHEN** the persisted dcm4chee profile is valid and all required bounded checks pass
- **THEN** Settings Overview reports dcm4chee as `ready` with secret-safe explanatory metadata

#### Scenario: Enabled profile has partial connectivity
- **WHEN** the persisted dcm4chee profile is valid and one or more independent checks fail
- **THEN** Settings Overview reports dcm4chee as `degraded` and Run all checks preserves each bounded partial result
