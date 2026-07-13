## MODIFIED Requirements

### Requirement: Selected patient workspace shows orders and results

Healthcare Lab SHALL show the selected patient's local orders and received results in one workspace, while keeping each Order row independently identifiable.

#### Scenario: User selects a patient

- **WHEN** a user selects a patient from the ADT Patients list
- **THEN** the Selected Patient workspace shows that patient's Orders section
- **AND** it shows that patient's Results section
- **AND** each Order row shows Order ID, MRN, Visit Number, order code, status, and an unambiguous Taipei Order Created At timestamp

#### Scenario: User selects an ADT, ORM, or ORU item

- **WHEN** a user selects an ADT patient row, order row, or result row
- **THEN** the shared HL7 preview updates to the selected ADT, ORM, or ORU raw payload
- **AND** the preview includes a parsed summary when parsing succeeds

#### Scenario: Operator verifies an HL7 Order row

- **WHEN** an operator compares an OIE Order row with its persisted ORM payload
- **THEN** the displayed MRN matches `PID-3`
- **AND** the displayed Visit Number matches `PV1-19`
- **AND** the displayed Order ID matches both `ORC-2` and `OBR-2`
