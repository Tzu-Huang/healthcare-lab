## MODIFIED Requirements

### Requirement: Missing profiles receive one-time bootstrap values

Healthcare Lab SHALL create a missing typed profile from safe local defaults plus any eligible environment-provided runtime and secret values exactly once, SHALL support clean startup when those environment values are absent, and SHALL treat the persisted profile as authoritative after creation.

#### Scenario: A clean database starts without an env file

- **WHEN** Healthcare Lab initializes a database without a persisted profile or repository-root `.env`
- **THEN** it validates and atomically seeds any profile that can be represented by safe defaults
- **AND** leaves integrations requiring operator credentials in a secret-safe `needs-setup` state
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

## ADDED Requirements

### Requirement: Advanced deployment overrides remain separate from application Settings

Healthcare Lab SHALL keep image selection, host publications, bind mounts, container database credentials, and deployment security hardening outside typed application Settings, while legacy application environment values remain eligible only for documented one-time bootstrap.

#### Scenario: Operator changes a deployment-only override

- **WHEN** an operator changes an image, host port, bind mount, or service database setting
- **THEN** the change takes effect only through its documented Compose activation behavior
- **AND** the web application does not write, persist, or apply that deployment value

#### Scenario: Operator saves application settings

- **WHEN** an operator saves a valid Medplum, OIE, GDT Bridge, dcm4chee, or AP profile through Settings
- **THEN** persisted typed configuration becomes authoritative according to its activation contract
- **AND** later container recreation does not require copying that value back into `.env`
