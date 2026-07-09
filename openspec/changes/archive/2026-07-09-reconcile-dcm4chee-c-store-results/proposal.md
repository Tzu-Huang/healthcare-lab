## Why

Healthcare Lab can create dcm4chee MWL orders, retain a canonical PACS/MWL mapping ledger, and verify whether an order is queryable from the AP-facing MWL surface. The remaining loop is result return: after AP completes processing and C-STOREs DICOM results into dcm4chee-arc, Healthcare Lab needs an operator-visible way to refresh from dcm4chee, detect newly stored studies, and reconcile those results back to the original local order.

The AP integration expectation for this change is that returned DICOM results preserve the key MWL/order identifiers: Study Instance UID when available, Accession Number, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID. That lets Healthcare Lab prefer deterministic matching over patient/time heuristics.

## What Changes

- Add a manual dcm4chee result refresh/reconciliation action that queries dcm4chee-arc for returned DICOM study, series, and instance metadata.
- Use the existing canonical PACS/MWL ledger as the source of expected identifiers for matching returned AP C-STORE results back to Healthcare Lab orders.
- Persist reconciled result metadata, including Study Instance UID, Series Instance UID, SOP Instance UID, modality, relevant timestamps, source query metadata, viewer/retrieval links, and reconciliation status.
- Detect and expose no-result, matched, ambiguous, duplicate, wrong-patient, missing-accession, and unlinked-result states for debugging.
- Surface DICOM results under the patient view as an expandable/dropdown-style section, while keeping backend result persistence independent enough to support multiple studies, series, or instances per order.
- Keep background polling/callback processing out of scope for the first version; operators refresh explicitly.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extend the dcm4chee MWL/PACS workflow with manual AP C-STORE result refresh, result reconciliation persistence, patient-level result display, and mismatch diagnostics.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, frontend patient/order DICOM result display code, `.env.example`/README diagnostics if endpoint naming needs clarification, and tests under `tests/`.
- Affected systems: local SQLite dcm4chee PACS/MWL ledger, new local result/reconciliation persistence, dcm4chee archive DICOMweb QIDO/WADO endpoints, dcm4chee viewer-link configuration, Healthcare Lab patient payloads.
- The change assumes AP preserves the agreed DICOM identifiers. If AP behavior changes, reconciliation should fail visibly rather than silently attach a result to the wrong order.
