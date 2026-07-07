## 1. Adapter Boundary

- [x] 1.1 Add a GDT 2.1 adapter module or equivalent backend boundary outside the persistence layer.
- [x] 1.2 Move or wrap existing record rendering/parsing helpers behind the adapter without changing API behavior.
- [x] 1.3 Return structured parsed fields, canonical JSON, and validation notices from adapter operations.

## 2. `6302` Generation

- [x] 2.1 Generate GDT 2.1 `6302` New Test Request messages from Healthcare Lab canonical order data.
- [x] 2.2 Preserve fixed MVP `8402=EKG01` behavior.
- [x] 2.3 Verify every generated record length and stabilized `8100` total length.
- [x] 2.4 Keep existing `/api/gdt/orders` response compatibility, including the `payload` raw message alias.

## 3. `6310` Parsing

- [x] 3.1 Parse GDT 2.1 `6310` Test Data Transfer messages through the adapter.
- [x] 3.2 Normalize ECG measurement groups using `8410`, `8420`, and `8421`.
- [x] 3.3 Support canonical measurement keys for `HR`, `PR`, `QRS`, `QT`, `QTC`, `P_AXIS`, `QRS_AXIS`, and `T_AXIS`.
- [x] 3.4 Map `8418`, `6227`, and `6228` into canonical status, comments, and formatted result text.
- [x] 3.5 Preserve raw GDT text and parsed repeated fields for audit/debug.

## 4. Validation

- [x] 4.1 Reject malformed record envelopes, invalid tag widths, missing CRLF, and bad byte lengths.
- [x] 4.2 Reject missing or mismatched `8100`.
- [x] 4.3 Reject required-field failures for the ZAC-23 minimum field set where required by message type.
- [x] 4.4 Record content and semantic warnings for recoverable issues such as unknown vendor `8410` mapping.
- [x] 4.5 Preserve validation errors/warnings in a structured shape for API/store inspection.

## 5. Integration

- [x] 5.1 Update GDT order creation to use the adapter for outbound `6302` generation.
- [x] 5.2 Update GDT result import to use the adapter for inbound `6310` parsing and canonical mapping.
- [x] 5.3 Keep existing independent GDT foundation storage and order/result matching behavior compatible.

## 6. Verification

- [x] 6.1 Add adapter tests for valid `6302` generation and `8100` validation.
- [x] 6.2 Add adapter tests for valid `6310` ECG measurement parsing.
- [x] 6.3 Add negative tests for bad record length and missing/mismatched `8100`.
- [x] 6.4 Add store/API regression tests that raw, parsed, canonical, and validation payloads are preserved.
- [x] 6.5 Run unit tests, Python compile checks, and OpenSpec validation.
