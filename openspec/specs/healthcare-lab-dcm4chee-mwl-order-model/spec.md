# healthcare-lab-dcm4chee-mwl-order-model Specification

## Purpose
Define the Healthcare Lab and dcm4chee-arc MWL order-first contract, including source-of-truth boundaries, required DICOM patient/order fields, generated identifier policy, and result reconciliation rules.
## Requirements
### Requirement: dcm4chee MWL workflow has explicit source-of-truth boundaries
Healthcare Lab SHALL define dcm4chee-arc as the source of truth for PACS, MWL, DICOM study, and artifact state, while Healthcare Lab owns local workflow intent, generated identifiers, sync attempts, and cross-system mapping metadata.

#### Scenario: Healthcare Lab creates a dcm4chee MWL order
- **WHEN** Healthcare Lab prepares a dcm4chee MWL/order creation request
- **THEN** the request represents a worklist/order item rather than a standalone patient master create operation
- **AND** Healthcare Lab records the local order identity and mapping metadata in its local ledger
- **AND** dcm4chee-arc remains authoritative for the MWL item exposed to APs and for returned DICOM study/artifact state

### Requirement: MWL order payload includes required patient demographics
Healthcare Lab SHALL include the agreed patient demographic attributes when creating a dcm4chee MWL/order.

#### Scenario: Patient demographics are mapped to DICOM MWL fields
- **WHEN** Healthcare Lab creates a dcm4chee MWL/order
- **THEN** the payload includes `00100010 Patient's Name`
- **AND** the payload includes `00100020 Patient ID`
- **AND** the payload includes `00100021 Issuer of Patient ID`
- **AND** the payload includes `00100030 Patient's Birth Date`
- **AND** the payload includes `00100040 Patient's Sex`
- **AND** the Patient ID is interpreted within the explicit issuer namespace

### Requirement: MWL order payload includes Scheduled Procedure Step identifiers
Healthcare Lab SHALL include the agreed Scheduled Procedure Step and order attributes needed by AP MWL query and result reconciliation.

#### Scenario: Order fields are mapped to DICOM MWL fields
- **WHEN** Healthcare Lab creates a dcm4chee MWL/order
- **THEN** the payload includes `00400001 Scheduled Station AE Title`
- **AND** the payload includes `00400009 Scheduled Procedure Step ID`
- **AND** the payload includes `0020000D Study Instance UID` when Healthcare Lab pre-allocates the study UID
- **AND** the payload includes `00080050 Accession Number`
- **AND** the payload includes `00401001 Requested Procedure ID`
- **AND** the payload includes `00741202 Worklist Label`

#### Scenario: Order fields use the selected dcm4chee profile
- **WHEN** Healthcare Lab prepares a future dcm4chee MWL/order request
- **THEN** it uses the selected dcm4chee connection profile for server identity
- **AND** it uses the profile MWL AE title and default Scheduled Station AE Title unless the workflow selects a more specific AP station
- **AND** it uses the profile DICOMweb and viewer settings for future query, verification, reconciliation, and viewer-link behavior

### Requirement: Healthcare Lab generated identifiers are sequential and namespace-aware
Healthcare Lab SHALL generate readable sequential identifiers for its local MWL workflow while keeping namespace boundaries explicit.

#### Scenario: Healthcare Lab generates MWL order identifiers
- **WHEN** Healthcare Lab creates a local dcm4chee MWL order intent
- **THEN** it assigns a sequential local order identifier such as `LAB-ORD-000001`
- **AND** it assigns a sequential accession number such as `ACC-000001`
- **AND** it assigns a sequential requested procedure ID such as `RP-000001`
- **AND** it assigns a sequential scheduled procedure step ID such as `SPS-000001`
- **AND** it assigns or references a Patient ID within an explicit issuer namespace
- **AND** it records the dcm4chee server identity that scopes the mapping

#### Scenario: Study Instance UID is generated as a valid DICOM UID
- **WHEN** Healthcare Lab generates `0020000D Study Instance UID`
- **THEN** it uses a configured DICOM UID root
- **AND** it appends a unique suffix such as date plus sequence
- **AND** it does not use a plain integer or local order ID as the complete DICOM UID
- **AND** it records the generated UID in the mapping ledger

### Requirement: Result reconciliation uses strongest available identifiers first
Healthcare Lab SHALL define deterministic matching precedence for reconciling AP C-STORE results stored in dcm4chee-arc back to local MWL orders.

#### Scenario: Returned DICOM study is matched to a local MWL order
- **WHEN** Healthcare Lab reconciles a returned DICOM study from dcm4chee-arc
- **THEN** it first matches by `0020000D Study Instance UID` when available
- **AND** otherwise matches by `00080050 Accession Number` within the dcm4chee server namespace
- **AND** otherwise matches by `00401001 Requested Procedure ID` and `00400009 Scheduled Procedure Step ID`
- **AND** weak fallback matching by Patient ID, issuer, Scheduled Station AE Title, modality/time window, and order status is treated as ambiguous unless exactly one active candidate exists

#### Scenario: Returned DICOM result validates patient identity
- **GIVEN** Healthcare Lab finds a result candidate by Accession Number, Requested Procedure ID, or Scheduled Procedure Step ID
- **WHEN** the returned DICOM metadata includes Patient ID or Issuer of Patient ID
- **THEN** Healthcare Lab compares those values with the canonical PACS/MWL ledger values
- **AND** it does not mark the result as matched when the patient identity conflicts
- **AND** it records a wrong-patient or identifier-mismatch diagnostic instead

### Requirement: Healthcare Lab creates dcm4chee MWL orders through MWL REST
Healthcare Lab SHALL create dcm4chee MWL/order records from Healthcare Lab ECG orders using the selected dcm4chee connection profile and the dcm4chee MWL REST creation path.

#### Scenario: Order creation posts a MWL item to dcm4chee
- **GIVEN** the selected dcm4chee profile is valid
- **AND** the Healthcare Lab order contains required patient and order data
- **WHEN** Healthcare Lab creates the dcm4chee MWL/order
- **THEN** it sends an `application/dicom+json` request to `POST /dcm4chee-arc/aets/{AETitle}/rs/mwlitems`
- **AND** `{AETitle}` is derived from the selected dcm4chee profile
- **AND** the request does not depend on manual dcm4chee UI entry

### Requirement: dcm4chee MWL creation records audit metadata
Healthcare Lab SHALL retain enough local metadata to debug and reconcile every dcm4chee MWL creation attempt.

#### Scenario: Creation attempt is recorded
- **WHEN** Healthcare Lab attempts to create a dcm4chee MWL/order
- **THEN** it records the local Healthcare Lab order identity
- **AND** it records the selected dcm4chee profile name and server identity
- **AND** it records generated Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, and Study Instance UID
- **AND** it records the outbound DICOM JSON request payload
- **AND** it records the dcm4chee response status, response body, attempt status, timestamps, and error details when available

### Requirement: dcm4chee MWL creation preserves local orders on failure
Healthcare Lab SHALL keep the local Healthcare Lab order even when dcm4chee MWL creation fails.

#### Scenario: dcm4chee creation fails after local order creation
- **GIVEN** Healthcare Lab has created a local order
- **WHEN** the dcm4chee MWL creation attempt fails
- **THEN** the local order remains available in Healthcare Lab
- **AND** the dcm4chee sync state is marked failed or pending separately from the local order
- **AND** the failure reason is visible through backend response metadata or a related status endpoint

### Requirement: Patient precondition failures are explicit
Healthcare Lab SHALL ensure the referenced Patient exists in dcm4chee before creating a dcm4chee MWL item, or clearly report that the Patient precondition failed.

#### Scenario: Patient is synced before MWL create
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **WHEN** the referenced local Patient is already synced to dcm4chee
- **THEN** Healthcare Lab may POST the MWL item to dcm4chee
- **AND** it records normal MWL create, read-back, and verification diagnostics

#### Scenario: Patient preflight sync succeeds
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **AND** the referenced local Patient is not yet synced to dcm4chee
- **WHEN** Healthcare Lab successfully syncs the Patient during MWL preflight
- **THEN** it may POST the MWL item to dcm4chee
- **AND** it records both the Patient sync attempt and the MWL create attempt

#### Scenario: Patient precondition fails
- **GIVEN** Healthcare Lab has a local DICOM MWL order intent
- **WHEN** the referenced Patient cannot be confirmed or synced in dcm4chee
- **THEN** Healthcare Lab does not POST the MWL item
- **AND** the local order remains available
- **AND** the MWL sync state identifies Patient sync or Patient missing as the root cause
- **AND** later MWL verification does not replace the Patient precondition failure with an empty-query diagnosis

### Requirement: Study Instance UID generation is configurable at runtime
Healthcare Lab SHALL generate valid DICOM Study Instance UIDs for dcm4chee MWL orders using a configured UID root.

#### Scenario: Runtime generates a Study Instance UID
- **WHEN** Healthcare Lab creates a dcm4chee MWL/order
- **THEN** it generates `0020000D Study Instance UID` using a configured dcm4chee UID root plus a unique suffix
- **AND** the generated UID is included in the MWL REST payload
- **AND** the generated UID is recorded in the local dcm4chee mapping/audit metadata

### Requirement: dcm4chee PACS/MWL ledger stores canonical order mappings
Healthcare Lab SHALL maintain a canonical local PACS/MWL ledger that maps each Healthcare Lab dcm4chee order to the dcm4chee identifiers used for MWL exposure and future result reconciliation.

#### Scenario: Canonical mapping is created for a dcm4chee order
- **WHEN** Healthcare Lab creates a local dcm4chee MWL order intent
- **THEN** it creates or updates one canonical PACS/MWL ledger record for the local Healthcare Lab order
- **AND** the ledger records the local Healthcare Lab order identity
- **AND** the ledger records the selected dcm4chee profile name and server identity
- **AND** the ledger records Patient ID and Issuer of Patient ID
- **AND** the ledger records AP-facing order identifiers when known
- **AND** the ledger records dcm4chee identifiers when known

### Requirement: dcm4chee PACS/MWL ledger separates mapping state from attempt audit
Healthcare Lab SHALL keep the canonical PACS/MWL mapping distinct from the audit history of dcm4chee create, read-back, retry, and failure attempts.

#### Scenario: Every create attempt is audited
- **WHEN** Healthcare Lab attempts to create or verify a dcm4chee MWL/order
- **THEN** it records an attempt audit entry with operation type, request target, raw request payload when available, response status/body when available, attempt status, timestamps, retry context, and error details
- **AND** the canonical PACS/MWL mapping remains the durable source for current reconciliation identifiers

#### Scenario: Mapping state records sync metadata
- **WHEN** Healthcare Lab updates the canonical PACS/MWL mapping
- **THEN** it records sync status
- **AND** it records last sync time when available
- **AND** it records retry count
- **AND** it records the latest error type, error text, and error payload when available

### Requirement: dcm4chee-generated identifiers are stored after read-back
Healthcare Lab SHALL persist identifiers that dcm4chee-arc generates, normalizes, or confirms once those identifiers are available from the create response or a read-back query.

#### Scenario: dcm4chee confirms generated or normalized identifiers
- **GIVEN** Healthcare Lab has created or attempted to create a dcm4chee MWL/order
- **WHEN** dcm4chee returns or read-back discovers Scheduled Procedure Step ID, Study Instance UID, Accession Number, Requested Procedure ID, Worklist Label, Patient ID, or Issuer of Patient ID
- **THEN** Healthcare Lab stores those values in the canonical PACS/MWL ledger
- **AND** Healthcare Lab preserves the raw response or read-back audit needed to debug the source of those values

#### Scenario: Read-back fails after creation
- **GIVEN** dcm4chee MWL/order creation has been attempted
- **WHEN** Healthcare Lab cannot read back dcm4chee identifiers
- **THEN** the local Healthcare Lab order remains available
- **AND** the canonical PACS/MWL ledger retains the strongest known identifiers
- **AND** the ledger sync status and attempt audit identify the read-back failure

### Requirement: dcm4chee MWL retry is idempotent per Healthcare Lab order
Healthcare Lab SHALL avoid creating duplicate dcm4chee MWL/orders for the same Healthcare Lab order during retry.

#### Scenario: Successful mapping already exists
- **GIVEN** a Healthcare Lab order has a successful canonical PACS/MWL mapping
- **WHEN** dcm4chee sync is requested again for that order
- **THEN** Healthcare Lab does not POST a duplicate dcm4chee MWL item
- **AND** it returns or refreshes the existing canonical mapping

#### Scenario: Failed mapping is retried
- **GIVEN** a Healthcare Lab order has a failed or pending dcm4chee mapping
- **WHEN** dcm4chee sync is retried
- **THEN** Healthcare Lab reuses the stable local identifiers already assigned to the canonical mapping
- **AND** it increments retry metadata
- **AND** it records the retry attempt in audit history

#### Scenario: Prior outcome is ambiguous
- **GIVEN** a Healthcare Lab order has an ambiguous previous dcm4chee attempt such as timeout or unknown response
- **WHEN** dcm4chee sync is retried
- **THEN** Healthcare Lab attempts to read back an existing dcm4chee MWL item using the strongest known identifiers before posting a new MWL item
- **AND** it avoids creating a duplicate item when the read-back confirms an existing dcm4chee record

### Requirement: Result reconciliation can find local orders from stored dcm4chee identifiers
Healthcare Lab SHALL provide deterministic local lookup behavior that can match future dcm4chee studies or AP C-STORE results back to the original Healthcare Lab order using the PACS/MWL ledger.

#### Scenario: Study is matched by strongest identifiers
- **WHEN** Healthcare Lab receives or queries dcm4chee study/result identifiers
- **THEN** it first matches by Study Instance UID when available
- **AND** otherwise matches by Accession Number within the dcm4chee profile/server namespace
- **AND** otherwise matches by Requested Procedure ID and Scheduled Procedure Step ID
- **AND** weak fallback matching by Patient ID, issuer, station, modality, or time window is treated as ambiguous unless exactly one active candidate exists

#### Scenario: Weak result candidates remain inspectable
- **GIVEN** Healthcare Lab queries dcm4chee and finds result candidates that cannot be matched by strong identifiers
- **WHEN** the candidates only match by weak patient, modality, station, or time-window signals
- **THEN** Healthcare Lab records the candidates as ambiguous or unlinked
- **AND** it exposes the relevant candidate metadata for operator debugging
- **AND** it does not update the local order as reconciled unless a deterministic match is established

### Requirement: dcm4chee MWL sync exposes retry and attempt APIs
Healthcare Lab SHALL expose explicit backend APIs that allow clients to retry dcm4chee MWL sync for a local Healthcare Lab order and inspect the dcm4chee sync attempt history for that order.

#### Scenario: Client retries a failed dcm4chee MWL sync
- **GIVEN** a local Healthcare Lab dcm4chee order has a failed or pending dcm4chee MWL sync state
- **WHEN** a client requests dcm4chee sync retry for that order
- **THEN** Healthcare Lab invokes the dcm4chee MWL sync workflow for the existing local order
- **AND** the retry reuses the canonical PACS/MWL mapping identifiers for that order
- **AND** the response includes the updated local order, latest dcm4chee mapping, latest attempt, and retryable metadata

#### Scenario: Retry does not duplicate confirmed dcm4chee orders
- **GIVEN** a local Healthcare Lab dcm4chee order already has a successful canonical PACS/MWL mapping
- **WHEN** a client requests dcm4chee sync retry for that order
- **THEN** Healthcare Lab does not POST a duplicate dcm4chee MWL item
- **AND** it returns the current successful mapping and order state

#### Scenario: Client inspects dcm4chee sync attempts
- **GIVEN** a local Healthcare Lab order has one or more dcm4chee MWL sync attempts
- **WHEN** a client requests the dcm4chee attempt history for that order
- **THEN** Healthcare Lab returns the attempts in a deterministic newest-first order
- **AND** each attempt includes operation type, status, request target, HTTP status when available, timestamps, error details, and retained response payload when available

### Requirement: dcm4chee MWL sync status is inspectable and action-oriented
Healthcare Lab SHALL expose dcm4chee MWL status metadata that is suitable for user inspection and retry decisions while preserving stored ledger status compatibility.

#### Scenario: Failed dcm4chee sync is visible and inspectable
- **GIVEN** dcm4chee MWL creation, read-back, or retry fails
- **WHEN** a client reads the local order or dcm4chee attempt history
- **THEN** Healthcare Lab exposes the current sync status
- **AND** it exposes the latest error type, error text, HTTP status, response payload, retry count, and relevant timestamps when available
- **AND** the local Healthcare Lab order remains available

#### Scenario: Retryable status is explicit
- **GIVEN** a dcm4chee MWL sync state can be retried
- **WHEN** a client reads the local order status
- **THEN** Healthcare Lab marks the dcm4chee MWL status as retryable
- **AND** it provides display-oriented status metadata that can be rendered as pending, synced, failed, retry needed, or reconciled without requiring clients to parse raw error text

#### Scenario: Non-retryable status remains explicit
- **GIVEN** dcm4chee MWL sync fails because of a patient precondition or invalid local/profile configuration
- **WHEN** a client reads the local order status
- **THEN** Healthcare Lab exposes the failure reason and retained diagnostics
- **AND** it does not present the state as retryable unless the local/profile data changes or the backend can safely retry the same request

### Requirement: DICOM order workspace supports dcm4chee retry and inspection
Healthcare Lab SHALL let users retry and inspect dcm4chee MWL sync from the DICOM order workspace.

#### Scenario: Retry action is shown for retryable dcm4chee orders
- **GIVEN** a DICOM MWL order has retryable dcm4chee sync metadata
- **WHEN** the order appears in the DICOM order list
- **THEN** the UI shows a retry action for that order
- **AND** activating the action calls the dcm4chee retry API
- **AND** the UI refreshes the order status after the retry completes

#### Scenario: User inspects latest sync details
- **GIVEN** a user selects a DICOM MWL order
- **WHEN** the order has dcm4chee MWL mapping or attempt metadata
- **THEN** the UI shows the latest dcm4chee sync status, retry count, timestamps, key identifiers, HTTP status, and latest error details when available

#### Scenario: User inspects attempt history
- **GIVEN** a user selects a DICOM MWL order
- **WHEN** dcm4chee attempt history is available
- **THEN** the UI shows each attempt with operation type, status, request target, HTTP status, timestamps, error details, and retained response payload when available

### Requirement: dcm4chee MWL queryability is explicitly verifiable
Healthcare Lab SHALL provide an explicit verification path that proves whether a Healthcare Lab-created dcm4chee MWL order is queryable from the configured dcm4chee MWL surface.

#### Scenario: Client verifies a dcm4chee MWL order
- **GIVEN** a local Healthcare Lab DICOM MWL order has a canonical PACS/MWL mapping
- **WHEN** a client requests MWL queryability verification for that order
- **THEN** Healthcare Lab queries the configured dcm4chee MWL endpoint using identifiers from the canonical mapping
- **AND** Healthcare Lab records a verification attempt separate from create, read-back, and retry attempts
- **AND** the local Healthcare Lab order remains available regardless of verification outcome

#### Scenario: Verification uses the configured MWL application
- **GIVEN** the selected dcm4chee profile exposes a MWL AE title and DICOMweb/MWL REST base URL
- **WHEN** Healthcare Lab runs automated MWL verification
- **THEN** it uses the configured MWL REST target for MWL item queries
- **AND** the local Docker profile can target the dcm4chee `WORKLIST` MWL web application
- **AND** profile or endpoint failures are reported as verification diagnostics rather than generic sync failures

### Requirement: MWL verification records proof metadata
Healthcare Lab SHALL retain enough metadata to prove which dcm4chee MWL item was found during verification.

#### Scenario: Verification finds the expected order
- **GIVEN** dcm4chee returns one or more MWL items for the verification query
- **WHEN** Healthcare Lab identifies an item matching the local order by strong identifiers
- **THEN** Healthcare Lab records verification status as verified
- **AND** it records the verification method, request target, query criteria, HTTP or tool status, verification timestamp, and selected match metadata
- **AND** the proof metadata includes available Patient ID, Issuer of Patient ID, Accession Number, Scheduled Station AE Title, Scheduled Procedure Step ID, Requested Procedure ID, Study Instance UID, and Worklist Label

#### Scenario: Verification response is non-empty but mismatched
- **GIVEN** dcm4chee returns MWL items for the verification query
- **WHEN** no returned item matches the expected local order identifiers strongly enough
- **THEN** Healthcare Lab records verification failure as an identifier mismatch
- **AND** it retains enough returned metadata to explain which fields did not match

#### Scenario: Verification response is ambiguous
- **GIVEN** dcm4chee returns multiple MWL items that match only weak criteria
- **WHEN** Healthcare Lab cannot identify exactly one expected order
- **THEN** Healthcare Lab records the result as ambiguous
- **AND** it does not mark the order as verified

### Requirement: MWL verification diagnostics are actionable
Healthcare Lab SHALL classify MWL verification failures into operator-actionable diagnostics.

#### Scenario: dcm4chee cannot be reached
- **GIVEN** the configured dcm4chee MWL endpoint is unavailable
- **WHEN** Healthcare Lab runs MWL verification
- **THEN** it records a dcm4chee connectivity diagnostic
- **AND** it preserves the request target and error detail needed to troubleshoot networking or service startup

#### Scenario: dcm4chee patient precondition is missing
- **GIVEN** dcm4chee indicates the MWL order cannot be created or queried because the referenced patient does not exist
- **WHEN** Healthcare Lab records verification or sync status
- **THEN** the diagnostic identifies the missing patient precondition
- **AND** the state is not presented as retryable unless patient data changes or patient creation/sync is completed

#### Scenario: MWL query returns no matching order
- **GIVEN** the configured dcm4chee MWL endpoint is reachable
- **WHEN** Healthcare Lab runs MWL verification and no MWL item is returned for the expected identifiers
- **THEN** it records an empty-result diagnostic
- **AND** it includes the query criteria and endpoint used for troubleshooting

### Requirement: DICOM order detail summarizes dcm4chee workflow status
Healthcare Lab SHALL show dcm4chee MWL/order and PACS result state from the selected DICOM order detail using operator-readable workflow statuses.

#### Scenario: User inspects selected DICOM order status
- **GIVEN** a local DICOM MWL order has dcm4chee mapping, verification, or result metadata
- **WHEN** the user selects the order in the Healthcare Lab order workspace
- **THEN** the UI shows MWL Sync status
- **AND** the UI shows MWL Queryable status
- **AND** the UI shows AP C-STORE Result status
- **AND** the UI shows Reconciliation status
- **AND** the UI keeps retry, verify, refresh, and attempt-history actions discoverable when applicable

#### Scenario: DICOM order diagnostics remain readable
- **GIVEN** dcm4chee sync, verification, result refresh, or reconciliation has failed or produced an ambiguous outcome
- **WHEN** the user inspects the selected order
- **THEN** Healthcare Lab shows the latest status, error type, error text, timestamps, and relevant identifiers without requiring the user to parse raw JSON
- **AND** raw request or response payloads remain available in expandable diagnostic sections when retained

### Requirement: Patient DICOM results use PACS-style hierarchical browsing
Healthcare Lab SHALL render patient dcm4chee DICOM results as structured DICOM-field tables with Study, Series, and Instance hierarchy where identifiers support it, while preserving Healthcare Lab visual styling.

#### Scenario: Matched results are grouped by order and study
- **GIVEN** a patient has dcm4chee DICOM result records matched to one or more local orders
- **WHEN** the Patient's inline Result section is rendered
- **THEN** the UI groups matched results by local order
- **AND** each order group shows expandable Study rows
- **AND** each Study row can expose nested Series rows
- **AND** each Series row can expose nested Instance rows

#### Scenario: DICOM result tables use dcm4chee-style metadata labels
- **GIVEN** a DICOM Study, Series, Instance, or diagnostic result row is visible
- **WHEN** the user reads the Patient's inline Result section
- **THEN** the result is presented through labeled table columns rather than a serialized object or raw JSON dump
- **AND** the table labels use DICOM/dcm4chee-style field names such as Accession Number, Study Instance UID, Series Instance UID, SOP Instance UID, Modality, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID
- **AND** Healthcare Lab workflow status labels remain separate from the DICOM metadata labels
- **AND** long values remain contained within the result-table region

#### Scenario: Unresolved result diagnostics remain visible
- **GIVEN** result refresh produces no-result, query-failed, ambiguous, duplicate, wrong-patient, missing-accession, or unlinked diagnostics
- **WHEN** the Patient's inline Result section is rendered
- **THEN** the UI shows those diagnostics as structured rows in an unresolved group
- **AND** it does not hide diagnostics merely because Study, Series, or Instance identifiers are incomplete
- **AND** it does not use raw object printing as the primary diagnostic presentation

### Requirement: DICOM result actions preserve viewer and retrieve access
Healthcare Lab SHALL expose dcm4chee viewer and retrieve actions from the PACS-style result browser when URLs are available.

#### Scenario: User opens a matched study
- **GIVEN** a matched Study row has a dcm4chee viewer URL
- **WHEN** the user activates the viewer action
- **THEN** Healthcare Lab opens the configured dcm4chee viewer link for that study

#### Scenario: User copies retrieve links
- **GIVEN** a Study, Series, or Instance row has a retrieve URL
- **WHEN** the user activates the copy/retrieve action
- **THEN** Healthcare Lab exposes the corresponding dcm4chee retrieve URL without changing the local reconciliation state

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

### Requirement: dcm4chee console is patient-centered
Healthcare Lab SHALL present the dcm4chee console around a dominant Patient list with independent Patient selection and Order/Result disclosure.

#### Scenario: Patient list uses the OIE-style workspace proportions
- **WHEN** the dcm4chee console is displayed at a supported desktop width
- **THEN** the Patient list occupies the dominant console area
- **AND** the list provides sufficient vertical space to review multiple Patients without appearing as a short summary card
- **AND** the page retains Healthcare Lab styling and responsive behavior

#### Scenario: User selects a Patient row
- **GIVEN** one or more DICOM Patients are listed
- **WHEN** the user activates a Patient row outside its disclosure control or row actions
- **THEN** Healthcare Lab selects that Patient
- **AND** it updates one Patient preview below the complete Patient list
- **AND** it does not expand or collapse the Patient's Order and Result sections

#### Scenario: User expands a Patient row
- **GIVEN** a DICOM Patient row is visible
- **WHEN** the user activates the leading disclosure control
- **THEN** Healthcare Lab expands or collapses that Patient's inline detail independently of Patient selection
- **AND** the control exposes its expanded state through accessible semantics
- **AND** expanded detail contains an Order section and a Result section for that Patient

#### Scenario: Patient Orders have one list presentation
- **WHEN** the dcm4chee Patient workspace is rendered
- **THEN** Orders are listed inside the expanded Patient detail
- **AND** applicable send, retry, verify, preview, or inspection actions remain discoverable from the Patient/order workflow
- **AND** the UI does not render a separate `MWL Selected Patient Orders` section

