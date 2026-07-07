## Overview

This change should preserve the existing ZAC-22 behavior while replacing the narrow storage shape with an independent GDT workflow foundation. The current `local_gdt_order_records` table can either be migrated forward or kept as a compatibility-facing projection over richer tables. The implementation should prefer additive schema changes so existing local dev databases continue to open.

## Proposed Data Model

### GDT Patient Context

Add GDT-specific patient context fields or a dedicated table, such as `local_gdt_patient_contexts`, linked to `local_patient_records`.

Fields should include:

- `local_patient_record_id`
- generated `gdt_patient_number` for field `3000`
- `gdt_patient_number_override`
- effective `gdt_patient_number`
- patient snapshot JSON for GDT workflows
- `created_at` and `updated_at`

MRN remains separate from the GDT `3000` value. New GDT patients should get a generated value like `GDT-PAT-000001` unless an override is supplied.

### GDT Orders

Keep a durable GDT order table with:

- local GDT order number
- linked local patient and GDT patient context
- fixed MVP `gdt_test_code=EKG01`
- order status
- requested time, provider, indication
- patient and order snapshot JSON
- created/updated timestamps

The current `/api/gdt/orders` response should continue to expose `localGdtOrderNumber`, `gdtTestField`, `gdtTestCode`, `payload`, `summary`, `status`, and timestamp fields expected by ZAC-22.

### GDT Messages And Results

Add message/result records, such as `local_gdt_message_records`, for both generated `6302` order messages and imported `6310` result messages.

Fields should include:

- linked order id when available
- message direction: outbound or inbound
- message type/set type, for example `6302` or `6310`
- raw GDT text
- parsed fields JSON, keyed by GDT field code while preserving repeated fields
- canonical JSON, shaped as `{ patient, order, result, attachments, correlation }`
- parse/match status
- error text
- received/exported/generated timestamps
- created/updated timestamps

`6310` result import should match to local GDT orders by local order/test identifier first, then patient number where useful. Unknown or unmatched results should still be persisted with match status and diagnostics.

### Attachments

Add normalized attachment records, such as `local_gdt_attachment_records`.

Fields should include:

- linked order id and/or message/result id
- attachment role: report, waveform, xml, other
- URL or local path
- content type
- filename
- checksum when available
- created/updated timestamps

The existing `attachmentUrl` request/response field can remain as a compatibility shortcut that creates or returns a primary attachment record.

### Events

Add an event table, such as `local_gdt_workflow_events`, for audit-capable workflow history.

Events should record:

- order id, patient context id, message id, and attachment id when applicable
- event type
- actor/operator when available
- details JSON
- created timestamp

Expected event types include patient-number-generated, patient-number-overridden, order-created, message-generated, result-imported, result-matched, attachment-registered, status-changed, and error-recorded.

## API Shape

Keep:

- `GET /api/gdt/orders`
- `POST /api/gdt/orders`

Add backend result/message endpoints as needed, for example:

- `GET /api/gdt/orders/<id>`
- `GET /api/gdt/messages`
- `POST /api/gdt/results`
- `GET /api/gdt/orders/<id>/events`

The implementation can choose exact endpoint names, but tests should assert stable behavior for order creation/listing and result persistence.

## Compatibility Rules

- Existing ZAC-22 dashboard-created GDT order tests should continue to pass or be updated only to include additive fields.
- `8402=EKG01` remains fixed.
- OpenEMR configuration must not be required for local GDT order/result persistence.
- `payload` may continue to alias the outbound raw `6302` message in response objects, but storage should use `raw_gdt_text`.
- Existing optional `attachmentUrl` should map into normalized attachment storage.

## Testing Strategy

- Store tests for generated and override `3000` behavior.
- Store tests for raw/parsed/canonical JSON separation.
- Store tests for multiple attachments on one order/result.
- API tests for creating/listing ZAC-22-compatible orders without OpenEMR.
- API/store tests for `6310` result import, matching, unmatched persistence, and event records.
- Regression tests for fixed `8402=EKG01` and rejection of non-MVP test codes.
