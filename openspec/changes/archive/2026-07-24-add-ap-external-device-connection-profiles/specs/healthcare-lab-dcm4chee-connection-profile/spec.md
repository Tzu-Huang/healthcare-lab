## ADDED Requirements

### Requirement: dcm4chee workflows use effective AP DICOM identity
MWL and DICOM result-delivery workflows SHALL obtain AP AE title, MWL calling/station identity, endpoint, and supported role from the effective AP DICOM projection.

#### Scenario: Create MWL for an AP
- **WHEN** an Order is projected to MWL for an environment with an enabled AP DICOM section
- **THEN** the Scheduled Station and calling identity derive from the effective AP profile

#### Scenario: Keep archive and AP endpoints distinct
- **WHEN** the system composes a DICOM operation
- **THEN** dcm4chee called AE and archive endpoints remain dcm4chee-owned while AP AE and device endpoint values remain AP-owned

#### Scenario: Unsupported result-delivery role
- **WHEN** an enabled AP DICOM section selects an unsupported or incomplete result-delivery role
- **THEN** validation rejects the profile with stable field-level errors before workflow execution
