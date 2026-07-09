## Why

Healthcare Lab can create local DICOM MWL order intents and attempt to sync them to dcm4chee-arc, but operators still need a clear proof that a Healthcare Lab-created order is actually queryable from the dcm4chee MWL surface that APs use.

Recent local runtime verification also exposed two important operational boundaries: the dcm4chee MWL REST web application is exposed through the `WORKLIST` AE/web app, and dcm4chee rejects MWL creation when the referenced Patient ID does not already exist in the archive. ZAC-39 should make those boundaries visible in verification status and diagnostics instead of leaving users to infer them from raw sync failures.

## What Changes

- Add an explicit MWL queryability verification path for Healthcare Lab-created dcm4chee orders.
- Query dcm4chee MWL using supported dcm4chee MWL REST and/or operator-run DICOM MWL tooling, starting from the strongest identifiers already stored in the PACS/MWL ledger.
- Record verification attempts separately from creation/read-back sync attempts while updating the canonical PACS/MWL ledger with the latest verification status.
- Store enough returned MWL metadata to prove which order was found, including Patient ID, Issuer of Patient ID, Accession Number, Scheduled Station AE Title, Scheduled Procedure Step ID, Requested Procedure ID, Study Instance UID when present, and Worklist Label when present.
- Produce actionable diagnostics for common failure modes: dcm4chee unreachable, wrong AE/web app, missing patient precondition, empty MWL query result, identifier mismatch, unsupported endpoint/tooling, and ambiguous query results.
- Keep AP code changes out of scope.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extend the dcm4chee MWL order model with explicit MWL queryability verification, verification attempt audit, ledger status fields, and diagnostic behavior.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, frontend DICOM order inspection code if status is surfaced, `.env.example`/README diagnostics if needed, and tests under `tests/`.
- Affected systems: local PACS/MWL ledger, dcm4chee MWL REST path under `WORKLIST`, dcm4chee patient/order preconditions, Healthcare Lab order sync/attempt APIs, and future AP-facing MWL validation workflow.
- The change verifies order visibility; it does not require AP changes and does not implement AP C-STORE result ingestion.
