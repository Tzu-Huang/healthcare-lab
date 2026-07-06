## 1. Scope and Contracts

- [x] 1.1 Confirm the exact GDT order-request set type and minimum field list for the local bridge contract.
- [x] 1.2 Update `PROJECT_BOUNDARY.md` or implementation docs to clarify that Healthcare Lab owns local GDT order creation but not the full GDT AP Simulator workflow.
- [x] 1.3 Preserve existing HL7 v2.3.1 ORM/OIE behavior and tests.

## 2. Backend Model and API

- [x] 2.1 Add GDT-specific SQLite persistence for dashboard-created local GDT ECG orders.
- [x] 2.2 Add GDT 8402 validation/rendering for fixed `EKG01`.
- [x] 2.3 Add `GET /api/gdt/orders` and `POST /api/gdt/orders` backend APIs.
- [x] 2.4 Store patient snapshots, raw GDT payload, optional local attachment URL, and local order status.
- [x] 2.5 Support refresh-safe listing of created GDT orders without requiring OpenEMR configuration.

## 3. Frontend Flow

- [x] 3.1 Add a dashboard OpenEMR/GDT action that opens the GDT ECG order flow.
- [x] 3.2 Enable a GDT ECG mode on the Order page without disrupting the HL7 ORM mode.
- [x] 3.3 Let users select an existing local patient or create a patient from the dashboard-started flow.
- [x] 3.4 Display fixed test type `8402=EKG01` and hide/disable non-MVP test types.
- [x] 3.5 Show raw GDT payload preview, created order status, and persisted GDT orders after refresh.

## 4. Verification

- [x] 4.1 Add backend tests for GDT order creation without OpenEMR configuration.
- [x] 4.2 Add backend tests for fixed `8402=EKG01` and rejection/non-exposure of `EKG04` and `ERGO01`.
- [x] 4.3 Add API tests for listing created GDT orders after refresh.
- [x] 4.4 Add frontend tests or syntax checks for the dashboard action and GDT order mode.
- [x] 4.5 Run Python unit tests, Python compile checks, frontend syntax checks, and OpenSpec validation.
