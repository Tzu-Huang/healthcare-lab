## ADDED Requirements

### Requirement: Typed integration settings distinguish integrations from device collections
The system SHALL preserve one canonical typed profile per integration while assigning multi-record AP/external-device ownership to a dedicated device-profile aggregate.

#### Scenario: Multiple AP profiles coexist with integration profiles
- **WHEN** operators configure multiple AP profiles
- **THEN** Medplum, OIE, GDT Bridge, and dcm4chee retain their independent canonical integration profiles

#### Scenario: Runtime requests effective device values
- **WHEN** an integration needs AP values
- **THEN** it obtains a narrow projection from the effective-device application service rather than reading or duplicating device persistence
