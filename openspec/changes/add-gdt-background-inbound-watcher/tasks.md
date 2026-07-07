## 1. Import Service Contract

- [ ] 1.1 Extract selected-file bridge import into a shared batch import service.
- [ ] 1.2 Return structured imported/skipped/failure summaries for manual and automatic imports.
- [ ] 1.3 Add configurable success handling for archive mode and delete mode.
- [ ] 1.4 Preserve current raw/parsed/canonical/result/event behavior for imported `6310` messages.

## 2. Safe File Acquisition

- [ ] 2.1 Implement inbound candidate discovery with `.gdt` filtering and temporary/internal file skipping.
- [ ] 2.2 Implement FIFO ordering by creation time with deterministic fallback.
- [ ] 2.3 Add file stability checks before import.
- [ ] 2.4 Claim files with same-volume rename before reading.
- [ ] 2.5 Route successful files to archive/delete and failed files to error without overwriting collisions.

## 3. Binding and Matching

- [ ] 3.1 Add filename binding profile configuration for permissive, GDT 2.1 legacy, and GDT 3.5 formats.
- [ ] 3.2 Apply receiver/sender/sequence binding checks during automatic and manual file import.
- [ ] 3.3 Keep patient-only `6310` results unmatched or review-needed instead of auto-attaching to latest order.
- [ ] 3.4 Document future precedence for GDT 3.5 `8314` and `8408` identifiers.

## 4. Watcher Lifecycle

- [ ] 4.1 Add an in-process GDT bridge inbound watcher with start, stop, status, and configure behavior.
- [ ] 4.2 Add watcher lifecycle APIs under `/api/gdt/bridge/watcher/*`.
- [ ] 4.3 Reject bridge path changes while automatic import is running.
- [ ] 4.4 Expose last run summary and last error through watcher status.

## 5. Console and Documentation

- [ ] 5.1 Add GDT console controls and status display for automatic import.
- [ ] 5.2 Keep manual selected-file import available.
- [ ] 5.3 Update GDT bridge docs to distinguish standards-oriented delete mode from PoC archive mode.
- [ ] 5.4 Document FIFO, temporary-file, binding, and patient-only matching behavior.

## 6. Verification

- [ ] 6.1 Add API/store tests for batch import, FIFO order, temp/unstable skip, archive/delete, error routing, and binding filters.
- [ ] 6.2 Add watcher lifecycle tests.
- [ ] 6.3 Add frontend contract tests for automatic import controls/status.
- [ ] 6.4 Run Python unit tests, Python compile checks, frontend syntax checks, and OpenSpec validation.
