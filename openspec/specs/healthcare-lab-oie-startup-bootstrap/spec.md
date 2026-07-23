# healthcare-lab-oie-startup-bootstrap Specification

## Purpose
TBD - created by archiving change provision-missing-managed-channels-on-startup. Update Purpose after archive.
## Requirements
### Requirement: Startup bootstrap mode is explicit and bounded

Healthcare Lab SHALL support startup bootstrap mode `create-missing` as the default and `off` as an opt-out, and SHALL require positive bounded timeout and retry interval configuration.

#### Scenario: Default startup configuration is loaded

- **WHEN** no bootstrap environment settings are provided
- **THEN** Healthcare Lab selects `create-missing` with documented finite timeout and retry interval defaults

#### Scenario: Bootstrap is disabled

- **WHEN** bootstrap mode is `off`
- **THEN** Healthcare Lab performs no bootstrap readiness checks or OIE Channel mutations

#### Scenario: Bootstrap configuration is invalid

- **WHEN** mode is unsupported or timeout or retry interval is not positive
- **THEN** Healthcare Lab rejects the invalid application configuration with an actionable error

### Requirement: Bootstrap starts once per runtime without browser traffic

Healthcare Lab SHALL start at most one bootstrap run for each concrete application runtime when runtime activation and `create-missing` mode are enabled, independently of browser requests.

#### Scenario: Production runtime starts

- **WHEN** the production lab-app runtime is constructed with bootstrap enabled
- **THEN** it starts one asynchronous bootstrap run without waiting for an HTTP request
- **AND** application health and HTTP handling remain available while bootstrap continues

#### Scenario: Runtime activation is suppressed

- **WHEN** an application is constructed with runtime activation disabled
- **THEN** it does not start the bootstrap worker

### Requirement: OIE readiness waiting is bounded and failure-isolated

Healthcare Lab SHALL retry OIE Management API readiness at the configured interval until a supported authenticated inventory can be read or the overall bootstrap timeout expires, and SHALL NOT crash or restart lab-app because bootstrap cannot complete.

#### Scenario: OIE readiness is delayed

- **WHEN** OIE is unavailable during initial attempts but becomes ready before the deadline
- **THEN** bootstrap continues from the first successful supported inventory read

#### Scenario: OIE readiness times out

- **WHEN** OIE does not become ready before the deadline
- **THEN** bootstrap records a bounded timeout outcome and stops for that runtime
- **AND** lab-app remains available

#### Scenario: Credentials or version are rejected

- **WHEN** readiness cannot establish an authenticated supported OIE session before the deadline
- **THEN** bootstrap records only a safe error category and does not expose credentials or upstream response bodies

### Requirement: Bootstrap creates and deploys only missing managed Channels

In `create-missing` mode, Healthcare Lab SHALL reconcile both canonical logical Channels and SHALL create, read back, persist identity, deploy, and verify only a Channel classified as `Missing` through guarded single-target lifecycle operations.

#### Scenario: Clean OIE startup completes

- **WHEN** both canonical managed Channels are missing and OIE becomes ready
- **THEN** bootstrap creates and deploys `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB` individually
- **AND** each persisted mapping contains its exact OIE identity and revision
- **AND** status verification reports each newly created Channel started

#### Scenario: Normal restart is a no-op

- **WHEN** both managed Channels are already present and unchanged
- **THEN** bootstrap performs no create, update, deploy, undeploy, delete, or redeploy mutation

#### Scenario: Only one Channel is missing

- **WHEN** one canonical Channel is unchanged and the other is missing
- **THEN** bootstrap creates and deploys only the missing Channel

#### Scenario: Existing unchanged Channel is stopped

- **WHEN** an unchanged managed Channel existed before the bootstrap run but is stopped or undeployed
- **THEN** bootstrap leaves its deployment state unchanged

### Requirement: Bootstrap preserves conflicts, drift, and external Channels

Healthcare Lab MUST NOT automatically update drifted Channels, adopt same-name external Channels, resolve ambiguous ownership, or mutate external or conflicted Channels during bootstrap.

#### Scenario: Managed Channel is drifted

- **WHEN** inventory classifies a canonical managed Channel as `Drifted`
- **THEN** bootstrap records a blocked no-mutation outcome for that logical type
- **AND** it does not update or redeploy the Channel

#### Scenario: Ownership is conflicted

- **WHEN** a same-name external Channel, duplicate managed marker, stale mapping, or other contradictory evidence produces `Conflict`
- **THEN** bootstrap records bounded blocking evidence and performs no mutation on any conflicting candidate

#### Scenario: Unrelated external Channel exists

- **WHEN** inventory contains a Channel unrelated to the two canonical managed identities
- **THEN** bootstrap leaves that Channel unchanged

### Requirement: Bootstrap evidence is durable and secret-safe

Healthcare Lab SHALL attribute bootstrap lifecycle activity to `startup-bootstrap` and SHALL record and log only bounded operational metadata without credentials, cookies, complete Channel payloads, HL7 messages, PHI, or arbitrary upstream bodies.

#### Scenario: Bootstrap mutation is attempted

- **WHEN** bootstrap creates or deploys a managed Channel
- **THEN** durable lifecycle audit records identify actor `startup-bootstrap`, logical type, operation, classification, Channel identity when known, revisions, outcome, and safe error category

#### Scenario: Bootstrap records a no-op or blocker

- **WHEN** bootstrap encounters unchanged, drifted, conflicted, external, or timeout state
- **THEN** its evidence is sufficient to identify the bounded outcome without storing sensitive values
