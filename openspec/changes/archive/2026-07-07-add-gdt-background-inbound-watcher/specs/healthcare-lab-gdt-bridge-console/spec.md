## ADDED Requirements

### Requirement: GDT bridge inbound files can be acquired automatically

Healthcare Lab SHALL provide an operator-controlled background watcher that
imports eligible GDT `6310` result files from the configured bridge inbound
folder without requiring a user to select each file manually.

#### Scenario: User enables automatic GDT import

- **WHEN** a user starts the GDT bridge inbound watcher
- **THEN** Healthcare Lab periodically scans the configured bridge inbound folder
- **AND** imports eligible `6310` result files through the same persistence path as manual import
- **AND** exposes watcher running state, poll interval, last run summary, and last error

#### Scenario: User disables automatic GDT import

- **WHEN** a user stops the GDT bridge inbound watcher
- **THEN** Healthcare Lab stops background scans
- **AND** manual selected-file import remains available
- **AND** the watcher status reports that automatic import is not running

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

Healthcare Lab SHALL support both standards-oriented delete behavior and
lab-oriented archive behavior for successfully imported bridge result files.

#### Scenario: Delete mode is enabled

- **WHEN** Healthcare Lab successfully imports a claimed inbound `6310` file
- **AND** the bridge import success mode is delete
- **THEN** Healthcare Lab deletes the exchange file after persistence succeeds
- **AND** retains the raw GDT text in local message persistence

#### Scenario: Archive mode is enabled

- **WHEN** Healthcare Lab successfully imports a claimed inbound `6310` file
- **AND** the bridge import success mode is archive
- **THEN** Healthcare Lab moves the exchange file to the configured archive folder
- **AND** labels archive mode in documentation or UI as a PoC/debug behavior that differs from strict GDT exchange deletion

#### Scenario: Import fails

- **WHEN** Healthcare Lab cannot parse or persist a claimed inbound file
- **THEN** Healthcare Lab moves the file to the configured error folder when possible
- **AND** records diagnostic details without discarding other pending inbound files

### Requirement: GDT filename binding filters are configurable

Healthcare Lab SHALL allow inbound bridge import to enforce a configured
filename binding profile while retaining permissive behavior for lab demos.

#### Scenario: GDT 3.5 binding is configured

- **WHEN** the filename binding profile is GDT 3.5
- **THEN** Healthcare Lab only treats filenames matching `<receiver>_<sender>_<sequence>.GDT` as eligible
- **AND** the receiver and sender abbreviations come from bridge configuration

#### Scenario: GDT 2.1 binding is configured

- **WHEN** the filename binding profile is GDT 2.1
- **THEN** Healthcare Lab only treats configured legacy recipient/sender filenames or allowed sequence-extension variants as eligible

#### Scenario: Permissive lab binding is configured

- **WHEN** the filename binding profile is permissive
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
