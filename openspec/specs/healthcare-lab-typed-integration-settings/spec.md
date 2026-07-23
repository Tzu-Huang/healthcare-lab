# healthcare-lab-typed-integration-settings Specification

## Purpose
TBD - created by archiving change establish-unified-typed-configuration-ownership. Update Purpose after archive.
## Requirements
### Requirement: Every supported configuration key has one documented owner

Healthcare Lab SHALL publish a configuration ownership matrix covering Medplum, OIE, GDT, dcm4chee, OpenEMR, AP-facing integration routes, and supported Docker deployment settings, and SHALL classify each current key as exactly one of deployment-only, runtime persisted, secret, or derived/default.

#### Scenario: Configuration ownership is inspected

- **WHEN** an operator or developer consults the configuration ownership matrix
- **THEN** every current configuration key identifies one owner, its source, whether it can be changed at runtime, its restart or activation behavior, and its environment-bootstrap behavior
- **AND** no key is classified under more than one ownership category

#### Scenario: Deployment-only configuration is evaluated

- **WHEN** a key controls an image, host-published port, Docker network, volume, bind mount, or Docker socket
- **THEN** the matrix classifies it as deployment-only
- **AND** the persisted settings boundary does not claim to apply or own that key

### Requirement: Persisted settings use integration-specific typed profiles

Healthcare Lab SHALL persist runtime settings through named integration-specific profile schemas with explicit field types and validators and MUST NOT expose an arbitrary untyped key-value persistence interface.

#### Scenario: A typed profile is saved

- **WHEN** a caller submits a complete valid integration profile mutation
- **THEN** Healthcare Lab validates the profile against that integration's schema and atomically persists all accepted fields
- **AND** a consumer can load the typed profile without reading raw SQL

#### Scenario: Any profile field is invalid

- **WHEN** one or more submitted fields fail type, range, identity, URL, or integration-specific validation
- **THEN** Healthcare Lab rejects the entire mutation with stable field-level error entries
- **AND** it leaves the previously persisted profile and secrets unchanged

#### Scenario: An unknown field or profile type is submitted

- **WHEN** a caller submits a field or profile type outside the registered typed contract
- **THEN** Healthcare Lab rejects it instead of storing arbitrary configuration

### Requirement: Missing profiles receive one-time bootstrap values

Healthcare Lab SHALL create a missing typed profile from safe local defaults plus eligible environment-provided runtime and secret values exactly once, and SHALL treat the persisted profile as authoritative after creation.

#### Scenario: A clean database starts

- **WHEN** Healthcare Lab initializes a database without a persisted profile for an integration
- **THEN** it validates and atomically seeds the profile from supported environment values and safe topology-derived defaults
- **AND** records bootstrap provenance without storing configuration values in audit data

#### Scenario: A persisted operator override exists

- **WHEN** Healthcare Lab restarts with a persisted profile and different environment values
- **THEN** it preserves every persisted operator value and secret
- **AND** does not silently reseed or overwrite the profile

#### Scenario: Bootstrap input is invalid

- **WHEN** an eligible environment value cannot produce a valid typed profile
- **THEN** Healthcare Lab does not partially persist the profile
- **AND** reports a bounded configuration error that contains no secret value

### Requirement: Secrets have write-only preserve replace and remove semantics

Healthcare Lab MUST keep persisted secret values out of public responses, logs, exceptions, diagnostics, and audit payloads, and SHALL distinguish preserve, replace, and explicit removal operations.

#### Scenario: A profile with a secret is read

- **WHEN** a caller reads a public typed profile
- **THEN** each secret field is represented only by `configured: true` or `configured: false`
- **AND** the response contains neither the secret value nor a masked placeholder derived from it

#### Scenario: A blank or omitted secret replacement is submitted

- **WHEN** a valid profile mutation omits a secret replacement or supplies it as blank
- **THEN** Healthcare Lab preserves the currently stored secret

#### Scenario: A non-blank secret replacement is submitted

- **WHEN** a valid profile mutation supplies a non-blank replacement secret
- **THEN** Healthcare Lab atomically stores the replacement with the other profile changes
- **AND** returns only its configured state

#### Scenario: Explicit secret removal is requested

- **WHEN** a caller invokes the distinct removal operation for a configured secret
- **THEN** Healthcare Lab removes that secret and reports `configured: false`
- **AND** does not interpret an ordinary blank replacement as removal

### Requirement: Runtime consumers read effective configuration outside request context

Healthcare Lab SHALL provide application-composed effective-settings readers that resolve persisted typed profiles and safe derived defaults without depending on Flask request state, direct environment access, or raw SQL at the consumer.

#### Scenario: A background runtime consumer starts

- **WHEN** a listener, watcher, startup coordinator, health check, or workflow service requests integration configuration outside an HTTP request
- **THEN** it receives the same effective typed configuration used by API-triggered workflows

#### Scenario: A migrated persisted setting changes

- **WHEN** an operator commits a valid runtime-persisted setting change
- **THEN** subsequent consumer reads use the persisted value according to its documented activation behavior
- **AND** do not fall back to a competing environment value

### Requirement: Typed settings APIs return stable secret-safe projections and errors

Healthcare Lab SHALL project typed profiles through stable response envelopes and SHALL return bounded machine-readable validation errors without echoing submitted values.

#### Scenario: A public profile is returned

- **WHEN** a settings API successfully reads or mutates a typed profile
- **THEN** the response identifies the profile type and returns its typed non-secret fields and secret configured states

#### Scenario: Validation fails at the API boundary

- **WHEN** a settings API receives invalid profile data
- **THEN** it returns a stable error code and a list of field paths with bounded reasons
- **AND** it does not include submitted values, credentials, tokens, private-key material, or upstream payloads

### Requirement: Settings mutations produce atomic value-free audits

Healthcare Lab SHALL append a settings mutation audit in the same local transaction as each successful bootstrap, update, or secret removal and MUST restrict audit content to an explicit metadata allowlist.

#### Scenario: A profile mutation succeeds

- **WHEN** a typed profile mutation commits
- **THEN** its audit records profile type and identity, actor, operation, allowlisted changed field names, outcome, and timestamp
- **AND** contains no old value, new value, secret, PHI, full request payload, or arbitrary upstream body

#### Scenario: Persistence or audit insertion fails

- **WHEN** either the profile write or required audit insertion fails
- **THEN** Healthcare Lab rolls back both operations and preserves the prior profile

#### Scenario: Validation fails before persistence

- **WHEN** a typed profile mutation is rejected during validation
- **THEN** no successful mutation audit is recorded

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

