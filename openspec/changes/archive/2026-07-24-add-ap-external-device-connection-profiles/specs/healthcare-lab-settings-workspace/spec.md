## ADDED Requirements

### Requirement: Settings provides an AP and external-device profile workspace
The Settings workspace SHALL provide an independently owned AP / External Devices module for profile management, protocol configuration, default selection, diagnostics, activation guidance, and safe last-interaction metadata.

#### Scenario: Operator reviews endpoint direction
- **WHEN** the operator edits an AP protocol section
- **THEN** the workspace clearly distinguishes AP endpoints from Healthcare Lab, OIE, GDT Bridge, and dcm4chee endpoints

#### Scenario: Optional AP integration is unused
- **WHEN** no AP profile or protocol path is enabled
- **THEN** the module reports `disabled` and does not block overall optional setup completion

### Requirement: Settings Overview reflects effective AP readiness
The Settings Overview SHALL aggregate AP readiness and diagnostics using the effective profile for the active environment.

#### Scenario: OIE activation is pending
- **WHEN** an AP HL7 change causes managed-Channel desired-state drift
- **THEN** Overview reports `apply-required` and directs the operator to the guarded OIE preview/apply workflow

#### Scenario: Device diagnostic fails
- **WHEN** an enabled device profile is valid but a bounded diagnostic fails
- **THEN** Overview reports `degraded` without exposing raw upstream errors or clinical payloads
