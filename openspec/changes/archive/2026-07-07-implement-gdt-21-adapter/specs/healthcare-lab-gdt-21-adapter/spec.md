## ADDED Requirements

### Requirement: GDT 2.1 adapter boundary

Healthcare Lab SHALL provide a backend GDT 2.1 adapter boundary that translates between Healthcare Lab canonical data and raw GDT 2.1 messages without requiring callers to perform persistence operations.

#### Scenario: Adapter returns raw parsed canonical and validation data

- **WHEN** Healthcare Lab generates or parses a GDT 2.1 message through the adapter
- **THEN** the adapter returns the raw GDT text when available
- **AND** it returns parsed fields keyed by GDT field code while preserving repeated field values
- **AND** it returns canonical JSON for Healthcare Lab workflow use
- **AND** it returns structured validation errors and warnings

#### Scenario: Persistence delegates message translation

- **WHEN** Healthcare Lab creates a local GDT order or imports a GDT result
- **THEN** persistence code uses the adapter for GDT render parse validation and canonical mapping
- **AND** persistence remains responsible for database writes order matching attachments and events

### Requirement: GDT records use strict BDT byte-counted syntax

Healthcare Lab SHALL generate and parse GDT 2.1 records using strict byte-counted BDT line syntax.

#### Scenario: Generated record length includes the full envelope

- **WHEN** Healthcare Lab generates any GDT 2.1 record
- **THEN** the first three bytes contain the encoded byte length of that record
- **AND** that length includes the three-byte length prefix
- **AND** the four-byte field tag
- **AND** the encoded value
- **AND** the trailing CRLF bytes

#### Scenario: Malformed record syntax is rejected

- **WHEN** Healthcare Lab parses a GDT 2.1 message with a nonnumeric length prefix malformed tag truncated record or missing CRLF
- **THEN** the adapter rejects the message with a structured format error
- **AND** the invalid message is not accepted as a valid canonical result

### Requirement: GDT 8100 total length is generated and validated

Healthcare Lab SHALL treat field `8100` as the full GDT dataset byte length.

#### Scenario: Generated 8100 includes every record

- **WHEN** Healthcare Lab generates a GDT 2.1 dataset
- **THEN** field `8100` equals the encoded byte length of the full dataset
- **AND** the total includes the `8000` record
- **AND** the `8100` record itself
- **AND** every remaining record
- **AND** every record CRLF

#### Scenario: Mismatched 8100 is rejected

- **WHEN** Healthcare Lab parses a GDT 2.1 message whose `8100` value does not equal the actual encoded dataset byte length
- **THEN** the adapter rejects the message with a structured validation error

### Requirement: GDT 6302 requests are generated from canonical order data

Healthcare Lab SHALL generate GDT 2.1 `6302` New Test Request messages from Healthcare Lab canonical order data.

#### Scenario: ECG01 request is generated

- **WHEN** Healthcare Lab has canonical local order data for a 12-lead resting ECG
- **THEN** the adapter generates a GDT `6302` message
- **AND** the message contains `8000=6302`
- **AND** the message contains `9218=02.10`
- **AND** the message contains patient fields `3000` `3101` `3102` and `3103`
- **AND** the message contains `8402=EKG01`

#### Scenario: Generated request remains compatible with existing order API

- **WHEN** Healthcare Lab creates a local GDT ECG order through the existing order API
- **THEN** the response still exposes the generated raw `6302` message through the compatible `payload` field
- **AND** the underlying message record stores raw parsed canonical and validation data

### Requirement: GDT 6310 results are parsed into canonical ECG results

Healthcare Lab SHALL parse GDT 2.1 `6310` Test Data Transfer messages into canonical ECG result JSON.

#### Scenario: ECG measurements are normalized

- **WHEN** Healthcare Lab parses a valid GDT `6310` result containing repeated measurement groups
- **AND** each measurement group uses `8410` for Test-ID `8420` for value and `8421` for unit
- **THEN** the canonical result contains measurements normalized by canonical measurement key
- **AND** the adapter supports at least `HR` `PR` `QRS` `QT` `QTC` `P_AXIS` `QRS_AXIS` and `T_AXIS`

#### Scenario: Result status and text are preserved

- **WHEN** Healthcare Lab parses a GDT `6310` result containing `8418` `6227` or `6228`
- **THEN** `8418` is preserved as result status
- **AND** `6227` values are preserved as comments
- **AND** `6228` values are preserved as formatted result text

#### Scenario: Result demographics are optional

- **WHEN** Healthcare Lab parses a GDT `6310` result that includes `3000` but omits `3101` or `3102`
- **THEN** the adapter does not reject the result solely because the optional result name fields are absent
- **AND** the canonical patient data preserves the available `3000` value for linkage

### Requirement: GDT adapter validation notices are structured by severity

Healthcare Lab SHALL classify adapter validation notices into structured errors and warnings.

#### Scenario: Format and required-field failures reject the message

- **WHEN** Healthcare Lab detects a format failure in the `000-099` range
- **OR** detects a required-field or required-context failure in the `200-299` range
- **THEN** the adapter reports a structured error
- **AND** the invalid message is rejected

#### Scenario: Recoverable content and semantic issues are warnings

- **WHEN** Healthcare Lab detects a recoverable content issue in the `100-199` range
- **OR** detects a semantic or context issue in the `300-399` range
- **THEN** the adapter reports a structured warning where possible
- **AND** the raw parsed and canonical data remain available when the message can still be interpreted safely

#### Scenario: Unknown vendor measurement IDs are preserved

- **WHEN** Healthcare Lab parses a `6310` result with a `8410` Test-ID that is not in the default measurement mapping
- **THEN** the parsed field value is preserved
- **AND** the adapter records a warning instead of silently dropping the measurement
