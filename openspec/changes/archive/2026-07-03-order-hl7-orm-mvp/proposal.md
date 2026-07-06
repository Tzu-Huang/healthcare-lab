## Why

Healthcare Lab has a local Patient MVP that creates HL7 v2.3.1 `ADT^A04` payloads and keeps those records visible in the OIE inventory. The next useful workflow is local order creation: select a registered patient, create a 12-lead ECG order, preview the HL7 v2.3.1 `ORM^O01`, and send it manually to a local OIE MLLP endpoint.

Today the Order page is present as a navigation surface, but it does not yet provide a working HL7 v2.3.1 order workflow. OIE also shows Patient inventory only, so there is no local order inventory, selected order payload preview, connection settings, or ACK result capture.

## What Changes

- Add an Order page protocol selector with HL7 v2.3.1 enabled and HL7 v2.5.1, FHIR, GDT, and DICOM shown as disabled future modes.
- Build a 12-lead ECG order form that reuses locally registered patients and provides demo defaults for ordering provider, order priority, requested time, clinical indication, and ECG coding.
- Generate an HL7 v2.3.1 `ORM^O01` preview with `MSH`, `PID`, `PV1`, `ORC`, and `OBR` segments.
- Persist local order records, order status, generated ORM payloads, and send/ACK results in SQLite.
- Extend the OIE page with an Order inventory beside the existing Patient inventory, including `Ready to send`, selected order details, and raw ORM preview.
- Add OIE connection settings for host, port, timeout, and MLLP framing with defaults for `localhost:6663`.
- Send one selected order at a time to OIE over MLLP and record ACK status as `AA`, `AE`, `AR`, or transport error.
- Document that OIE-to-AP routing and channel configuration stay outside the Dashboard/Order MVP.

## Non-Goals

- No OIE channel provisioning or OIE-to-AP routing automation.
- No automatic send-on-create behavior in the MVP.
- No full HL7 v2.5.1, FHIR, GDT, or DICOM order workflow.
- No production-grade terminology service or final ECG coding strategy.
- No multi-order batch sending.

## Capabilities

### New Capabilities

- `healthcare-lab-order-hl7-orm-mvp`: Define local HL7 v2.3.1 ECG order creation, persistence, OIE inventory display, and manual MLLP send behavior.

### Modified Capabilities

- None.

## Impact

- Affected code: Healthcare Lab Order page, OIE page, local SQLite store, HL7 payload generation, MLLP client path, backend tests, frontend syntax.
- Affected runtime: local Healthcare Lab database and optional local OIE listener at `localhost:6663`.
- Affected workflow: developers can create a patient locally, create a linked ECG order, inspect the generated ORM payload, manually send it to OIE, and review the ACK or transport result.
