## Overview

ZAC-22 adds a local, dashboard-started GDT ECG order flow to Healthcare Lab. The implementation should keep the dashboard as the operational entry point and keep the form workflow in the existing Patient/Order area. The dashboard OpenEMR/GDT group can expose an action such as "Create ECG Order" that focuses the Order page in GDT ECG mode.

The current HL7 ORM order workflow should remain isolated. GDT order creation has different payload, status, and future export/result semantics, so it should not be forced through the HL7-specific local order row shape.

## Current-State Conflicts

- Existing `Order` UI has GDT as a disabled future mode.
- Existing `/api/orders` creates HL7 v2.3.1 `ORM^O01` local order records.
- Existing `local_order_records` includes HL7-specific fields such as `payload_hl7`, `ack_code`, `ack_payload`, and OIE send status.
- Existing tests assert that `/api/gdt/orders` is absent.
- `PROJECT_BOUNDARY.md` excludes GDT Hospital/AP workflow UI from Healthcare Lab, so the implementation must stay limited to order creation/status and not pull in AP simulator result workflows.

## Proposed API

Use dedicated GDT endpoints:

- `GET /api/gdt/orders`: list local dashboard-created GDT orders.
- `POST /api/gdt/orders`: create one local 12-lead resting ECG GDT order for a local patient.
- Optional `GET /api/gdt/orders/<id>`: retrieve a persisted GDT order and payload/status detail if the UI needs a detail pane.

Request shape should include:

- `patientRecordId`
- optional requested time
- optional ordering provider/operator
- optional clinical indication/free-text note
- optional local attachment URL, demo-grade only

The backend owns the fixed MVP values:

- GDT set type/order request payload appropriate for the chosen MVP contract
- `8402=EKG01`
- display label "12-lead resting ECG"

## Data Model

Add GDT-specific persistence rather than overloading the HL7 ORM table. A table such as `local_gdt_order_records` should include:

- local id and local GDT order number
- linked `local_patient_records.id`
- patient snapshot fields needed to render/review the GDT payload after patient edits
- protocol version, message type/set type, and fixed `gdt_test_code = EKG01`
- status: `Created`, `Queued for GDT`, `Exported`, or `Error`
- requested time, ordering provider/operator, indication/note
- raw GDT payload text
- optional local attachment URL
- optional export path and error text
- created/updated timestamps

The existing local patient table can remain the source for patient creation and selection. Existing GDT 6301 patient rendering helpers may be reused where helpful, but order creation needs its own 8402-aware payload helper.

## GDT 8402 Mapping

The order payload must include field `8402` with value `EKG01`.

Rules to encode in validation/tests:

- Value is 1-6 alphanumeric characters.
- Value uses an uppercase group identifier of up to four letters followed by two digits.
- `EKG01` is fixed for the MVP and represents resting ECG.
- `EKG04` and `ERGO01` are valid real-world examples but must not be selectable in this MVP.
- Do not use field `8410` as a substitute for `8402`; `8410` is vendor-specific Test-ID and has a different purpose.

The proposal intentionally does not introduce a dynamic QMS-managed 8402 catalog. The code should make the fixed MVP explicit so a later change can replace it with a catalog-backed selector.

## UI Shape

Dashboard:

- Add a visible action on the OpenEMR/GDT service group for creating a local GDT ECG order.
- The action should navigate/focus the Order page in GDT ECG mode.
- Dashboard should show enough status after refresh to satisfy ZAC-22, either through a compact recent GDT orders panel or by making the GDT order list clearly accessible from the dashboard action.

Order page:

- Enable a GDT ECG mode separate from HL7 v2.3.1.
- In GDT mode, show patient selection and patient creation affordances needed by the dashboard-started flow.
- Hide HL7-only fields or clearly separate them from GDT fields.
- Show fixed test type `EKG01` as non-editable MVP information.
- Show raw GDT payload preview and persisted order status.

Patient creation:

- Reuse existing local patient creation where possible.
- If a compact create-patient form is added inside the GDT order flow, it must create the same local patient records used by the Patient page.

## Status Semantics

Initial statuses are local workflow states:

- `Created`: persisted locally.
- `Queued for GDT`: ready for local GDT export/bridge pickup when export is implemented in this flow.
- `Exported`: written to the configured local GDT bridge/export path.
- `Error`: validation or export failed.

Do not use device/result-complete language until Healthcare Lab has a corresponding GDT result import contract.

## Boundaries

Healthcare Lab owns:

- dashboard entry point
- local patient selection/creation for this flow
- local GDT ECG order creation
- local persistence and status display
- optional local demo-grade attachment URL field

Healthcare Lab does not own in this change:

- AP simulator ECG result packaging
- GDT Hospital/AP workflow UI
- complete GDT device simulation
- OpenEMR-driven order ingestion
- OIE routing or HL7 result workflows

## Open Questions

- Which exact GDT set type should the MVP order request use in this app's local bridge contract?
- Should the first implementation write an outbound GDT file immediately, or persist as `Queued for GDT` and add export in a follow-up task?
- Should dashboard status show only recent GDT orders, or all local GDT orders with filtering?

