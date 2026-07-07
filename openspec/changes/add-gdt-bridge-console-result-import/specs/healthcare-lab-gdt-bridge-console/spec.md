## ADDED Requirements

### Requirement: GDT console is patient-centered

Healthcare Lab SHALL provide a dedicated GDT console that follows the same
patient-centered workflow model as the OIE console while remaining specific to
GDT order/result handling.

#### Scenario: User opens the GDT console

- **WHEN** a user selects the GDT navigation item
- **THEN** Healthcare Lab shows local GDT patients
- **AND** selecting a patient shows that patient's GDT ECG orders
- **AND** selecting an order or result updates the detail/preview panel without leaving the GDT console

#### Scenario: GDT console does not change non-GDT boundaries

- **WHEN** Healthcare Lab displays the GDT console
- **THEN** the console is limited to GDT patient context, `6302` requests, `6310` results, artifact references, and local audit history
- **AND** it does not add HL7, FHIR, or DICOM AP-simulator result packaging workflows

### Requirement: GDT orders can be written to the bridge outbox

Healthcare Lab SHALL allow a local GDT ECG order to be exported as a GDT `6302`
request file in the configured shared-folder bridge outbox.

#### Scenario: User writes an order request

- **WHEN** a user selects a local GDT ECG order
- **AND** activates `Write 6302`
- **THEN** Healthcare Lab writes the order's raw `6302` payload to the bridge outbox
- **AND** the file is written with partial-file protection such as temp-file plus rename
- **AND** Healthcare Lab records export path/status details and an event for the order

#### Scenario: Outbox write fails

- **WHEN** Healthcare Lab cannot write the `6302` outbox file
- **THEN** the order remains visible
- **AND** the failure is surfaced in the GDT console
- **AND** diagnostic details are preserved for developer/operator review

### Requirement: GDT results can be imported from the bridge inbox

Healthcare Lab SHALL list inbound GDT files from the configured bridge inbox and
import selected `6310` result files into local GDT result persistence.

#### Scenario: User imports an inbound result file

- **WHEN** a valid inbound `6310` file is available
- **AND** the user imports it
- **THEN** Healthcare Lab stores the original raw GDT text
- **AND** it stores parsed fields and canonical result data
- **AND** it matches the result to a local GDT order when an unambiguous order identifier is present
- **AND** it records import, match or unmatched, attachment, and status events

#### Scenario: Result file cannot be parsed

- **WHEN** an inbound GDT file cannot be parsed as an importable `6310`
- **THEN** Healthcare Lab marks the file/import as errored
- **AND** it preserves diagnostic details
- **AND** it does not discard other pending inbound files

### Requirement: Artifact references are stored without blocking result import

Healthcare Lab SHALL persist GDT result artifact metadata and references from
`6302-6305` artifact groups without requiring referenced files to be present.

#### Scenario: Result contains PDF and DICOM artifact references

- **WHEN** Healthcare Lab imports a `6310` result containing artifact groups
- **THEN** it maps `6303` to artifact format
- **AND** it maps `6304` to artifact description
- **AND** it maps `6305` to the artifact reference path URL or UNC value
- **AND** it stores each artifact as a normalized attachment record linked to the result/order/message

#### Scenario: Referenced artifact target is missing

- **WHEN** a `6310` result references a PDF DICOM or other artifact target that Healthcare Lab cannot verify
- **THEN** Healthcare Lab still imports the result when the GDT message itself is parseable
- **AND** it records a warning/status detail for the missing or unverifiable artifact reference
- **AND** the GDT console shows the artifact reference as copyable text

### Requirement: GDT console displays result details and artifacts

Healthcare Lab SHALL display imported ECG result details in the GDT console.

#### Scenario: User selects an imported result

- **WHEN** a user selects an imported GDT `6310` result
- **THEN** the GDT console shows canonical ECG measurements including HR PR QRS QT and QTC when present
- **AND** it shows result status and text from result fields such as `8418`, `6220`, `6227`, and `6228`
- **AND** it shows artifact references with format description and reference/path/URL
- **AND** it provides access to the raw `6310` payload

#### Scenario: Artifact reference is usable from the browser

- **WHEN** an artifact reference can be safely represented as a URL or download target
- **THEN** the GDT console offers an open or download action
- **AND** DICOM artifacts are treated as downloadable/reference files only
- **AND** Healthcare Lab does not parse or render DICOM content in this change

### Requirement: Demo result exercises the GDT import path

Healthcare Lab SHALL provide a deterministic demo result action for a selected
local GDT order.

#### Scenario: User creates a demo result

- **WHEN** a user selects a local GDT ECG order
- **AND** activates `Demo Result`
- **THEN** Healthcare Lab creates deterministic `6310` result content for that order
- **AND** the demo result includes HR PR QRS QT and QTC measurements
- **AND** the demo result includes PDF and DICOM artifact references
- **AND** the demo result is persisted through the same import/display path as other GDT results
