---
change: add-dcm4chee-sync-retry-api
date: 2026-07-09
---

## Context

ZAC-38 adds the user-facing recovery layer for dcm4chee order sync failures. The existing PACS/MWL ledger already stores canonical mappings, attempts, retry metadata, and idempotent identifier behavior; this change builds API and UI workflows on top of that foundation.

## Implementation

- Added order-level dcm4chee sync/retry and attempt-history APIs:
  - `POST /api/orders/<order_id>/dcm4chee-sync`
  - `GET /api/orders/<order_id>/dcm4chee-attempts`
- Added dcm4chee MWL response metadata for `retryable`, `displayStatus`, `displayState`, and `latest` status details.
- Added DICOM order workspace retry action for retryable MWL sync states.
- Added selected DICOM order inspection for latest sync details, identifiers, retry count, HTTP/error details, and attempt history.
- Added focused backend tests for retry success, retry failure, non-DICOM/unknown order handling, and attempt history ordering.
- Fixed the failed-retry UI path so HTTP 200 responses with `success: false` still render updated MWL status and refresh attempts.

## Decisions

- Kept existing stored ledger status values such as `Pending sync`, `Created`, `Sync failed`, and `Patient missing`; clearer labels are exposed as display metadata instead of migrating stored data.
- Treated infrastructure/read-back failures as retryable, while patient-precondition and profile-validation failures remain non-retryable unless the underlying data/config changes.
- Reused the existing dcm4chee sync function and canonical mapping ledger to preserve idempotency instead of adding a separate retry implementation.
- Scoped the fix for failed business responses to the dcm4chee retry call by adding a local request helper that only throws on non-2xx transport failures.

## Validation Plan

- Validate OpenSpec with `openspec validate add-dcm4chee-sync-retry-api --strict`.
- Check frontend syntax with `node --check frontend\static\app.js`.
- Run dcm4chee API tests with `python -m unittest tests.test_app -k dcm4chee`.
- Run the existing dcm4chee mapping migration regression:
  `python -m unittest tests.test_lab_store.HealthcareLabStoreTests.test_dcm4chee_mapping_backfills_from_existing_attempts`.
- Before demo use, manually smoke-check the browser flow for a failed DICOM retry, selected-order details, and attempt-history rendering.

## Code Review

### Round 1 (2026-07-09)

- Initial review found no blocking issues; residual risk was manual browser smoke coverage for the DICOM retry UI.
- R2 found one P1: failed dcm4chee retry responses returned HTTP 200 with `success: false`, but the frontend generic request helper threw before rendering the updated order/error payload.
- Fix commit `07bae94` added `requestJsonAllowBusinessFailure()` for the retry path.
- R3 found no blocking issues; R2 finding was confirmed resolved.

## Follow-ups

- Manual browser smoke test remains recommended because the local automated checks do not exercise actual DOM rendering in a browser.
- If the product later needs a `Reconciled` state, wire it to result reconciliation rather than folding it into MWL create/retry status prematurely.
