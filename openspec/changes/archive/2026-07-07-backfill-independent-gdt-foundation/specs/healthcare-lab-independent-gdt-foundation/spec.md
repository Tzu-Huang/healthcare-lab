## ADDED Requirements

### Requirement: Healthcare Lab owns independent GDT patient numbers

Healthcare Lab SHALL generate and persist a local GDT patient number for field `3000` without relying on OpenEMR or assuming the MRN is the GDT patient number.

#### Scenario: GDT patient number is generated

- **WHEN** Healthcare Lab creates a local patient context for a GDT workflow
- **AND** no manual GDT patient number override is supplied
- **THEN** Healthcare Lab assigns a stable local GDT patient number
- **AND** generated GDT order/result payloads use that number in field `3000`
- **AND** the original MRN remains stored separately from the GDT patient number

#### Scenario: GDT patient number is manually overridden

- **WHEN** a user or backend caller supplies a manual GDT patient number override
- **THEN** Healthcare Lab validates and persists the override
- **AND** generated GDT order/result payloads use the override as the effective field `3000` value
- **AND** Healthcare Lab records that an override was applied

#### Scenario: GDT patient number is snapshotted on workflow records

- **WHEN** Healthcare Lab creates a GDT order, message, or result record
- **THEN** the effective GDT field `3000` value is snapshotted on that workflow record
- **AND** later patient edits do not rewrite the historical snapshot

### Requirement: GDT orders use an independent persistence foundation

Healthcare Lab SHALL persist dashboard-created GDT ECG orders in an OpenEMR-independent data model that can support future export, import, result, attachment, and audit workflows.

#### Scenario: Dashboard-created order remains compatible

- **WHEN** a caller creates a local GDT ECG order through the ZAC-22 API contract
- **THEN** Healthcare Lab persists the order through the independent GDT foundation
- **AND** the API response still includes the compatible order number, status, fixed `8402=EKG01`, summary, raw payload alias, and timestamps expected by the dashboard flow

#### Scenario: OpenEMR is unavailable

- **WHEN** OpenEMR configuration is missing or OpenEMR is not running
- **AND** a caller creates a local GDT patient and ECG order
- **THEN** Healthcare Lab persists the records successfully
- **AND** no OpenEMR database query or runtime dependency is required

### Requirement: GDT messages store raw, parsed, and canonical representations separately

Healthcare Lab SHALL store raw GDT text separately from parsed field JSON and canonical workflow JSON for generated and imported GDT messages.

#### Scenario: Outbound order message is stored in three representations

- **WHEN** Healthcare Lab generates a GDT `6302` order message
- **THEN** it stores the raw GDT text as `raw_gdt_text`
- **AND** it stores parsed fields as structured JSON keyed by GDT field code
- **AND** it stores canonical workflow JSON containing patient, order, test, and correlation data

#### Scenario: Inbound result message is stored in three representations

- **WHEN** Healthcare Lab receives or imports a GDT `6310` result message
- **THEN** it stores the raw GDT text as `raw_gdt_text`
- **AND** it stores parsed fields as structured JSON keyed by GDT field code
- **AND** it stores canonical workflow JSON containing patient, order, result, attachment, and correlation data

### Requirement: GDT result records are persisted and matched

Healthcare Lab SHALL persist GDT `6310` result messages and match them to local GDT ECG orders when possible.

#### Scenario: Result matches a local GDT order

- **WHEN** Healthcare Lab imports a valid GDT `6310` result with a local order or test identifier matching a persisted GDT order
- **THEN** Healthcare Lab links the result to that order
- **AND** records a matched result status
- **AND** keeps the raw, parsed, and canonical result data available for backend inspection

#### Scenario: Result cannot be matched

- **WHEN** Healthcare Lab imports a valid GDT `6310` result that does not match a local GDT order
- **THEN** Healthcare Lab persists the result
- **AND** marks it as unmatched with diagnostic details
- **AND** does not discard the raw GDT text

### Requirement: GDT attachments are normalized records

Healthcare Lab SHALL persist GDT attachments as normalized records instead of relying only on a single attachment URL field.

#### Scenario: Multiple artifacts are attached to one GDT result

- **WHEN** a GDT result references both a PDF report and an XML or waveform artifact
- **THEN** Healthcare Lab stores each artifact as a separate attachment record
- **AND** each record identifies its role, path or URL, content type when available, and related order or message

#### Scenario: Legacy attachment URL remains compatible

- **WHEN** a ZAC-22-compatible order request includes `attachmentUrl`
- **THEN** Healthcare Lab stores it as a normalized attachment record
- **AND** the order response can still expose `attachmentUrl` for compatibility

### Requirement: GDT workflow events provide audit-capable history

Healthcare Lab SHALL record timestamped workflow events for important GDT lifecycle actions.

#### Scenario: Order workflow events are recorded

- **WHEN** Healthcare Lab creates a GDT patient context, creates an order, generates a `6302` message, changes status, or records an error
- **THEN** it records timestamped workflow events with enough details to reconstruct the backend lifecycle

#### Scenario: Result workflow events are recorded

- **WHEN** Healthcare Lab imports a `6310` result, matches or fails to match it, or registers attachments
- **THEN** it records timestamped workflow events linked to the relevant order, message, result, or attachment records
