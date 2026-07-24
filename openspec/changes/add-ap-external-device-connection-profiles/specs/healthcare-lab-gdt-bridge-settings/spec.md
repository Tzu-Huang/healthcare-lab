## ADDED Requirements

### Requirement: AP GDT identity is associated with a GDT Bridge profile
An enabled AP GDT section SHALL reference a valid GDT Bridge profile and SHALL supply the device-side sender and receiver identity used by GDT workflows.

#### Scenario: Resolve an enabled AP GDT section
- **WHEN** a GDT workflow starts for an environment with an effective AP profile
- **THEN** it combines the AP device identity with the selected Bridge profile's filesystem and lifecycle settings

#### Scenario: Missing or conflicting Bridge association
- **WHEN** an enabled AP GDT section references an unavailable Bridge profile or conflicts with required effective identity
- **THEN** the system reports `needs-setup` with stable value-safe guidance and does not start the workflow with ambiguous identity
