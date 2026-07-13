# healthcare-lab-order-hl7-orm-mvp Specification

## Purpose
Define Healthcare Lab's local HL7 v2.5.1 ECG order workflow, including order creation, stable ORM payload persistence, OIE order inventory, configurable MLLP send, ACK/result recording, and the boundary that downstream OIE-to-AP routing remains external OIE channel configuration.
## Requirements
### Requirement: Order page exposes HL7 v2.5.1 ECG order creation

Healthcare Lab SHALL provide an Order page workflow for creating local 12-lead ECG orders using HL7 v2.5.1.

#### Scenario: HL7 v2.5.1 is the enabled order protocol

- **WHEN** a user opens the Order page protocol selector
- **THEN** HL7 v2.5.1 is available for order creation
- **AND** FHIR, GDT, and DICOM are shown according to their current implementation status

#### Scenario: User prepares a 12-lead ECG order

- **WHEN** a user selects a local patient and applies the 12-lead ECG demo preset
- **THEN** the order form includes provider defaults, priority, requested service time, clinical indication, and ECG service coding
- **AND** the page displays validation status for required patient and order fields

### Requirement: Local order creation persists a stable ORM payload

Healthcare Lab SHALL persist local ECG order records and their generated HL7 v2.5.1 `ORM^O01` payloads in SQLite.

#### Scenario: User creates a valid local ECG order

- **WHEN** the selected patient and order fields are valid
- **AND** the user creates the order
- **THEN** Healthcare Lab stores a local order record linked to the selected local patient
- **AND** the order is marked `Ready to send`
- **AND** the generated `ORM^O01` payload is persisted with the order

#### Scenario: Patient has no visit or account number

- **WHEN** a user creates an order for a local patient without an existing visit/account number
- **THEN** Healthcare Lab generates a local outpatient visit/account id for the order
- **AND** the generated id is included in the persisted order payload

### Requirement: ORM preview uses the MVP segment baseline

Healthcare Lab SHALL generate and display an HL7 v2.5.1 `ORM^O01` preview containing the MVP segment baseline.

#### Scenario: User previews an order payload

- **WHEN** the Order page has enough valid patient and order data to preview a payload
- **THEN** the preview includes `MSH`, `PID`, `PV1`, `ORC`, and `OBR` segments
- **AND** `MSH` identifies `HEALTHCARE_LAB|DASHBOARD` as sender and `OIE|HL7LAB` as receiver
- **AND** `MSH-9` is `ORM^O01^ORM_O01`
- **AND** `MSH-12` is `2.5.1`

#### Scenario: User selects the 12-lead ECG preset

- **WHEN** the 12-lead ECG preset is active
- **THEN** the generated `OBR` service identifier includes local code `ECG12` and alternate code `93000`

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

### Requirement: OIE send transmits one selected order and records the result

Healthcare Lab SHALL send one selected local order at a time to an OIE MLLP endpoint and persist the result.

#### Scenario: User sends an order and OIE returns AA

- **WHEN** a user sends a selected `Ready to send` order to the configured OIE MLLP endpoint
- **AND** OIE returns an HL7 ACK with `MSA-1` of `AA`
- **THEN** Healthcare Lab stores the raw ACK payload
- **AND** the order send result records ACK code `AA`
- **AND** the order status indicates the order was accepted

#### Scenario: User sends an order and OIE returns AE or AR

- **WHEN** OIE returns an HL7 ACK with `MSA-1` of `AE` or `AR`
- **THEN** Healthcare Lab stores the raw ACK payload
- **AND** the order send result records the ACK code
- **AND** the order status indicates an HL7 application error or rejection

#### Scenario: OIE transport fails

- **WHEN** Healthcare Lab cannot connect to the configured OIE MLLP endpoint or the send times out
- **THEN** the order send result records a transport error
- **AND** no ACK code is fabricated

### Requirement: OIE connection settings are local and configurable

Healthcare Lab SHALL expose local OIE connection settings for manual order sending.

#### Scenario: User opens OIE connection settings

- **WHEN** the OIE page is loaded
- **THEN** the connection settings include host, port, timeout, and MLLP framing
- **AND** the default host is `localhost`
- **AND** the default port is `6600`

### Requirement: OIE-to-AP routing remains external configuration

Healthcare Lab SHALL treat OIE routing from received ORM messages to the AP as external OIE channel configuration.

#### Scenario: User reviews Order/OIE MVP scope

- **WHEN** the app documents or labels the Order/OIE send workflow
- **THEN** it does not claim to configure OIE-to-AP routing automatically
- **AND** it identifies downstream routing as OIE channel configuration outside this MVP scope

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
