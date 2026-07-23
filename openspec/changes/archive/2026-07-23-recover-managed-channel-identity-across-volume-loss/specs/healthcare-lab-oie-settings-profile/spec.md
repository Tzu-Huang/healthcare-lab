## ADDED Requirements

### Requirement: Managed Channel recovery binds one empty identity atomically

Healthcare Lab SHALL compare and bind one canonical managed Channel mapping in a single transaction only when its persisted identity is still empty and the supplied live identity has passed guarded recovery validation. The operation SHALL preserve unrelated profile fields and mappings.

#### Scenario: Empty mapping is rebound

- **WHEN** guarded recovery supplies a validated Channel ID, canonical name, template version, and revision for a mapping whose identity remains empty
- **THEN** the repository persists those identity fields and the bounded recovery audit event atomically

#### Scenario: Mapping changed concurrently

- **WHEN** the mapping identity no longer matches the expected empty prior state
- **THEN** the repository rejects the bind without changing settings, mappings, or audit history

#### Scenario: Rebinding is repeated

- **WHEN** the same recovery bind is attempted after identity has already been persisted
- **THEN** the repository performs no duplicate or replacement write and reports the stale expected state
