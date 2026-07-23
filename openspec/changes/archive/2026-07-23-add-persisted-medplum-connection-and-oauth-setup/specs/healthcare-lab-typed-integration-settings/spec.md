## ADDED Requirements

### Requirement: Medplum compatibility surfaces derive from typed settings
Healthcare Lab SHALL treat the typed Medplum profile as the canonical owner for application connection decisions while retaining Lab Server inventory only as a compatible presentation and deployment-control surface.

#### Scenario: Medplum inventory is displayed
- **WHEN** a caller reads Lab Server inventory or browser navigation data for Medplum
- **THEN** application-facing and browser-facing connection values are derived from or linked to the canonical profile
- **AND** inventory does not become a second writable owner

#### Scenario: Medplum health or smoke runs
- **WHEN** a health or smoke operation evaluates Medplum
- **THEN** it receives enabled state, internal FHIR URL, OAuth configuration, and timeout from the effective typed profile
- **AND** it does not select a hard-coded or independently persisted application URL

### Requirement: Medplum profile evolution preserves persisted authority
Healthcare Lab SHALL migrate existing persisted Medplum profiles to the expanded schema deterministically and SHALL migrate eligible legacy environment values only during first profile creation.

#### Scenario: Existing profile predates new fields
- **WHEN** Healthcare Lab starts with an older valid persisted Medplum profile
- **THEN** it adds safe values for newly required fields through an idempotent profile migration
- **AND** preserves all existing public fields and secrets

#### Scenario: Environment changes after bootstrap
- **WHEN** an expanded persisted profile already exists and eligible Medplum environment values change
- **THEN** Healthcare Lab retains the persisted profile unchanged
- **AND** records no new bootstrap mutation
