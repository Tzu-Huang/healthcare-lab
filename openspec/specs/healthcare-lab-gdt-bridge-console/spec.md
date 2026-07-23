# healthcare-lab-gdt-bridge-console Specification

## Purpose
Define Healthcare Lab's patient-centered GDT bridge console for local ECG order
export, inbound `6310` result import, reference-only artifact display, and
raw/canonical GDT inspection.
## Requirements
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

Healthcare Lab SHALL allow a local GDT ECG order to be exported as a GDT `6302` request file in the outbox resolved from the effective persisted GDT Bridge profile.

#### Scenario: User writes an order request

- **WHEN** a user selects a local GDT ECG order
- **AND** activates `Write 6302`
- **THEN** Healthcare Lab writes the order's raw `6302` payload to the effective profile's bridge outbox
- **AND** the file is written with partial-file protection such as temp-file plus rename
- **AND** Healthcare Lab records export path/status details and an event for the order

#### Scenario: Outbox write fails

- **WHEN** Healthcare Lab cannot write the `6302` outbox file
- **THEN** the order remains visible
- **AND** the failure is surfaced in the GDT console
- **AND** diagnostic details are preserved for developer/operator review without exposing PHI-bearing filenames

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

### Requirement: GDT bridge inbound files can be acquired automatically

Healthcare Lab SHALL provide an operator-controlled background watcher constructed from the effective persisted GDT Bridge profile that imports eligible GDT `6310` result files without requiring a user to select each file manually.

#### Scenario: Persisted profile enables automatic GDT import

- **WHEN** application startup resolves an enabled effective GDT Bridge profile
- **THEN** Healthcare Lab starts the watcher deterministically with that profile snapshot
- **AND** periodically scans its resolved inbound folder
- **AND** imports eligible `6310` result files through the same persistence path as manual import
- **AND** exposes bounded watcher running state, poll interval, last run summary, and last error

#### Scenario: Persisted profile disables automatic GDT import

- **WHEN** the effective GDT Bridge profile is disabled
- **THEN** Healthcare Lab does not run background scans
- **AND** manual selected-file import remains available when its path is otherwise usable
- **AND** the watcher status reports that automatic import is disabled

#### Scenario: Profile changes between scans

- **WHEN** a profile mutation becomes effective while the watcher is running
- **THEN** an active scan completes against one immutable profile snapshot
- **AND** the next scan uses the newly activated profile

### Requirement: Automatic inbound import processes files safely and in FIFO order

Healthcare Lab SHALL process bridge inbound files in FIFO order and avoid
reading partial or internally managed files.

#### Scenario: Multiple inbound result files are pending

- **WHEN** multiple eligible inbound GDT files are present
- **THEN** Healthcare Lab processes them by creation date and time when available
- **AND** falls back to a deterministic timestamp and filename order when creation time is unavailable or unreliable
- **AND** continues processing remaining files when one file fails

#### Scenario: A device is still writing a file

- **WHEN** an inbound candidate is temporary, hidden, internally marked as processing, or not stable yet
- **THEN** Healthcare Lab skips that file for the current scan
- **AND** does not attempt to parse or move it until a later scan finds it eligible

#### Scenario: Healthcare Lab claims a file for import

- **WHEN** Healthcare Lab begins importing an eligible file
- **THEN** it first claims the file using a same-volume rename or move into processing state
- **AND** if the claim fails because the file disappeared or is locked, the scan records a skip or retry outcome without failing the entire batch

### Requirement: Inbound result files have configurable post-success handling

Healthcare Lab SHALL use the effective persisted GDT Bridge profile to select standards-oriented delete behavior or lab-oriented archive behavior for successfully imported bridge result files.

#### Scenario: Delete mode is effective

- **WHEN** Healthcare Lab successfully imports a claimed inbound `6310` file
- **AND** the effective profile's import success mode is delete
- **THEN** Healthcare Lab deletes the exchange file after persistence succeeds
- **AND** retains the raw GDT text in local message persistence

#### Scenario: Archive mode is effective

- **WHEN** Healthcare Lab successfully imports a claimed inbound `6310` file
- **AND** the effective profile's import success mode is archive
- **THEN** Healthcare Lab moves the exchange file to the effective profile's archive folder
- **AND** labels archive mode in documentation or UI as a PoC/debug behavior that differs from strict GDT exchange deletion

#### Scenario: Import fails

- **WHEN** Healthcare Lab cannot parse or persist a claimed inbound file
- **THEN** Healthcare Lab moves the file to the effective profile's error folder when possible
- **AND** records diagnostic details without discarding other pending inbound files

### Requirement: GDT filename binding filters are configurable

Healthcare Lab SHALL enforce the filename binding profile and sender/receiver identities from the effective persisted GDT Bridge profile while retaining permissive behavior for lab demos.

#### Scenario: GDT 3.5 binding is effective

- **WHEN** the effective filename binding profile is GDT 3.5
- **THEN** Healthcare Lab only treats filenames matching `<receiver>_<sender>_<sequence>.GDT` as eligible
- **AND** the receiver and sender abbreviations come from the same effective profile snapshot

#### Scenario: GDT 2.1 binding is effective

- **WHEN** the effective filename binding profile is GDT 2.1
- **THEN** Healthcare Lab only treats configured legacy recipient/sender filenames or allowed sequence-extension variants as eligible

#### Scenario: Permissive lab binding is effective

- **WHEN** the effective filename binding profile is permissive
- **THEN** Healthcare Lab may treat any otherwise eligible `.gdt` file as importable

### Requirement: Ambiguous patient-only results are not auto-attached to orders

Healthcare Lab SHALL avoid automatically matching a GDT result to the latest
order for a patient when no unambiguous order identifier is present.

#### Scenario: Result contains patient number but no order identifier

- **WHEN** Healthcare Lab imports a `6310` result with a known `3000` patient number
- **AND** no supported order identifier matches a persisted GDT order
- **THEN** Healthcare Lab preserves the patient context when available
- **AND** marks the result as unmatched or review-needed
- **AND** does not attach it to the latest order for that patient
