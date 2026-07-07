## 1. Scope and Compatibility

- [x] 1.1 Confirm the final table/API names for independent GDT foundation records.
- [x] 1.2 Preserve ZAC-22 `/api/gdt/orders` create/list response compatibility.
- [x] 1.3 Keep Healthcare Lab GDT runtime independent from OpenEMR configuration and database access.
- [x] 1.4 Keep MVP ECG type fixed to `8402=EKG01`.

## 2. Data Model

- [x] 2.1 Add GDT patient context persistence with generated `3000` values and manual override support.
- [x] 2.2 Add or migrate GDT order persistence to reference patient context and store order snapshots.
- [x] 2.3 Add GDT message/result records with `raw_gdt_text`, `parsed_fields_json`, and `canonical_json`.
- [x] 2.4 Add normalized GDT attachment records with support for multiple artifacts.
- [x] 2.5 Add GDT workflow event records for audit-capable history.

## 3. Backend Behavior

- [x] 3.1 Generate stable Healthcare Lab-owned GDT patient numbers such as `GDT-PAT-000001`.
- [x] 3.2 Apply manual patient-number overrides and snapshot the effective `3000` value on orders/messages.
- [x] 3.3 Persist generated `6302` order messages through the message table while keeping `payload` compatibility.
- [x] 3.4 Implement backend `6310` result import/persistence and order matching.
- [x] 3.5 Map legacy `attachmentUrl` into normalized attachment records.
- [x] 3.6 Record workflow events for order creation, message generation/import, matching, attachments, status changes, and errors.

## 4. API and UI Compatibility

- [x] 4.1 Keep existing dashboard/order UI behavior working with the richer backend records.
- [x] 4.2 Add backend APIs for result/message/event inspection where needed.
- [x] 4.3 Avoid introducing OpenEMR runtime dependencies into the local GDT path.

## 5. Verification

- [x] 5.1 Add tests for generated and manually overridden GDT `3000` values.
- [x] 5.2 Add tests for raw, parsed, and canonical GDT message storage.
- [x] 5.3 Add tests for normalized multiple attachments.
- [x] 5.4 Add tests for `6310` result import, matching, unmatched persistence, and events.
- [x] 5.5 Add regression tests for ZAC-22 `/api/gdt/orders` compatibility and no-OpenEMR runtime behavior.
- [x] 5.6 Run unit tests, Python compile checks, frontend syntax checks if touched, and OpenSpec validation.
