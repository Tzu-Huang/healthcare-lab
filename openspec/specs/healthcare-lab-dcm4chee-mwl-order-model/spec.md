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

