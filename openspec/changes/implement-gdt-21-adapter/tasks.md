## 1. Adapter Boundary

- [ ] 1.1 Add a GDT 2.1 adapter module or equivalent backend boundary outside the persistence layer.
- [ ] 1.2 Move or wrap existing record rendering/parsing helpers behind the adapter without changing API behavior.
- [ ] 1.3 Return structured parsed fields, canonical JSON, and validation notices from adapter operations.

## 2. `6302` Generation

- [ ] 2.1 Generate GDT 2.1 `6302` New Test Request messages from Healthcare Lab canonical order data.
- [ ] 2.2 Preserve fixed MVP `8402=EKG01` behavior.
- [ ] 2.3 Verify every generated record length and stabilized `8100` total length.
- [ ] 2.4 Keep existing `/api/gdt/orders` response compatibility, including the `payload` raw message alias.

## 3. `6310` Parsing

- [ ] 3.1 Parse GDT 2.1 `6310` Test Data Transfer messages through the adapter.
- [ ] 3.2 Normalize ECG measurement groups using `8410`, `8420`, and `8421`.
- [ ] 3.3 Support canonical measurement keys for `HR`, `PR`, `QRS`, `QT`, `QTC`, `P_AXIS`, `QRS_AXIS`, and `T_AXIS`.
- [ ] 3.4 Map `8418`, `6227`, and `6228` into canonical status, comments, and formatted result text.
- [ ] 3.5 Preserve raw GDT text and parsed repeated fields for audit/debug.

## 4. Validation

- [ ] 4.1 Reject malformed record envelopes, invalid tag widths, missing CRLF, and bad byte lengths.
- [ ] 4.2 Reject missing or mismatched `8100`.
- [ ] 4.3 Reject required-field failures for the ZAC-23 minimum field set where required by message type.
- [ ] 4.4 Record content and semantic warnings for recoverable issues such as unknown vendor `8410` mapping.
- [ ] 4.5 Preserve validation errors/warnings in a structured shape for API/store inspection.

## 5. Integration

- [ ] 5.1 Update GDT order creation to use the adapter for outbound `6302` generation.
- [ ] 5.2 Update GDT result import to use the adapter for inbound `6310` parsing and canonical mapping.
- [ ] 5.3 Keep existing independent GDT foundation storage and order/result matching behavior compatible.

## 6. Verification

- [ ] 6.1 Add adapter tests for valid `6302` generation and `8100` validation.
- [ ] 6.2 Add adapter tests for valid `6310` ECG measurement parsing.
- [ ] 6.3 Add negative tests for bad record length and missing/mismatched `8100`.
- [ ] 6.4 Add store/API regression tests that raw, parsed, canonical, and validation payloads are preserved.
- [ ] 6.5 Run unit tests, Python compile checks, and OpenSpec validation.
