# healthcare-lab-openemr-gdt-backend-verify Specification

## Purpose
TBD - created by archiving change openemr-gdt-backend-verify. Update Purpose after archive.
## Requirements
### Requirement: OpenEMR/GDT backend verification reports required runtime dependencies

Healthcare Lab SHALL treat OpenEMR backend verification as an optional integration and SHALL NOT require OpenEMR HTTP or MariaDB for the default local GDT runtime.

#### Scenario: Default local GDT runtime is used

- **WHEN** OpenEMR is not configured or provisioned
- **THEN** Healthcare Lab can run its local GDT order, bridge, watcher, and result workflows
- **AND** missing OpenEMR HTTP or MariaDB is not a required GDT runtime failure

#### Scenario: Optional OpenEMR integration is configured

- **WHEN** an operator configures an external OpenEMR HTTP endpoint and procedure-order database source
- **THEN** the OpenEMR verification path reports HTTP reachability, MariaDB connectivity, procedure-order query readiness, and GDT shared-folder access as structured check steps

#### Scenario: GDT bridge folder is not writable

- **WHEN** the configured GDT bridge folder structure cannot be created, written, or read by the lab app
- **THEN** the local GDT verification marks the folder contract as a required failure
- **AND** the failure is independent of OpenEMR availability

### Requirement: Missing ECG orders degrade verification without hiding backend readiness

Healthcare Lab SHALL distinguish a connected OpenEMR/GDT backend with no matching ECG procedure orders from a backend dependency failure.

#### Scenario: No matching ECG procedure orders exist

- **WHEN** OpenEMR HTTP, MariaDB connectivity, required procedure-order query readiness, and GDT folder checks pass
- **AND** the OpenEMR procedure-order query returns zero rows for the configured ECG procedure codes
- **THEN** the backend verify result marks the ECG order presence step as `Degraded`
- **AND** the overall backend verify result is `Degraded`

#### Scenario: Matching ECG procedure orders exist

- **WHEN** the required backend checks pass
- **AND** the OpenEMR procedure-order query returns at least one matching ECG order
- **THEN** the backend verify result marks ECG order presence as `Healthy`

### Requirement: Backend verify details are developer-visible before frontend status-card work

Healthcare Lab SHALL expose OpenEMR/GDT backend verification details through an existing backend smoke/check response or an equivalent backend API response before adding any new frontend status-card design.

#### Scenario: Developer runs OpenEMR/GDT smoke or check

- **WHEN** a developer invokes the OpenEMR/GDT backend smoke/check path
- **THEN** the response includes each verification step name, status, required flag, and diagnostic message

