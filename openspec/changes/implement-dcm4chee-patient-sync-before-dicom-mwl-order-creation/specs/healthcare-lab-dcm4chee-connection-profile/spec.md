## ADDED Requirements

### Requirement: dcm4chee profile includes HL7 Patient sync settings
Healthcare Lab SHALL store the HL7 receiver settings required by dcm4chee Patient sync workflows.

#### Scenario: Profile exposes HL7 receiver values
- **WHEN** Healthcare Lab loads the dcm4chee connection profile
- **THEN** the profile includes HL7 receiver host and port
- **AND** the profile includes sending application and sending facility
- **AND** the profile includes receiving application and receiving facility
- **AND** the profile includes the Patient assigning authority used for dcm4chee Patient IDs

## MODIFIED Requirements

### Requirement: dcm4chee profile diagnostics report incomplete configuration
Healthcare Lab SHALL provide backend validation or diagnostic output for the dcm4chee connection profile.

#### Scenario: Local profile diagnostics report invalid required fields
- **WHEN** a required local dcm4chee profile field is missing or invalid
- **THEN** Healthcare Lab reports the invalid field and a human-readable diagnostic message
- **AND** Patient sync, MWL, and DICOMweb diagnostics identify their own missing or invalid settings
