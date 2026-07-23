## MODIFIED Requirements

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
