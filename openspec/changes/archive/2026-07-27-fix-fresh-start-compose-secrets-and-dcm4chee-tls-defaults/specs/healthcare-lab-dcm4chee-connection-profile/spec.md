## MODIFIED Requirements

### Requirement: dcm4chee profile includes explicit security settings
Healthcare Lab SHALL include internally valid auth and TLS settings in the dcm4chee profile even when the local lab profile runs without auth or TLS.

#### Scenario: Local profile declares no auth or TLS
- **WHEN** Healthcare Lab loads or bootstraps the local dcm4chee profile
- **THEN** the profile includes auth mode `none`
- **AND** the profile includes TLS enabled `false`
- **AND** the profile includes TLS verification `false`
- **AND** the profile includes empty placeholders for future credential, token, certificate, and key settings
- **AND** the profile passes typed validation without an operator override
- **AND** Healthcare Lab does not imply that the local unauthenticated profile is production-ready

#### Scenario: Contradictory TLS values are supplied explicitly
- **WHEN** an advanced bootstrap or Settings mutation supplies TLS enabled `false` with TLS verification `true`
- **THEN** typed validation rejects the contradictory profile with a stable field-level error
- **AND** no partial profile is persisted
