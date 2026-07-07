---
change: implement-gdt-21-adapter
date: 2026-07-07
issue: ZAC-23
---

## Context

ZAC-23 implements the Healthcare Lab GDT 2.1 adapter for outbound `6302` exam requests and inbound `6310` results. The adapter must preserve raw GDT payloads, enforce BDT framing and `8100` total length, canonicalize patient/order/result data, and surface structured validation notices.

## Implementation

- Added `backend/gdt_adapter.py` with GDT record/message rendering, parsing, validation, `6302` request generation, and `6310` result parsing.
- Updated `backend/lab_store.py` to route outbound GDT order creation and inbound result recording through the adapter while preserving existing public helper wrappers.
- Added canonical result payloads for patient data, order identifiers, ECG measurements, result summary fields, comments, formatted text, attachments, and validation notices.
- Added regression coverage in `tests/test_gdt_adapter.py`, `tests/test_lab_store.py`, and `tests/test_app.py`.

## Decisions

- Kept old `lab_store` GDT helper names as wrappers to avoid breaking existing imports.
- Stored validation notices inside the canonical payload because the current database schema has no dedicated validation column.
- Treated `8410` as vendor-defined and mapped only known ECG aliases from the knowledge base, warning on unknown measured values instead of rejecting them.
- Preserved legacy attachment parsing while adding support for grouped `6302`-`6305` artifact fields.

## Validation Plan

- Run full unit tests for the backend test suite.
- Run Python compile checks on touched app, backend, and test modules.
- Validate the OpenSpec change in strict mode.
- Run `git diff --check` before completion.

## Verification

### Round 1 (2026-07-07)

- `python -m unittest discover -s tests -v`: passed 63 tests.
- `python -m py_compile app.py backend\gdt_adapter.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_gdt_adapter.py tests\test_lab_store.py tests\test_app.py tests\test_b64_pdf.py`: passed.
- `openspec validate implement-gdt-21-adapter --strict`: passed.
- `git diff --check`: passed.

### Round 2 (2026-07-07)

- After fixing required `6310` field validation, `python -m unittest discover -s tests -v`: passed 65 tests.
- `python -m py_compile app.py backend\gdt_adapter.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_gdt_adapter.py tests\test_lab_store.py tests\test_app.py tests\test_b64_pdf.py`: passed.
- `openspec validate implement-gdt-21-adapter --strict`: passed.
- `git diff --check`: passed.

## Code Review

### Round 1 (2026-07-07)

- Review file: `openspec/changes/implement-gdt-21-adapter/review/2026-07-07_codex-review.md`
- Verdict: changes requested.
- Finding: `6310` required content fields `3000` and `8402` were accepted when missing, allowing invalid clinical results to persist.

### Round 2 (2026-07-07)

- Review file: `openspec/changes/implement-gdt-21-adapter/review/2026-07-07_codex-review-r2.md`
- Verdict: no issues found.
- Confirmed the prior P2 was resolved by rejecting missing `3000` and `8402` with structured `201` validation notices and regression tests.

## Follow-ups

- Add real vendor GDT `6310` fixtures when available to harden vendor-specific `8410` mapping behavior.
