# Codex Review: backfill-independent-gdt-foundation

## Findings

### P1 - Do not match `6310` results to the latest order using only patient number

[backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:2106)

When an inbound `6310` result has no matching `6200`/`8410` order identifier but does include `3000`, `record_gdt_result()` falls back to selecting the latest order for that GDT patient number and marks the result as `order-matched`. That can attach a result, artifacts, status update, and audit events to the wrong ECG order whenever a patient has more than one local GDT order or a device omits/uses a mismatched order identifier. The safer behavior is to keep this as unmatched or patient-only unless the order identifier is unambiguous. Add a regression test with two orders for one patient and a `6310` containing only `3000`.

### P2 - Order event history includes unrelated events from other orders for the same patient context

[backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:2023)

`list_gdt_events(order_record_id)` returns every event with the same `patient_context_id`, not just context-level events. Because order-created, message-generated, result-imported, attachment, and status events also carry `patient_context_id`, the event list for order A will include lifecycle events for order B if both share the same patient context. This weakens the audit trail and can confuse the new `/api/gdt/orders/<id>/events` endpoint. Filter shared-context events to records where `order_record_id IS NULL`, or explicitly query only the target order plus patient-number lifecycle events.

## Open Questions

- Should result import expose a patient-only match status distinct from fully unmatched when `3000` is known but no order identifier matches?

## Test Gaps

- Missing multi-order tests for one GDT patient context.
- Missing tests for `6310` payloads with only `3000` and no usable order identifier.

## Summary

The implementation covers the requested foundation shape and the happy-path tests pass, but the result matching and event filtering logic can corrupt or confuse order-level history in common multi-order patient scenarios. I recommend fixing these before `/dev-done`.
