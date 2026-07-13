## MODIFIED Requirements

### Requirement: OIE page shows local Order inventory

Healthcare Lab SHALL show local Order inventory in the patient-centered OIE workspace with sufficient identity and transmission context for independent operator verification.

#### Scenario: Orders exist in local inventory

- **WHEN** one or more local orders have been created
- **THEN** the OIE Orders section lists each Order's placer Order ID, Patient MRN, Visit Number, order code, status, and Order Created At
- **AND** the placer Order ID is the value emitted consistently in `ORC-2` and `OBR-2`
- **AND** Visit Number is the value emitted in `PV1-19`, while `PV1-1` remains the segment Set ID
- **AND** Order Created At is rendered as an unambiguous Taipei timestamp
- **AND** the row retains ACK and sent-time context when transmission has been attempted
- **AND** selecting an order displays order details and the raw persisted ORM payload

#### Scenario: No orders exist

- **WHEN** no local orders have been created
- **THEN** the OIE page displays an empty Order inventory state without hiding the Patient inventory

## ADDED Requirements

### Requirement: Local Orders shows consistent core order identity

Healthcare Lab SHALL show the same core patient, visit, order, and creation identifiers for local orders across supported protocol modes.

#### Scenario: Local Order row is displayed

- **WHEN** a local HL7 v2, FHIR, GDT, or DICOM order is listed
- **THEN** Local Orders displays Order ID, mode, MRN, Visit Number, patient name, order code, status, and Order Created At when those values exist for the protocol
- **AND** Order Created At is rendered as an unambiguous Taipei timestamp

#### Scenario: HL7 Order row is displayed

- **WHEN** a local HL7 v2.5.1 Order is listed
- **THEN** Order ID identifies the placer order number represented by `ORC-2` and `OBR-2`
- **AND** Visit Number identifies `PV1-19`
- **AND** MRN identifies `PID-3`
