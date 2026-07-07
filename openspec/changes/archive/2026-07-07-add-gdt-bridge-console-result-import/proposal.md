## Why

Healthcare Lab owns the local GDT ECG workflow. It can already create local GDT
orders and persist imported `6310` result messages, but the user-facing flow is
still split across the general Order page and backend-only APIs. ZAC-24 should
turn the GDT foundation into a complete Healthcare Lab GDT bridge console: a
dashboard surface that can create orders, write `6302` bridge files, import
`6310` result files from the shared folder, show ECG measurements, and expose
artifact references.

This remains inside the Healthcare Lab boundary because the responsibility is
limited to GDT order/result receiving, local persistence, shared-folder bridge
file handling, and dashboard display. It does not expand HL7, FHIR, or DICOM
AP-simulator behavior.

## What Changes

- Add a sidebar `GDT` console with an OIE-like patient-centered layout.
- Show local GDT patients, selected-patient details, GDT ECG orders, GDT
  results, bridge inbox files, artifact references, raw payloads, and events.
- Let users create or select GDT patients and create local `8402=EKG01` ECG
  orders from the console.
- Add shared-folder bridge operations for:
  - writing a selected order's `6302` request into the configured outbox,
  - listing inbound `.gdt` files,
  - importing selected inbound `6310` files,
  - recording archive/error state without discarding raw payloads.
- Keep manual/raw `6310` import available for operator-driven testing.
- Add a `Demo Result` action that creates deterministic demo result content for
  a selected order and exercises the same import/display path.
- Map `6310` artifact groups according to the GDT bridge knowledge base:
  - `6302`: artifact group or identifier,
  - `6303`: artifact format such as `PDF` or `DICOM`,
  - `6304`: artifact description,
  - `6305`: file path, UNC path, URL, or other artifact reference.
- Store artifact records as metadata/reference records. Do not copy PDF or
  DICOM bytes into managed storage in this change.
- Display ECG measurements, result status/text, attachment references, raw
  `6310`, and workflow events in the GDT console.

## Non-Goals

- No HL7, FHIR, or non-GDT result packaging changes.
- No full GDT hospital/AP simulator UI in Healthcare Lab.
- No DICOM parser, PACS send, SOP validation, or DICOM waveform rendering.
- No PDF text extraction or browser-side PDF processing beyond opening or
  downloading a referenced artifact when the reference is usable.
- No managed artifact byte storage or file copying; Healthcare Lab records
  paths/references only.
- No production vendor onboarding UI or dynamic vendor profile editor.
- No GDT 3.5 object parser.

## Key Decisions

- Format authority: GDT field semantics for this change follow
  `test-ui/docs/knowledge-base/gdt-bridge-knowledge-base.md`.
- Console shape: use the same mental model as the OIE console:
  `Patient -> Orders -> Results -> Payload/Detail`.
- Import strictness: import what is received. Missing referenced artifacts do
  not block result import; Healthcare Lab records warnings/status/details for
  operator review.
- Artifact storage: persist `6305` references and metadata only. Keep the
  original path/URL/UNC value and link it to the result/order/message.
- DICOM scope: treat DICOM as an artifact format/reference only.
- Demo path: keep a deterministic `Demo Result` action for fast local demos.
- File serving: when a reference can be safely opened or downloaded by the app,
  expose a view/download/copy affordance. Otherwise expose copyable reference
  text.

## Capabilities

### New Capabilities

- `healthcare-lab-gdt-bridge-console`: A patient-centered Healthcare Lab GDT
  console for local GDT order creation, bridge file operations, result import,
  artifact reference display, and raw/canonical result inspection.

### Modified Capabilities

- `healthcare-lab-independent-gdt-foundation`: Extend existing GDT persistence
  with shared-folder import/export state and reference-only artifact registry
  behavior needed by the console.
- `healthcare-lab-dashboard-gdt-order-flow`: Keep the dashboard-started order
  path compatible while allowing the full GDT console to become the primary
  workflow surface.
- `healthcare-lab-gdt-21-adapter`: Ensure artifact group parsing aligns with
  the GDT bridge knowledge base for `6302-6305`.

## Impact

- Affected code: Flask GDT APIs, GDT store operations, bridge file helpers,
  frontend navigation/templates/scripts/styles, and tests.
- Affected data: local SQLite GDT order/message/attachment/event records and
  any new bridge import/export state needed for idempotency and operator
  visibility.
- Affected UI: add a new GDT console while preserving existing Dashboard,
  Patient, Order, and OIE views.
- Affected docs/tests: update GDT bridge docs as needed and add regression
  coverage for bridge import, artifact reference mapping, and UI/API contracts.
