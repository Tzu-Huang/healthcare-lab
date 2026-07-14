## MODIFIED Requirements

### Requirement: Dashboard starts local GDT ECG order creation

Healthcare Lab SHALL provide a focused workspace for creating local GDT 12-lead resting ECG orders without coupling that workflow to an OpenEMR dashboard service row.

#### Scenario: User starts ECG order creation

- **WHEN** a user opens the Healthcare Lab application
- **THEN** dedicated GDT navigation opens or focuses the Order workflow in GDT ECG mode
- **AND** no OpenEMR/GDT service-group action is required

#### Scenario: Dashboard remains an operational surface

- **WHEN** the GDT ECG order flow is launched
- **THEN** Healthcare Lab does not replace the service health table with a full form-only dashboard
- **AND** the order form lives in the existing order workflow or an equivalent focused order workspace

