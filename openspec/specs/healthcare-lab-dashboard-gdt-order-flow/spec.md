# healthcare-lab-dashboard-gdt-order-flow Specification

## Purpose
Define Healthcare Lab's dashboard-started local GDT 12-lead resting ECG order workflow, including patient selection or creation, fixed `8402=EKG01` test type handling, OpenEMR-independent persistence, local status display, and preservation of the existing HL7 ORM/OIE order flow.
## Requirements
### Requirement: Dashboard starts local GDT ECG order creation

Healthcare Lab SHALL provide a dashboard-started flow for creating local GDT 12-lead resting ECG orders.

#### Scenario: User starts ECG order creation from the dashboard

- **WHEN** a user opens the Healthcare Lab dashboard
- **THEN** the OpenEMR/GDT service group exposes an action for creating a local ECG order
- **AND** activating that action opens or focuses the Order workflow in GDT ECG mode

#### Scenario: Dashboard remains an operational surface

- **WHEN** the GDT ECG order flow is launched from the dashboard
- **THEN** Healthcare Lab does not replace the service health table with a full form-only dashboard
- **AND** the order form lives in the existing order workflow or an equivalent focused order workspace

### Requirement: GDT ECG order flow supports patient selection and creation

Healthcare Lab SHALL allow the user to select an existing local patient or create a local patient before creating a GDT ECG order.

#### Scenario: User selects an existing patient

- **WHEN** local patient records exist
- **AND** the user opens the GDT ECG order flow
- **THEN** the user can select one local patient for the order

#### Scenario: User creates a patient from the order flow

- **WHEN** the needed patient does not exist
- **AND** the user enters the required patient demographics in the dashboard-started flow
- **THEN** Healthcare Lab creates a local patient record
- **AND** the new patient can be used immediately for the GDT ECG order

### Requirement: GDT ECG order uses fixed MVP test type

Healthcare Lab SHALL create only 12-lead resting ECG GDT orders in the MVP.

#### Scenario: User creates the MVP ECG order

- **WHEN** the user creates a GDT ECG order
- **THEN** Healthcare Lab stores the order with GDT field `8402` value `EKG01`
- **AND** the UI identifies the order as 12-lead resting ECG

#### Scenario: Non-MVP ECG test types are not selectable

- **WHEN** the user opens the GDT ECG order flow
- **THEN** `EKG04` is not selectable
- **AND** `ERGO01` is not selectable
- **AND** the backend does not accept a request that overrides the MVP test type away from `EKG01`

#### Scenario: 8402 is not confused with Test-ID

- **WHEN** Healthcare Lab renders or stores the GDT ECG order payload
- **THEN** field `8402` carries the standardized category code `EKG01`
- **AND** field `8410` is not used as a substitute for the order's 8402 test category

### Requirement: GDT ECG orders persist independently from OpenEMR

Healthcare Lab SHALL persist dashboard-created GDT ECG orders without requiring OpenEMR server or database access.

#### Scenario: OpenEMR is not configured

- **WHEN** OpenEMR database settings are missing or unreachable
- **AND** the user creates a valid local GDT ECG order
- **THEN** Healthcare Lab stores the order successfully
- **AND** the response does not depend on OpenEMR procedure-order query readiness

#### Scenario: Created orders survive refresh

- **WHEN** one or more GDT ECG orders have been created
- **AND** the user refreshes the browser or reloads the order list
- **THEN** the created GDT ECG orders remain visible with patient identity, `EKG01`, status, and created time

### Requirement: GDT order status is local and explicit

Healthcare Lab SHALL display local status for dashboard-created GDT ECG orders without implying device result completion.

#### Scenario: Order is created locally

- **WHEN** Healthcare Lab persists a new GDT ECG order
- **THEN** the order status is shown as a local workflow status such as `Created` or `Queued for GDT`

#### Scenario: Order export fails

- **WHEN** Healthcare Lab attempts a local GDT export and the export fails
- **THEN** the order status is shown as `Error`
- **AND** diagnostic text is preserved for developer review

### Requirement: Existing HL7 ORM order flow remains intact

Healthcare Lab SHALL preserve the existing HL7 v2.3.1 ORM order creation and OIE send workflow while adding the GDT ECG order path.

#### Scenario: User creates an HL7 order

- **WHEN** the user selects HL7 v2.3.1 order mode
- **THEN** Healthcare Lab continues to create an `ORM^O01` payload with `MSH`, `PID`, `PV1`, `ORC`, and `OBR`
- **AND** existing OIE local order send behavior remains available

#### Scenario: User creates a GDT order

- **WHEN** the user selects GDT ECG order mode
- **THEN** Healthcare Lab creates a GDT-specific local order record
- **AND** it does not fabricate HL7 ACK fields or OIE send status for that GDT order
