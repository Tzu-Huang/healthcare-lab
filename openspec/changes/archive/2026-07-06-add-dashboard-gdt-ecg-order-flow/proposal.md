## Why

Healthcare Lab already has local Patient and Order pages, plus an OpenEMR/GDT service group on the dashboard. The current order workflow is explicitly HL7 v2.3.1 `ORM^O01`; the UI shows GDT as a disabled future order mode, and tests currently assert that `/api/gdt/orders` is not registered. ZAC-22 changes that direction for a narrow MVP: users need a Healthcare Lab dashboard path to create a 12-lead resting ECG GDT order without depending on OpenEMR.

This should not replace the existing HL7 ORM/OIE flow. It should add a separate, clearly scoped GDT order path that reuses local patient data where practical, persists created orders, and shows order status after refresh.

## What Changes

- Add a Healthcare Lab dashboard entry point for the OpenEMR/GDT service group that opens the local GDT ECG order workflow.
- Enable a GDT ECG order creation mode in the existing Order area instead of building a second full workflow surface in the dashboard table.
- Allow users to select an existing local patient or create a patient as part of the dashboard-started flow.
- Add backend support for creating local GDT ECG order records without reading OpenEMR MariaDB.
- Use GDT 2.1-compatible payload rendering for the MVP order request and fixed `8402=EKG01`.
- Persist created GDT orders and show their status after page refresh.
- Keep HL7 v2.3.1 `ORM^O01` order creation and OIE send behavior unchanged.
- Update specs/tests that currently treat GDT order mode and `/api/gdt/orders` as absent or future-only.

## Non-Goals

- No support for `EKG04`, `ERGO01`, or other 8402 values in the first implementation.
- No full GDT AP Simulator migration back into Healthcare Lab.
- No ECG JSON, PDF, aECG, DICOM result packaging, or AP-side result workflow.
- No OpenEMR server, OpenEMR database, or procedure-order query requirement for this dashboard-created order path.
- No production patient data handling, auth, audit, or external GDT device certification.
- No automatic GDT hospital simulator/device orchestration beyond local demo-grade status and optional local attachment URL support.

## Key Decisions

- API shape: prefer a clean dedicated GDT order endpoint, such as `/api/gdt/orders`, because existing `/api/orders` is HL7 ORM/OIE-specific and its data model includes HL7-only send/ACK semantics. This requires updating the current route-absence test.
- Frontend shape: use the dashboard OpenEMR/GDT service group as the entry point, then open or focus the Order page in GDT ECG mode. This keeps the dashboard operational and avoids turning it into a complex form surface.
- Data model: add GDT-specific persistence fields/tables rather than overloading `payload_hl7`, `message_type=ORM^O01`, and HL7 ACK columns.
- Status model: start with local MVP statuses such as `Created`, `Queued for GDT`, `Exported`, and `Error`. Do not imply device completion or result receipt until a later result workflow exists.
- Boundary: Healthcare Lab may own local GDT order creation and status display, but the full GDT AP Simulator workflow remains out of scope.

## GDT 8402 Contract

The MVP fixed test type is `8402=EKG01`. Field `8402` is the device and process-specific characteristic map. For GDT 2.1 and 3.5, its value is a 1-6 alphanumeric code composed of an uppercase group identifier up to 4 letters followed by two digits. `00` is reserved for unspecified tests within a group. `EKG01` identifies resting ECG, while `EKG04` and `ERGO01` remain out of this MVP. Field `8402` is a standardized category code and must not be confused with vendor-specific `8410` Test-ID values.

## Capabilities

### New Capabilities

- `healthcare-lab-dashboard-gdt-order-flow`: Define dashboard-started local GDT 12-lead resting ECG order creation, persistence, status display, and boundary rules.

### Modified Capabilities

- `healthcare-lab-order-hl7-orm-mvp`: Implementation must preserve the existing HL7 order behavior while removing the assumption that GDT order creation is unavailable.

## Impact

- Affected code: dashboard service UI, Order page mode handling, patient/order frontend state, backend APIs, SQLite persistence, GDT payload rendering helpers, tests, and documentation.
- Affected runtime: local Healthcare Lab SQLite database stores GDT order records; optional local GDT bridge/export paths may be used for demo-grade order export.
- Affected workflow: users can start from the dashboard, create/select a local patient, create one fixed 12-lead resting ECG GDT order, and see it after refresh without OpenEMR.

