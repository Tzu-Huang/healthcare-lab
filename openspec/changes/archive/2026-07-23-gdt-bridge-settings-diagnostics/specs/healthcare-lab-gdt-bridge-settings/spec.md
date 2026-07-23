## ADDED Requirements

### Requirement: GDT Bridge runtime settings use a typed persisted profile

Healthcare Lab SHALL persist enabled state, application-visible bridge path, receiver ID, sender ID, filename profile, import-success mode, polling interval, and stable-file interval as one validated GDT Bridge profile.

#### Scenario: Operator saves a valid profile
- **WHEN** an operator submits a complete valid GDT Bridge profile
- **THEN** Healthcare Lab atomically persists the profile
- **AND** returns its typed public projection and activation outcome

#### Scenario: Any GDT field is invalid
- **WHEN** a submitted identity, mode, path, polling interval, or stable-file interval violates the typed contract
- **THEN** Healthcare Lab rejects the complete mutation with stable field-level errors
- **AND** preserves the prior profile

### Requirement: Supported Docker deployments distinguish application and host paths

Healthcare Lab SHALL use `/data/gdt-bridge` as the fixed application-visible path for the supported Docker runtime and SHALL present a discoverable host bind-mount source only as read-only deployment information.

#### Scenario: Docker bind mount is discoverable
- **WHEN** Settings reads GDT Bridge deployment information in a supported Docker deployment
- **THEN** it identifies `/data/gdt-bridge` as the application path
- **AND** displays the discovered host path as deployment-owned information
- **AND** explains that changing it requires deployment configuration and container recreation

#### Scenario: Host path cannot be discovered
- **WHEN** the application cannot safely discover the host bind-mount source
- **THEN** Settings still reports `/data/gdt-bridge` as the application path
- **AND** reports host-path metadata as unavailable without degrading GDT solely for that reason

### Requirement: Operators explicitly provision only documented bridge directories

Healthcare Lab SHALL require an explicit action before creating missing bridge directories and MUST restrict provisioning to documented directory roles beneath the effective bridge root.

#### Scenario: Operator provisions missing directories
- **WHEN** an operator explicitly requests GDT Bridge directory provisioning
- **THEN** Healthcare Lab creates only the documented inbox, outbox, processing, archive, error, and diagnostic directories that are missing
- **AND** returns bounded role-based outcomes without enumerating existing files

#### Scenario: Requested path escapes the bridge root
- **WHEN** a provisioning operation would resolve outside the effective bridge root
- **THEN** Healthcare Lab rejects the operation
- **AND** creates or mutates no directory or file

### Requirement: GDT filesystem diagnostics are bounded and non-destructive

Healthcare Lab SHALL diagnose mount/root existence, documented directory existence, read access, write/delete capability, and watcher runtime state without reading or mutating operator files.

#### Scenario: Empty bridge folder is healthy
- **WHEN** all required directories exist with required access and contain no files
- **THEN** diagnostics report the applicable path and permission checks as healthy
- **AND** do not treat the absence of messages as a failure

#### Scenario: Write/delete probe runs
- **WHEN** an operator runs the GDT write diagnostic
- **THEN** Healthcare Lab creates a uniquely generated empty diagnostic file in the documented diagnostic location
- **AND** verifies and deletes only that generated file
- **AND** reports distinct write or delete failures using bounded codes

#### Scenario: Diagnostics encounter operator data
- **WHEN** bridge directories contain GDT messages or filenames that may contain PHI
- **THEN** diagnostic responses, logs, readiness, and errors contain no message content or filename

### Requirement: GDT profile activation reports effective lifecycle state

Healthcare Lab SHALL apply saved watcher settings immediately when a safe serialized reload is supported and otherwise SHALL return `restart-required` with an exact activation class.

#### Scenario: Watcher reload is safe
- **WHEN** a valid saved change can be applied after safely quiescing the watcher
- **THEN** Healthcare Lab rebuilds the watcher from the new effective profile
- **AND** reports that the saved settings are effective immediately

#### Scenario: Watcher reload is unsafe
- **WHEN** the runtime cannot safely apply a valid saved change in-process
- **THEN** Healthcare Lab retains the persisted change
- **AND** reports `restart-required`
- **AND** identifies whether application restart or container recreation is required

### Requirement: GDT Settings owns its modular workspace

Healthcare Lab SHALL provide a GDT-owned Settings module for profile editing, deployment explanation, readiness, provisioning, and bounded diagnostics.

#### Scenario: Operator opens GDT Bridge Settings
- **WHEN** the GDT Bridge section is activated
- **THEN** the module loads the typed profile and read-only deployment metadata
- **AND** places expert-only identity, filename, and timing controls behind an accessible Advanced disclosure

#### Scenario: GDT Bridge is disabled
- **WHEN** the persisted GDT Bridge profile is disabled
- **THEN** its readiness provider reports `disabled`
- **AND** optional GDT setup does not block overall setup completion
