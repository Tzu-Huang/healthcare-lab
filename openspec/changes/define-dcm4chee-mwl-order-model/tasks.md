## 1. MWL Order Contract

- [x] 1.1 Document the dcm4chee MWL order-first source-of-truth boundary.
- [x] 1.2 Document patient demographic fields included in MWL/order creation.
- [x] 1.3 Document Scheduled Procedure Step and order fields included in MWL/order creation.

## 2. Identifier Strategy

- [x] 2.1 Define Healthcare Lab generated sequential identifiers for local order, patient, accession, requested procedure, and scheduled procedure step.
- [x] 2.2 Define explicit Patient ID issuer behavior.
- [x] 2.3 Define valid Study Instance UID generation using a configured DICOM UID root plus unique suffix.
- [x] 2.4 Define how externally generated or observed dcm4chee/AP identifiers are recorded.

## 3. Mapping And Reconciliation

- [x] 3.1 Define the local mapping ledger fields needed by future implementation tickets.
- [x] 3.2 Define AP C-STORE result reconciliation precedence.
- [x] 3.3 Define ambiguity handling for weak fallback matches.

## 4. Verification

- [x] 4.1 Run OpenSpec validation for the new proposal.
