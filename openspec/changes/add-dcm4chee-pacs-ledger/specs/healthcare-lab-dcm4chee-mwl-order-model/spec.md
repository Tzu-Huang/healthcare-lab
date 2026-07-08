## ADDED Requirements

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
