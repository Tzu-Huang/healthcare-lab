# healthcare-lab-gdt-host-path-controller Specification

## Purpose
TBD - created by archiving change gdt-host-path-controller. Update Purpose after archive.
## Requirements
### Requirement: A bounded localhost controller applies the GDT host root

The supported Windows deployment SHALL provide a loopback-only controller that accepts one validated GDT host root and SHALL NOT expose general filesystem, environment, Compose, Docker, or command execution.

#### Scenario: Operator submits a valid dedicated absolute path

- **WHEN** an authorized Healthcare Lab origin submits one valid Windows absolute GDT host root
- **THEN** the controller accepts a serialized apply operation
- **AND** performs only the documented GDT provisioning, persistence, `lab-app` recreation, and verification steps

#### Scenario: Request attempts broader control

- **WHEN** a request contains an unsupported operation, field, service, command, environment key, or mount
- **THEN** the controller rejects the complete request
- **AND** performs no filesystem or deployment mutation

### Requirement: Controller requests are local and authenticated

The controller MUST listen only on loopback and MUST require an exact allowed local Healthcare Lab origin, a non-simple request header, and an installation-scoped authorization value for every mutation.

#### Scenario: Authorized browser request

- **WHEN** the GDT UI loaded from an allowed local Healthcare Lab origin submits a correctly authenticated apply request
- **THEN** the controller evaluates the request under the bounded GDT contract

#### Scenario: Untrusted web or local request

- **WHEN** a mutation has a missing, null, wildcard, or unapproved origin or lacks valid authorization
- **THEN** the controller rejects it before path validation or mutation
- **AND** does not disclose the authorization value in its response or logs

### Requirement: Host paths are narrowly validated and provisioned

The controller SHALL accept only a dedicated Windows absolute directory and SHALL reject broad, traversing, relative, UNC, repository-owned, deployment-owned, or file targets before creating anything.

#### Scenario: Safe missing directory is selected

- **WHEN** a valid dedicated absolute target does not exist
- **THEN** the controller creates that exact root
- **AND** creates only the documented inbox, outbox, processing, archive, error, and diagnostic children

#### Scenario: Unsafe target is selected

- **WHEN** the target is a drive root, repository root, deployment root, user-profile root, relative path, UNC path, traversal path, or existing file
- **THEN** the controller rejects the operation with bounded guidance
- **AND** creates, deletes, or moves nothing

### Requirement: Deployment state and application settings remain separate

The controller SHALL atomically persist the desired host bind source in host-local deployment state, while `/data/gdt-bridge` remains the fixed application path and typed GDT settings continue to own protocol and watcher behavior.

#### Scenario: Controller-owned value is applied

- **WHEN** no higher-precedence advanced override exists and an apply operation persists a host root
- **THEN** the wrapper supplies that root to Compose as `GDT_BRIDGE_HOST_PATH`
- **AND** the replacement application continues to use `/data/gdt-bridge`

#### Scenario: Advanced override conflicts

- **WHEN** a process environment or documented `.env` value has higher precedence than controller-owned state
- **THEN** the system reports desired and effective sources as different
- **AND** does not overwrite or silently bypass the advanced override

### Requirement: Apply operations survive application recreation

The controller SHALL run apply as a serialized operation independent of the `lab-app` HTTP lifecycle and SHALL expose bounded status through terminal success or failure.

#### Scenario: Apply succeeds

- **WHEN** validation, provisioning, persistence, recreation, and post-restart verification all succeed
- **THEN** the operation reaches `succeeded`
- **AND** reports the normalized effective host root and healthy role-based diagnostics without listing bridge files

#### Scenario: Apply fails

- **WHEN** any apply stage fails
- **THEN** the operation reaches `failed` with its stage and bounded remediation
- **AND** no secret, token, directory content, or PHI-bearing filename is returned or logged
- **AND** a later retry remains possible

