## ADDED Requirements

### Requirement: Effective AP HL7 values drive approved OIE desired state
The ORM-to-AP desired Channel projection SHALL obtain its AP destination and owned AP identity values from the effective AP profile for the active environment.

#### Scenario: Effective AP endpoint changes
- **WHEN** the effective AP HL7 host or port differs from the inspected managed Channel
- **THEN** inventory reports `apply-required` with owned-field drift

#### Scenario: AP profile is saved
- **WHEN** an operator saves or selects an AP profile
- **THEN** the system does not automatically preview, apply, deploy, redeploy, or otherwise mutate an OIE Channel

#### Scenario: Guarded activation
- **WHEN** an operator chooses to activate AP-driven desired changes
- **THEN** the existing state-bound single-target preview and execute requirements remain mandatory
