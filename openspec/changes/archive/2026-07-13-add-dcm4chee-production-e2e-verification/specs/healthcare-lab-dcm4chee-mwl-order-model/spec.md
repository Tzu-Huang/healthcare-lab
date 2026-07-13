## ADDED Requirements

### Requirement: dcm4chee workflow has production-like E2E verification
Healthcare Lab SHALL provide a repeatable verification path that proves a local DICOM patient/order can flow through dcm4chee MWL, AP result return, dcm4chee result storage, Healthcare Lab reconciliation, and frontend result display.

#### Scenario: Operator runs the production-like dcm4chee E2E verification
- **GIVEN** the local Healthcare Lab and dcm4chee services are started with a valid dcm4chee profile
- **WHEN** an operator creates the E2E demo DICOM patient/order
- **THEN** Healthcare Lab syncs the dcm4chee Patient precondition
- **AND** Healthcare Lab creates or confirms the dcm4chee MWL/order
- **AND** Healthcare Lab verifies the order is queryable from the configured MWL surface
- **AND** the verification path records the identifiers needed by AP to query and fulfill the order

#### Scenario: Verification records repeatable evidence
- **GIVEN** an E2E verification run has created or selected a DICOM order
- **WHEN** Healthcare Lab reports verification evidence
- **THEN** the evidence includes Patient ID, Issuer of Patient ID, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Study Instance UID when available, AE titles, endpoint URLs, status values, timestamps, and relevant diagnostics
- **AND** the evidence distinguishes automated fixture checks from manual live AP/dcm4chee checks

### Requirement: AP-return simulation can verify frontend result display
Healthcare Lab SHALL provide a repeatable simulated AP-return fixture that can prove the frontend displays AP-returned PDF or DICOM results for a local DICOM order without requiring a live AP run.

#### Scenario: Simulated AP returns a PDF artifact
- **GIVEN** a local DICOM order has canonical dcm4chee MWL identifiers
- **WHEN** Healthcare Lab records a simulated AP-return PDF artifact for that order
- **THEN** the patient or order DICOM result UI shows the AP-returned result status
- **AND** the UI exposes the PDF artifact label and link or path metadata when available
- **AND** the displayed result remains tied to the expected local order identifiers

#### Scenario: Simulated AP returns DICOM result metadata
- **GIVEN** a local DICOM order has canonical dcm4chee MWL identifiers
- **WHEN** Healthcare Lab records simulated AP-return DICOM result metadata for that order
- **THEN** the patient or order DICOM result UI shows the Study, Series, and Instance hierarchy when those identifiers are available
- **AND** the UI shows Study Instance UID, Series Instance UID, SOP Instance UID, Accession Number, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID when available
- **AND** Healthcare Lab labels the result source so operators can distinguish simulated AP-return evidence from live dcm4chee-reconciled evidence

### Requirement: E2E SOP is sufficient to repeat the lab verification
Healthcare Lab SHALL document the complete dcm4chee production-like verification procedure so an operator can repeat the test in the local lab environment.

#### Scenario: Operator follows the SOP
- **GIVEN** an operator needs to repeat dcm4chee E2E verification
- **WHEN** the operator follows the SOP
- **THEN** the SOP identifies service startup steps, required ports, AE titles, dcm4chee MWL and archive endpoints, demo fixture steps, live AP steps, simulated AP-return steps, expected identifiers, evidence capture, and troubleshooting guidance
- **AND** the SOP explains the distinction between the `WORKLIST` MWL REST surface and the `DCM4CHEE` archive QIDO/WADO/STOW surface
