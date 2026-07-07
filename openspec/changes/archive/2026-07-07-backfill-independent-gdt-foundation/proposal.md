## Why

ZAC-22 already added a working dashboard-started GDT ECG order path on top of Healthcare Lab: users can create or select a local patient, create a local GDT ECG order through `/api/gdt/orders`, persist a raw `6302` order payload, and reload the order list without OpenEMR running. That flow is useful and should be preserved.

The current implementation is still a narrow MVP. It stores one order table with a patient snapshot, one raw order payload, and an optional attachment URL. It does not yet define the long-lived independent GDT workflow foundation that future export/import/result work can depend on: generated GDT patient numbers, manual patient-number override semantics, separate raw/parsed/canonical message storage, normalized attachments, result records, and audit-capable event history.

This change backfills that foundation while keeping the ZAC-22 dashboard behavior compatible.

## What Changes

- Add an independent GDT foundation capability for Healthcare Lab-owned patient, order, message/result, attachment, and event persistence.
- Keep the existing ZAC-22 `/api/gdt/orders` create/list API behavior compatible for dashboard-created 12-lead ECG orders.
- Define Healthcare Lab ownership of GDT field `3000` patient numbers:
  - generate stable local values such as `GDT-PAT-000001`,
  - allow manual override when creating or updating GDT workflow context,
  - snapshot the chosen value onto each GDT order/message.
- Store raw GDT text separately from parsed field JSON and canonical workflow JSON.
- Normalize attachment records so one GDT order/result can reference multiple artifacts such as PDF reports and XML/waveform files.
- Add full backend foundation for `6310` GDT result/import persistence and matching to local GDT orders.
- Record audit-capable GDT workflow events for creation, payload generation, export/import, result matching, attachment registration, and error states.
- Update tests to cover the no-OpenEMR path, ZAC-22 compatibility, field `3000` behavior, result/message persistence, attachment records, raw/parsed/canonical separation, and audit/event history.

## Non-Goals

- No rebuild of the ZAC-22 dashboard UI from scratch.
- No support for `EKG04`, `ERGO01`, or a dynamic `8402` catalog in this change.
- No full AP simulator UI in Healthcare Lab.
- No production-grade GDT device certification, auth, or external device orchestration.
- No dependency on OpenEMR runtime or OpenEMR database access for dashboard-created local GDT workflows.

## Key Decisions

- Branching: this proposal is based on `feature/ZAC-22_add-dashboard-gdt-ecg-order-flow` because ZAC-21 reconciles and strengthens that already implemented flow. The implementation branch should merge after ZAC-22 or temporarily target ZAC-22 until ZAC-22 lands.
- Capability shape: introduce `healthcare-lab-independent-gdt-foundation` instead of overloading the dashboard flow capability. The existing dashboard spec remains the user-facing order-creation contract; this new spec owns backend persistence and lifecycle foundations.
- Patient number: Healthcare Lab generates a stable local GDT patient number for field `3000`, with manual override support. MRN remains separate identity data and must not be assumed to equal `3000`.
- Payload storage: every persisted GDT message/result stores `raw_gdt_text`, `parsed_fields_json`, and `canonical_json` separately.
- Attachments: attachments are normalized records, not only a single string URL on the order row.
- Results: implement the backend persistence/matching foundation for `6310` results now, even if the UI remains minimal.

## Capabilities

### New Capabilities

- `healthcare-lab-independent-gdt-foundation`: Define OpenEMR-independent GDT patient number, order, message/result, attachment, and audit/event persistence for Healthcare Lab.

### Modified Capabilities

- `healthcare-lab-dashboard-gdt-order-flow`: Preserve existing ZAC-22 dashboard-created GDT order API/UI behavior while routing persistence through the independent foundation.

## Impact

- Affected code: SQLite schema/migrations, GDT payload parsing/rendering helpers, GDT order APIs, result/import backend APIs, local store serialization, tests, and possibly small dashboard/order UI compatibility fields.
- Affected runtime: local Healthcare Lab database gains independent GDT workflow tables and event records.
- Affected workflow: developers can create local GDT patients/orders/results without OpenEMR, inspect raw and parsed GDT content, attach result artifacts, and rely on stable backend records for future export/import UI.
