## 1. Scope Confirmation

- [x] 1.1 Summarize the ZAC-18 Order HL7 v2.3.1 ORM MVP scope in the devlog before implementation.
- [x] 1.2 Confirm current Patient MVP persistence and decide the exact local `visit_id` / account-number generation behavior.

## 2. Local Order Model and HL7 Generation

- [x] 2.1 Add SQLite persistence for local order records linked to local patients.
- [x] 2.2 Generate stable local placer order numbers and outpatient visit/account ids.
- [x] 2.3 Add HL7 v2.3.1 `ORM^O01` generation with `MSH`, `PID`, `PV1`, `ORC`, and `OBR`.
- [x] 2.4 Persist generated ORM payloads with order records.

## 3. Order Page

- [x] 3.1 Add protocol/type selector with HL7 v2.3.1 enabled and HL7 v2.5.1, FHIR, GDT, and DICOM disabled as future modes.
- [x] 3.2 Add patient selector and 12-lead ECG demo preset.
- [x] 3.3 Add order fields for provider defaults, priority, requested time, and clinical indication.
- [x] 3.4 Display validation status, patient/order summary, and raw ORM preview.
- [x] 3.5 Create local orders with status `Ready to send`.

## 4. OIE Inventory and Send

- [x] 4.1 Extend OIE page with Order inventory beside Patient inventory.
- [x] 4.2 Show selected order details and raw ORM preview.
- [x] 4.3 Add OIE connection settings for host, port, timeout, and MLLP framing with defaults `localhost:6663`.
- [x] 4.4 Implement manual one-at-a-time `Send Order` to OIE over MLLP.
- [x] 4.5 Record and display parsed ACK status `AA`, `AE`, `AR`, raw ACK payload, and transport errors.
- [x] 4.6 Document OIE-to-AP routing as OIE channel configuration outside app scope.

## 5. Verification

- [x] 5.1 Add backend tests for order persistence and ORM generation.
- [x] 5.2 Add backend tests for ACK parsing and transport-error handling.
- [x] 5.3 Add frontend syntax checks for Order and OIE page behavior.
- [x] 5.4 Verify existing Dashboard, Patient, and OIE behavior remains intact.
