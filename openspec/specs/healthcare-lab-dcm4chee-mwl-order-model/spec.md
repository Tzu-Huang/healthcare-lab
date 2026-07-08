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
Healthcare Lab SHALL distinguish dcm4chee patient precondition failures from generic MWL creation failures.

#### Scenario: dcm4chee rejects MWL creation because the patient is missing
- **GIVEN** the dcm4chee MWL REST endpoint rejects the request because the patient does not exist
- **WHEN** Healthcare Lab records the creation attempt
- **THEN** the attempt status identifies the missing-patient or patient-precondition failure
- **AND** the dcm4chee response body is retained for debugging
- **AND** the local Healthcare Lab order is not deleted

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

