---
change: add-gdt-bridge-console-result-import
date: 2026-07-07
issue: ZAC-24
---

## Context

ZAC-24 promotes the local GDT ECG workflow from backend-capable order/result APIs into a patient-centered GDT bridge console. The change stays inside Healthcare Lab's local GDT boundary: local order creation, shared-folder `6302` export, inbound `6310` import, reference-only artifact records, and dashboard display.

## Implementation

- Added GDT bridge APIs for workbench data, inbound `.gdt` listing, selected-file `6310` import, selected-order `6302` outbox write, and deterministic demo result creation.
- Extended GDT result canonical metadata and attachment records so `6302-6305` artifact groups preserve `6305` as the original artifact reference.
- Added non-blocking artifact status/details for missing PDF/DICOM references.
- Added a sidebar `GDT` console with patient, order, inbox, result, artifact, and raw payload/detail panels.
- Preserved the existing dashboard `ECG Order` action by restoring the order form entrypoint in GDT mode after review identified the regression.
- Added store/API/frontend contract tests for bridge import/export, demo result, warning artifacts, workbench shape, and dashboard GDT order entry.

## Decisions

- GDT bridge file I/O uses CP1252 bytes rather than text-mode reads/writes so byte-counted GDT records keep their `\r\n` envelopes intact on Windows.
- Artifact references remain metadata only; PDF/DICOM bytes are not copied or parsed.
- Missing artifact targets produce warning status details and do not block `6310` import.
- The GDT console is the primary inspection and bridge-operation surface, while the existing Order view remains the dashboard-started creation surface.

## Validation Plan

- Compile backend Python modules.
- Run frontend JavaScript syntax checks.
- Run Python unit/API tests.
- Validate the OpenSpec change strictly.
- Check diff whitespace.

## Verification

### Round 1 (2026-07-07)

- pass: `python -m py_compile app.py backend\lab_store.py`
- pass: `node --check frontend\static\app.js`
- pass: `python -m unittest discover -s tests` (`58` tests)
- pass: `openspec validate add-gdt-bridge-console-result-import --strict`
- pass: `git diff --check`

## Code Review

### Round 1 (2026-07-07)

- review file: `openspec/changes/add-gdt-bridge-console-result-import/review/2026-07-07_codex-review.md`
- verdict: no issues found after fix commit `0e85425`
- previous finding resolved: dashboard `ECG Order` now sets GDT mode and opens `order-view`, preserving creatable GDT order entry.
- residual risk: manual browser walkthrough was not run; artifact open/copy behavior remains covered by static/API/unit checks only.

## Follow-ups

- Run a manual browser walkthrough before demo or release if UI layout and clipboard/open behavior need interactive sign-off.
