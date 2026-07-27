## MODIFIED Requirements

### Requirement: Missing profiles receive one-time bootstrap values

Healthcare Lab SHALL create a missing typed profile from safe local defaults plus any eligible environment-provided runtime and secret values exactly once, SHALL support clean startup when those environment values and optional secret sources are absent, and SHALL treat the persisted profile as authoritative after creation.

#### Scenario: A clean database starts without an env file

- **WHEN** Healthcare Lab initializes a database without a persisted profile, repository-root `.env`, or optional application integration secret variables
- **THEN** deployment rendering and application startup succeed
- **AND** Healthcare Lab validates and atomically seeds any profile that can be represented by safe defaults
- **AND** leaves integrations requiring operator credentials in a secret-safe `needs-setup` state with their secrets reported only as `configured: false`
- **AND** records bootstrap provenance without storing configuration values in audit data

#### Scenario: A legacy environment-backed installation upgrades

- **WHEN** Healthcare Lab initializes a database without a persisted profile and eligible legacy environment values are present
- **THEN** it validates and atomically seeds the profile from those values and safe topology-derived defaults
- **AND** preserves secret values without projecting them into output or diagnostics

#### Scenario: A persisted operator override exists

- **WHEN** Healthcare Lab restarts with a persisted profile and different or absent environment values
- **THEN** it preserves every persisted operator value and secret
- **AND** does not silently reseed, merge, clear, or overwrite the profile

#### Scenario: Bootstrap input is invalid

- **WHEN** an eligible environment value cannot produce a valid typed profile
- **THEN** Healthcare Lab does not partially persist the profile
- **AND** reports a bounded configuration error that contains no secret value
