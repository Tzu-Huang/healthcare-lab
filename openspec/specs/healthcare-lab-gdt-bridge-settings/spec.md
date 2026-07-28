# healthcare-lab-gdt-bridge-settings Specification

## Purpose
TBD - created by archiving change gdt-bridge-settings-diagnostics. Update Purpose after archive.
## Requirements
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

Healthcare Lab SHALL use `/data/gdt-bridge` as the fixed application-visible path for the supported Docker runtime and SHALL let an operator view and explicitly apply one dedicated Windows host bind-mount root through the bounded localhost deployment controller.

#### Scenario: Docker bind mount is discoverable

- **WHEN** Settings reads GDT Bridge deployment information in a supported Docker deployment
- **THEN** it identifies `/data/gdt-bridge` as the fixed application path
- **AND** displays the desired and effective host path and ownership source
- **AND** indicates whether a save, container recreation, verification, or external-override resolution is required

#### Scenario: Operator applies a new host path

- **WHEN** an operator enters a valid dedicated Windows absolute path and confirms apply
- **THEN** Settings submits one root to the bounded localhost controller
- **AND** displays progress while the controller provisions the directory contract and recreates `lab-app`
- **AND** reloads the effective deployment and diagnostics after successful verification

#### Scenario: Host controller is unavailable

- **WHEN** the application cannot safely discover or contact the host controller
- **THEN** Settings still reports `/data/gdt-bridge` as the application path
- **AND** preserves read-only desired/effective deployment metadata when available
- **AND** reports bounded wrapper fallback guidance without degrading GDT solely for controller unavailability

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

### Requirement: AP GDT identity is associated with a GDT Bridge profile
An enabled AP GDT section SHALL reference a valid GDT Bridge profile and SHALL supply the device-side sender and receiver identity used by GDT workflows.

#### Scenario: Resolve an enabled AP GDT section
- **WHEN** a GDT workflow starts for an environment with an effective AP profile
- **THEN** it combines the AP device identity with the selected Bridge profile's filesystem and lifecycle settings

#### Scenario: Missing or conflicting Bridge association
- **WHEN** an enabled AP GDT section references an unavailable Bridge profile or conflicts with required effective identity
- **THEN** the system reports `needs-setup` with stable value-safe guidance and does not start the workflow with ambiguous identity

### Requirement: GDT folder setup uses one operator-owned root

Healthcare Lab SHALL ask the operator for one host bridge root and SHALL derive all supported host and container bridge subdirectories rather than requiring separate GDT-IN and GDT-OUT path coordination.

#### Scenario: GDT setup is rendered

- **WHEN** the operator opens the GDT folder setup surface
- **THEN** it provides one editable host root
- **AND** shows inbox, outbox, processing, archive, error, and diagnostic paths as derived read-only values
- **AND** does not expose `/data/gdt-bridge` as an editable deployment choice

