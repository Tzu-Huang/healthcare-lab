## ADDED Requirements

### Requirement: Dashboard exposes allowlisted primary and child services

Healthcare Lab SHALL present OIE, Medplum, and dcm4chee as the dashboard's external primary services and SHALL expose only their declared deployment children.

#### Scenario: Dashboard service hierarchy is loaded
- **WHEN** a user loads the dashboard service list
- **THEN** the primary rows are OIE, Medplum, and dcm4chee
- **AND** OIE has no child services
- **AND** Medplum has `medplum-redis-1` and `medplum-postgres-1`
- **AND** dcm4chee has `ldap-1` and `dcm4chee-db-1`

#### Scenario: Arbitrary container is requested
- **WHEN** a caller requests a child identifier that is not declared under its primary service
- **THEN** Healthcare Lab rejects the request
- **AND** no Docker operation is performed

### Requirement: Child services are expandable and independently controllable

Healthcare Lab SHALL render declared child services in an expandable list and SHALL provide Check, Start, Stop, and Restart for each child when Docker operations are available.

#### Scenario: User expands a primary service
- **WHEN** a primary service has declared children and the user expands it
- **THEN** each child is shown with its own runtime status and action controls

#### Scenario: User controls one child
- **WHEN** a user starts, stops, or restarts one declared child
- **THEN** Healthcare Lab targets only that child Compose service
- **AND** it does not send the corresponding action to the primary service

#### Scenario: User checks one child
- **WHEN** a user checks a declared child
- **THEN** Healthcare Lab reports whether its Docker container exists and is running
- **AND** the check does not require an HTTP or protocol endpoint

### Requirement: Primary controls coordinate dependent child services

Healthcare Lab SHALL apply primary lifecycle actions to the primary service and all declared children in dependency-safe order.

#### Scenario: Primary service is started
- **WHEN** a user starts Medplum or dcm4chee
- **THEN** Healthcare Lab starts the declared children before the primary service

#### Scenario: Primary service is stopped
- **WHEN** a user stops Medplum or dcm4chee
- **THEN** Healthcare Lab stops the primary service before its declared children

#### Scenario: Primary service is restarted
- **WHEN** a user restarts Medplum or dcm4chee
- **THEN** Healthcare Lab restarts the declared children before restarting the primary service

#### Scenario: Standalone OIE is controlled
- **WHEN** a user starts, stops, or restarts OIE
- **THEN** Healthcare Lab controls only the OIE Compose service

### Requirement: Child names and state are stable across Compose prefixes

Healthcare Lab SHALL resolve child containers using Docker Compose service labels and SHALL present stable short display names independent of the Compose project prefix.

#### Scenario: Compose uses the interoperability-lab project prefix
- **WHEN** Docker reports a container named `interoperability-lab-medplum-redis-1`
- **THEN** the dashboard displays `medplum-redis-1`
- **AND** actions resolve the container using the `medplum-redis` Compose service label

### Requirement: GDT remains separate from server lifecycle controls

Healthcare Lab SHALL keep the local GDT workspace available without presenting OpenEMR or GDT as a dashboard-controlled external server.

#### Scenario: User opens the service dashboard
- **WHEN** the default local GDT workflow is enabled
- **THEN** no OpenEMR/GDT service row is shown
- **AND** the GDT workspace remains accessible through its dedicated navigation
- **AND** GDT bridge watcher controls remain available in that workspace

