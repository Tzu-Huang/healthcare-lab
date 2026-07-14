## MODIFIED Requirements

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

