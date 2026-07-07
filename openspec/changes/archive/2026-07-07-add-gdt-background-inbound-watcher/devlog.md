---
change: add-gdt-background-inbound-watcher
date: 2026-07-07
---

## Context

Healthcare Lab already supported manual GDT `6310` result import from the bridge
inbox. The change adds background-capable inbound acquisition so the lab can
model modern AIS/EDP shared-folder behavior while retaining operator-visible
debug controls.

## Implementation

- Added a shared GDT bridge batch import path used by manual selected-file import
  and automatic watcher import.
- Added safe inbound file discovery with temporary/internal file skipping,
  stability checks, FIFO ordering, and same-volume claim rename into a
  processing folder.
- Added archive/delete success modes, error routing, disposition warning
  handling, and collision-safe diagnostic paths.
- Added filename binding profiles for permissive lab mode, GDT 2.1 legacy
  sequence-extension files, and GDT 3.5 receiver/sender/sequence filenames.
- Added an in-process GDT bridge inbound watcher with start, stop, status, last
  run summary, and path-change guard behavior.
- Added GDT console controls/status for automatic import.
- Updated docs and environment defaults for watcher, filename profile, stable
  file timing, and archive-vs-delete behavior.
- Added regression coverage for batch import, FIFO order, temporary/unstable
  skipping, archive/delete handling, disposition warnings, binding filters,
  GDT 2.1 sequence-extension inbox visibility, watcher lifecycle, and frontend
  contract presence.

## Decisions

- Use polling instead of OS filesystem events because Docker bind mounts,
  Windows folders, and network shares are expected deployment surfaces.
- Keep archive mode as the lab default for observability, while supporting
  delete mode for standards-oriented exchange-folder cleanup.
- Preserve the existing safe matching policy: patient-only `6310` results are
  not attached to the latest order automatically.
- Treat post-persistence archive/delete failures as imported-with-warning
  disposition problems instead of parse/import failures.

## Validation Plan

- Run the full Python unit test suite.
- Run Python compile checks for app, backend modules, and tests.
- Run frontend JavaScript syntax check.
- Run strict OpenSpec validation for the change.
- Run whitespace/diff hygiene check.

## Follow-ups

- For a production deployment, replace or supervise the in-process watcher with
  an external service/daemon model.
- Future GDT 3.5 matching work should prefer `8314` Request-UID and `8408`
  Study-UID when supported by real sender fixtures.

## Verification

### Round 1 (2026-07-07)

Result: pass.

- `python -m unittest discover -s tests -v`: pass, 65 tests.
- `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`: pass.
- `node --check frontend\static\app.js`: pass.
- `openspec validate add-gdt-background-inbound-watcher --strict`: pass.

### Round 2 (2026-07-07)

Result: pass after review fixes.

- `python -m unittest discover -s tests -v`: pass, 67 tests.
- `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`: pass.
- `node --check frontend\static\app.js`: pass.
- `openspec validate add-gdt-background-inbound-watcher --strict`: pass.
- `git diff --check`: pass.

## Code Review

### Round 1 (2026-07-07)

Source: `openspec/changes/add-gdt-background-inbound-watcher/review/2026-07-07_codex-review.md`

Verdict: changes requested.

- P2: Post-persistence archive/delete cleanup failures were reported as import
  failures after the result had already been committed.
- P2: Manual inbox listing hid valid GDT 2.1 numeric-extension files while the
  backend supported importing them.

### Round 2 (2026-07-07)

Source: `openspec/changes/add-gdt-background-inbound-watcher/review/2026-07-07_codex-review-r2.md`

Verdict: no blocking issues found.

- Prior P2 cleanup/disposition finding resolved with `imported-warning` and
  `dispositionError`.
- Prior P2 GDT 2.1 inbox visibility finding resolved by listing supported
  sequence-extension files under `gdt21`.
