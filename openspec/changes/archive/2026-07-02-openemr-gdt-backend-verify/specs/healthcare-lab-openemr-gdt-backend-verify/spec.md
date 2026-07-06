## ADDED Requirements

### Requirement: OpenEMR/GDT backend verification reports required runtime dependencies

Healthcare Lab SHALL provide a backend OpenEMR/GDT verification result that reports OpenEMR HTTP reachability, OpenEMR MariaDB connectivity, required OpenEMR procedure-order query readiness, and GDT shared-folder access as structured check steps.

#### Scenario: All required backend checks pass

- **WHEN** the default Docker runtime has reachable OpenEMR HTTP, reachable OpenEMR MariaDB, query-ready OpenEMR procedure-order tables, and a writable GDT bridge folder
- **THEN** the backend verify result reports the required OpenEMR/GDT steps as `Healthy`

#### Scenario: OpenEMR HTTP is unreachable

- **WHEN** OpenEMR HTTP cannot be reached through the configured runtime endpoint
- **THEN** the backend verify result marks the OpenEMR HTTP step as a required failure
- **AND** the overall backend verify result is not `Healthy`

#### Scenario: OpenEMR MariaDB is unreachable

- **WHEN** the lab app cannot connect to OpenEMR MariaDB using the default runtime settings
- **THEN** the backend verify result marks the MariaDB connection step as a required failure
- **AND** the overall backend verify result is not `Healthy`

#### Scenario: Required OpenEMR order schema is unavailable

- **WHEN** the lab app can connect to MariaDB but the required OpenEMR procedure-order query cannot run because required tables or query fields are unavailable
- **THEN** the backend verify result marks the OpenEMR order schema/query step as a required failure
- **AND** the overall backend verify result is not `Healthy`

#### Scenario: GDT bridge folder is not writable

- **WHEN** the configured GDT bridge folder structure cannot be created, written, or read by the lab app
- **THEN** the backend verify result marks the GDT folder contract step as a required failure
- **AND** the overall backend verify result is not `Healthy`

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

