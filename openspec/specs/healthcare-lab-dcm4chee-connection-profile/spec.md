# healthcare-lab-dcm4chee-connection-profile Specification

## Purpose
Define the Healthcare Lab dcm4chee-arc connection profile contract, including local defaults, DIMSE/MWL/DICOMweb/viewer settings, security placeholders, and profile diagnostics.
## Requirements
### Requirement: Healthcare Lab loads a named dcm4chee connection profile
Healthcare Lab SHALL load a named dcm4chee-arc connection profile for DICOM workflow configuration.

#### Scenario: Local dcm4chee profile is available
- **WHEN** Healthcare Lab requests the `local-dcm4chee` connection profile
- **THEN** the profile includes the display name `dcm4chee Local Archive`
- **AND** the profile includes the environment name `local-docker`
- **AND** the profile includes the Web UI URL `http://127.0.0.1:8082/dcm4chee-arc/ui2`

### Requirement: dcm4chee profile includes DIMSE and MWL connection values
Healthcare Lab SHALL store the DIMSE and MWL values required by future MWL order creation, MWL verification, and result reconciliation workflows.

#### Scenario: Profile exposes DICOM association values
- **WHEN** Healthcare Lab loads the dcm4chee connection profile
- **THEN** the profile includes DIMSE host `127.0.0.1`
- **AND** the profile includes DIMSE port `11112`
- **AND** the profile includes called AE title `DCM4CHEE`
- **AND** the profile includes Healthcare Lab calling AE title `HEALTHCARE_LAB`

#### Scenario: Profile exposes MWL station values
- **WHEN** Healthcare Lab loads the dcm4chee connection profile
- **THEN** the profile includes MWL AE title `WORKLIST`
- **AND** the profile includes default Scheduled Station AE Title `ECG_AP`

### Requirement: dcm4chee profile includes DICOMweb and viewer endpoint values
Healthcare Lab SHALL store DICOMweb endpoint values and viewer-link configuration needed by future query, retrieve, store, and viewer integrations.

#### Scenario: Profile exposes DICOMweb endpoints
- **WHEN** Healthcare Lab loads the dcm4chee connection profile
- **THEN** the profile includes DICOMweb base URL `http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs`
- **AND** the profile includes query endpoint configuration for QIDO-RS
- **AND** the profile includes retrieve/view endpoint configuration for WADO-RS
- **AND** the profile includes store endpoint configuration for STOW-RS
- **AND** the profile includes viewer-link configuration for future study links

### Requirement: dcm4chee profile includes explicit security settings
Healthcare Lab SHALL include auth and TLS settings in the dcm4chee profile even when the local lab profile runs without auth or TLS.

#### Scenario: Local profile declares no auth or TLS
- **WHEN** Healthcare Lab loads the local dcm4chee profile
- **THEN** the profile includes auth mode `none`
- **AND** the profile includes TLS enabled `false`
- **AND** the profile includes placeholders for future credential, token, certificate, and key settings
- **AND** Healthcare Lab does not imply that the local unauthenticated profile is production-ready

### Requirement: dcm4chee profile diagnostics report incomplete configuration
Healthcare Lab SHALL provide backend validation or diagnostic output for the dcm4chee connection profile.

#### Scenario: Profile is complete
- **GIVEN** the configured dcm4chee profile includes all required local values
- **WHEN** Healthcare Lab validates the profile
- **THEN** the diagnostic output reports the profile as valid
- **AND** the diagnostic output includes individual checks for identity, Web UI, DIMSE, MWL, DICOMweb, and security settings

#### Scenario: Required profile values are missing
- **GIVEN** the configured dcm4chee profile is missing a required value
- **WHEN** Healthcare Lab validates the profile
- **THEN** the diagnostic output reports the profile as invalid
- **AND** the diagnostic output identifies each missing or invalid field with a clear message
