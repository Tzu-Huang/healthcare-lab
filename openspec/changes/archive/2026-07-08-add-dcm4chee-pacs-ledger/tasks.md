## 1. Data Model And Migration

- [x] 1.1 Add or extend local SQLite persistence for a canonical dcm4chee PACS/MWL mapping per Healthcare Lab order.
- [x] 1.2 Preserve existing dcm4chee create attempts as audit history and distinguish canonical mapping state from attempt status.
- [x] 1.3 Store local order identity, profile/server namespace, Patient ID, Issuer of Patient ID, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Study Instance UID, and Worklist Label.
- [x] 1.4 Store sync status, last sync time, retry count, last error details, and latest/raw request/response audit references where appropriate.

## 2. Creation And Read-Back

- [x] 2.1 Ensure dcm4chee order creation creates or updates the canonical mapping before outbound sync.
- [x] 2.2 Keep Healthcare Lab prefill limited to required patient/order/worklist fields and stable local workflow identifiers.
- [x] 2.3 Parse dcm4chee creation response identifiers when available and save them to the canonical mapping.
- [x] 2.4 Add a dcm4chee read-back path that can retrieve identifiers generated or normalized by dcm4chee after creation.
- [x] 2.5 Mark read-back failures without deleting the local Healthcare Lab order or losing the create attempt audit.

## 3. Retry And Idempotency

- [x] 3.1 Reuse an existing successful canonical mapping instead of POSTing a duplicate dcm4chee MWL item.
- [x] 3.2 Reuse stable local identifiers from the canonical mapping when retrying failed sync.
- [x] 3.3 For ambiguous timeout or unknown outcomes, attempt dcm4chee read-back before creating another MWL item.
- [x] 3.4 Track retry count and last retry/sync timestamps in the canonical mapping.

## 4. Reconciliation Lookup

- [x] 4.1 Add local lookup by Study Instance UID.
- [x] 4.2 Add local lookup by Accession Number within the dcm4chee profile/server namespace.
- [x] 4.3 Add local lookup by Requested Procedure ID plus Scheduled Procedure Step ID.
- [x] 4.4 Treat weak fallback matching as ambiguous unless exactly one active candidate exists.

## 5. UI / Documentation

- [x] 5.1 Surface canonical dcm4chee mapping state where local order dcm4chee status is shown, if practical for this ticket.
- [x] 5.2 Document the PACS/MWL ledger, read-back behavior, and retry/idempotency rules.
- [x] 5.3 Clarify that this enables future AP C-STORE result reconciliation but may not implement full result ingestion/display.

## 6. Verification

- [x] 6.1 Add tests for canonical mapping creation and schema migration.
- [x] 6.2 Add tests for response/read-back identifier persistence.
- [x] 6.3 Add tests proving retry does not create duplicate dcm4chee MWL orders after success.
- [x] 6.4 Add tests proving failed/ambiguous retry reuses stable identifiers and records retry metadata.
- [x] 6.5 Add tests for local reconciliation lookup precedence.
- [x] 6.6 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
