## Why

Healthcare Lab now keeps a canonical dcm4chee PACS/MWL ledger and attempt audit trail, but operators still do not have a direct retry/status workflow for failed dcm4chee order sync. A dcm4chee outage, invalid profile, patient precondition failure, or read-back failure is visible only through compact order-list metadata, and retry requires reusing internal sync logic without an explicit API/UI action.

ZAC-38 makes failed dcm4chee order sync recoverable and inspectable from the Healthcare Lab order workspace while preserving the local order and avoiding duplicate dcm4chee MWL records.

## What Changes

- Add backend dcm4chee order sync/retry and attempt-history endpoints for Healthcare Lab orders.
- Enrich dcm4chee MWL status payloads with retryability and display-oriented status metadata without requiring a risky migration of existing stored status values.
- Surface latest dcm4chee sync details, retry count, timestamps, HTTP status, error type/text, and response payloads through order APIs.
- Add a DICOM order-list retry action for failed or pending dcm4chee sync states.
- Add selected-order inspection UI for the latest dcm4chee sync result and full attempt history.
- Preserve idempotency by continuing to route retries through the canonical PACS/MWL mapping ledger and stable identifier policy.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extend the existing dcm4chee MWL order model with explicit retry/status APIs and frontend inspection behavior.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, `frontend/static/app.js`, `frontend/templates/index.html`, `frontend/static/styles.css`, and tests under `tests/`.
- Affected systems: local dcm4chee order sync APIs, local SQLite attempt/mapping read models, Healthcare Lab order workspace UI, dcm4chee-arc MWL REST retry flow.
- This change does not replace the existing PACS/MWL ledger. It builds the user-facing retry and inspection workflow on top of that ledger.
