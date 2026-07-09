## MODIFIED Requirements

### Requirement: dcm4chee profile includes local archive connection settings
Healthcare Lab SHALL provide a named dcm4chee-arc connection profile for local lab workflows.

#### Scenario: Local dcm4chee profile is available
- **WHEN** Healthcare Lab loads the local dcm4chee profile
- **THEN** it includes the profile name, display name, and environment name
- **AND** it includes the Web UI URL
- **AND** it includes DIMSE host, port, called AE title, and Healthcare Lab calling AE title
- **AND** it includes MWL AE title and default Scheduled Station AE Title
- **AND** it includes DICOMweb endpoint values for query, retrieve, store, and MWL workflows
- **AND** it includes HL7 receiver host, port, sending application/facility, receiving application/facility, and Patient assigning authority settings for Patient sync workflows
- **AND** it includes auth and TLS settings needed by future secured dcm4chee deployments

#### Scenario: Local profile diagnostics report invalid required fields
- **WHEN** a required local dcm4chee profile field is missing or invalid
- **THEN** Healthcare Lab reports the invalid field and a human-readable diagnostic message
- **AND** Patient sync, MWL, and DICOMweb diagnostics identify their own missing or invalid settings
