## 1. Import Service Contract

- [x] 1.1 Extract selected-file bridge import into a shared batch import service.
- [x] 1.2 Return structured imported/skipped/failure summaries for manual and automatic imports.
- [x] 1.3 Add configurable success handling for archive mode and delete mode.
- [x] 1.4 Preserve current raw/parsed/canonical/result/event behavior for imported `6310` messages.

## 2. Safe File Acquisition

- [x] 2.1 Implement inbound candidate discovery with `.gdt` filtering and temporary/internal file skipping.
- [x] 2.2 Implement FIFO ordering by creation time with deterministic fallback.
- [x] 2.3 Add file stability checks before import.
- [x] 2.4 Claim files with same-volume rename before reading.
- [x] 2.5 Route successful files to archive/delete and failed files to error without overwriting collisions.

## 3. Binding and Matching

- [x] 3.1 Add filename binding profile configuration for permissive, GDT 2.1 legacy, and GDT 3.5 formats.
- [x] 3.2 Apply receiver/sender/sequence binding checks during automatic and manual file import.
- [x] 3.3 Keep patient-only `6310` results unmatched or review-needed instead of auto-attaching to latest order.
- [x] 3.4 Document future precedence for GDT 3.5 `8314` and `8408` identifiers.

## 4. Watcher Lifecycle

- [x] 4.1 Add an in-process GDT bridge inbound watcher with start, stop, status, and configure behavior.
- [x] 4.2 Add watcher lifecycle APIs under `/api/gdt/bridge/watcher/*`.
- [x] 4.3 Reject bridge path changes while automatic import is running.
- [x] 4.4 Expose last run summary and last error through watcher status.

## 5. Console and Documentation

- [x] 5.1 Add GDT console controls and status display for automatic import.
- [x] 5.2 Keep manual selected-file import available.
- [x] 5.3 Update GDT bridge docs to distinguish standards-oriented delete mode from PoC archive mode.
- [x] 5.4 Document FIFO, temporary-file, binding, and patient-only matching behavior.

## 6. Verification

- [x] 6.1 Add API/store tests for batch import, FIFO order, temp/unstable skip, archive/delete, error routing, and binding filters.
- [x] 6.2 Add watcher lifecycle tests.
- [x] 6.3 Add frontend contract tests for automatic import controls/status.
- [x] 6.4 Run Python unit tests, Python compile checks, frontend syntax checks, and OpenSpec validation.
