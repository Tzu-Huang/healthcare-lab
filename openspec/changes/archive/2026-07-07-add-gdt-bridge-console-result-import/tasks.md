## 1. Contract and Data Model

- [x] 1.1 Confirm current GDT bridge folder config and add any missing import/export state needed for outbox/inbound/archive/error visibility.
- [x] 1.2 Extend normalized GDT attachment/result metadata to preserve `6302-6305` artifact group details, especially `6305` reference/path/URL.
- [x] 1.3 Add non-blocking artifact warning/status fields so missing PDF/DICOM targets do not prevent result import.

## 2. Bridge File Operations

- [x] 2.1 Add a `Write 6302` backend operation for selected GDT orders using temp-file plus rename.
- [x] 2.2 Add inbound `.gdt` file listing for the configured bridge inbound folder.
- [x] 2.3 Add selected-file `6310` import with raw payload retention, match status, archive/error handling, and lifecycle events.
- [x] 2.4 Keep raw/pasted `6310` import compatible with the existing `/api/gdt/results` contract.

## 3. Demo Result

- [x] 3.1 Add deterministic demo `6310` generation for a selected order.
- [x] 3.2 Include HR, PR, QRS, QT, QTC, result text, PDF artifact reference, and DICOM artifact reference in the demo result.
- [x] 3.3 Route demo import through the same persistence and display path as real imports.

## 4. GDT Console UI

- [x] 4.1 Add a sidebar `GDT` view using an OIE-like patient-centered layout.
- [x] 4.2 Render GDT patients, selected patient summary, GDT orders, bridge inbox files, results, artifacts, and preview/detail panels.
- [x] 4.3 Add order actions for `Preview 6302`, `Write 6302`, `Demo Result`, and `Import 6310`.
- [x] 4.4 Display canonical measurements, result status/text, raw `6310`, artifact references, and event trail.
- [x] 4.5 Provide copy/open/download affordances for artifact references where practical without parsing DICOM or PDF bytes.

## 5. Verification

- [x] 5.1 Add store/API tests for outbox write, inbound import, non-blocking missing artifact warnings, and artifact group mapping.
- [x] 5.2 Add API/UI contract tests for the GDT console view and actions.
- [x] 5.3 Run Python unit tests, Python compile checks, frontend syntax checks, and OpenSpec validation.
