## Why

Healthcare Lab can now load a validated dcm4chee-arc connection profile, and the MWL order model defines the required patient, order, and reconciliation identifiers. The next missing step is runtime creation of dcm4chee MWL/order records from Healthcare Lab orders.

ZAC-36 implements the first dcm4chee runtime integration path so AP devices can later query orders from dcm4chee-arc instead of relying on manual dcm4chee UI entry.

## What Changes

- Implement a backend dcm4chee MWL creation path from Healthcare Lab ECG orders.
- Use the selected dcm4chee profile, defaulting to `local-dcm4chee`, for archive identity, MWL AE title, default Scheduled Station AE Title, and DICOMweb/MWL REST endpoint construction.
- Use the dcm4chee MWL REST API as the supported creation mechanism:
  - `POST /dcm4chee-arc/aets/{AETitle}/rs/mwlitems`
  - `Content-Type: application/dicom+json`
- Build DICOM JSON payloads containing required patient demographic fields and Scheduled Procedure Step/order fields.
- Generate and persist valid Healthcare Lab identifiers, including Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, and Study Instance UID using a configured DICOM UID root.
- Handle the dcm4chee Patient precondition explicitly: MWL creation must report a clear status when dcm4chee rejects the request because the patient does not exist.
- Save outbound request payload, response status/body, generated identifiers, and error details for audit/debugging.
- Preserve the Healthcare Lab local order when dcm4chee MWL creation fails, marking only the dcm4chee sync attempt as failed or pending.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Implement dcm4chee MWL order creation from Healthcare Lab orders using the selected dcm4chee profile and MWL REST creation path.

## Impact

- Affected code: likely `backend/lab_store.py`, `app.py`, frontend order/local-order display code if dcm4chee sync status is surfaced, `.env.example`, `README.md`, and tests under `tests/`.
- Affected systems: local SQLite order records, local dcm4chee mapping/audit ledger, dcm4chee-arc MWL REST API, dcm4chee local Docker runtime.
- No AP MWL query, C-STORE result reconciliation, or viewer-link consumption is implemented in this change.
- HL7 ORM feeding is deferred as an alternative integration path and is not the ZAC-36 implementation route.
