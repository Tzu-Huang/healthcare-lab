---
change: backfill-independent-gdt-foundation
date: 2026-07-07
---

## Context

ZAC-21 backfills the independent GDT persistence foundation underneath the ZAC-22 dashboard-created ECG order flow. The branch is intentionally stacked on `feature/ZAC-22_add-dashboard-gdt-ecg-order-flow` so the existing dashboard/API contract can be preserved while strengthening the long-lived backend model.

## Implementation

- Added independent GDT patient contexts with generated `GDT-PAT-000001`-style field `3000` values and manual override support.
- Added GDT order snapshots, outbound `6302` message persistence, raw/parsed/canonical message storage, normalized attachments, and workflow event history.
- Added backend `6310` result import, matching, unmatched persistence, attachment extraction, and status/event updates.
- Added GDT inspection APIs for order detail, message listing, order events, and result import.
- Preserved ZAC-22 `/api/gdt/orders` create/list compatibility with additive fields only.

## Decisions

- `local_gdt_order_records` remains the ZAC-22 compatibility surface while new foundation tables hold patient context, messages/results, attachments, and events.
- GDT field `3000` no longer assumes MRN; MRN remains separate identity data.
- Inbound `6310` results require an explicit local order identifier for order-level matching. Patient number alone identifies patient context but does not guess an order.
- Order event history includes the target order plus context-only patient-number events, not sibling order lifecycle events.

## Validation Plan

- Run Python unit discovery for store/API coverage.
- Run Python compile checks for touched modules/tests.
- Run OpenSpec strict validation.
- Run `git diff --check`.

## Verification

### Round 1 (2026-07-07)

- Pass: `python -m unittest discover -s tests` (55 tests before review fix).
- Pass: `python -m py_compile app.py backend\lab_store.py tests\test_app.py tests\test_lab_store.py`.
- Pass: `openspec validate backfill-independent-gdt-foundation --strict`.
- Pass: `git diff --check`.

### Round 2 (2026-07-07)

- Pass: `python -m unittest discover -s tests` (57 tests after review fix).
- Pass: `python -m py_compile app.py backend\lab_store.py tests\test_app.py tests\test_lab_store.py`.
- Pass: `openspec validate backfill-independent-gdt-foundation --strict`.
- Pass: `git diff --check`.

## Code Review

### Round 1 (2026-07-07)

- Review file: `openspec/changes/backfill-independent-gdt-foundation/review/2026-07-07_codex-review.md`.
- Verdict: changes requested.
- Findings:
  - P1: inbound `6310` results could match the latest order by `3000` patient number alone.
  - P2: order event history could include lifecycle events from sibling orders sharing the same patient context.

### Round 2 (2026-07-07)

- Review file: `openspec/changes/backfill-independent-gdt-foundation/review/2026-07-07_codex-review-r2.md`.
- Verdict: no issues found.
- Prior findings were confirmed fixed with multi-order regression coverage.

## Follow-ups

- Keep PR base/merge order aligned with ZAC-22 because this branch is stacked on the ZAC-22 dashboard GDT order flow.
