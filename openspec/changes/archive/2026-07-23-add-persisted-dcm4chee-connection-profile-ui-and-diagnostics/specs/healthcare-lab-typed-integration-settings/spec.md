## ADDED Requirements

### Requirement: Typed settings owns dcm4chee bootstrap and projection
Healthcare Lab SHALL register dcm4chee with the shared typed integration-settings boundary, create a profile from eligible `DCM4CHEE_*` compatibility values only when the profile is missing, and expose application-scoped public and private effective projections through the existing redaction and audit contracts.

#### Scenario: Persisted profile already exists
- **WHEN** startup environment values differ from an existing persisted dcm4chee profile
- **THEN** bootstrap leaves the persisted profile unchanged and runtime consumers receive the persisted effective projection

#### Scenario: Missing profile is seeded once
- **WHEN** no persisted dcm4chee profile exists at startup
- **THEN** Healthcare Lab validates and atomically creates one profile from eligible environment values and supported defaults with a value-free bootstrap audit
