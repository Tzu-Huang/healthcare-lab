## Why

Healthcare Lab can create dcm4chee MWL orders and retain request/response audit metadata, but the current record is still attempt-oriented. ZAC-37 adds the durable PACS/MWL mapping ledger needed to reconcile future dcm4chee studies and AP C-STORE results back to the original Healthcare Lab order.

Some dcm4chee identifiers may be generated or normalized by dcm4chee-arc. Healthcare Lab should persist the identifiers it prefilled, read back the identifiers dcm4chee actually stored when possible, and keep one canonical mapping per Healthcare Lab order while retaining sync attempts for audit/debugging.

## What Changes

- Add a canonical local PACS/MWL ledger mapping each Healthcare Lab dcm4chee order to the dcm4chee MWL/study identifiers known for that order.
- Keep Healthcare Lab responsible for required local workflow intent and required MWL prefill fields, without assuming Healthcare Lab owns every dcm4chee-generated identifier.
- Persist AP-facing and dcm4chee-facing identifiers including Patient ID, Issuer of Patient ID, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Study Instance UID, Worklist Label, profile/server identity, and local order identity.
- Preserve request/response audit records for every dcm4chee creation/read-back attempt separately from the canonical mapping state.
- Add read-back handling after MWL creation so dcm4chee-generated or normalized identifiers can be stored once available.
- Add retry/idempotency behavior so repeated sync for the same Healthcare Lab order reuses the existing canonical mapping and does not create duplicate dcm4chee orders.
- Add local lookup support for result reconciliation by strongest identifiers, starting with Study Instance UID and then Accession Number, Requested Procedure ID, and Scheduled Procedure Step ID.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extend the dcm4chee MWL order model with a canonical PACS/MWL ledger, read-back identifier persistence, retry/idempotency rules, and local reconciliation lookup behavior.

## Impact

- Affected code: likely `backend/lab_store.py`, `app.py`, frontend order/local-order display code if mapping state is surfaced, `.env.example`, `README.md`, and tests under `tests/`.
- Affected systems: local SQLite dcm4chee PACS/MWL mapping ledger, local dcm4chee sync attempt audit records, dcm4chee-arc MWL REST/read-back API, future result reconciliation lookup paths.
- This change prepares result reconciliation by storing and querying mapping identifiers; full AP C-STORE result ingestion/display can remain a follow-up if it requires additional dcm4chee study polling or viewer workflows.
