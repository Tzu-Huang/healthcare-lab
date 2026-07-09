## Context

ZAC-34 defined the dcm4chee MWL/order contract and result matching precedence. ZAC-37 added the canonical PACS/MWL mapping ledger. ZAC-39 added explicit MWL queryability verification. ZAC-40 closes the first result loop by letting an operator refresh Healthcare Lab from dcm4chee after AP C-STORE has stored DICOM results.

Current boundaries:

- Healthcare Lab owns local workflow intent, local order state, generated identifiers, and reconciliation/audit metadata.
- dcm4chee-arc remains authoritative for DICOM study, series, instance, artifact, and viewer state.
- The AP is expected to preserve Study Instance UID when available, Accession Number, Patient ID, Issuer of Patient ID, Requested Procedure ID, and Scheduled Procedure Step ID in returned DICOM results.
- The first implementation should be explicit refresh, not background polling.

## Goals / Non-Goals

**Goals:**

- Add a manual refresh operation that queries dcm4chee-arc for new AP C-STORE results.
- Reconcile returned studies/series/instances to Healthcare Lab orders using the canonical ledger.
- Persist result metadata and reconciliation diagnostics separately from MWL sync attempts.
- Expose DICOM results and mismatch states under the patient view in an expandable/dropdown-style UI section.
- Generate viewer/retrieval links from the configured dcm4chee profile when enough identifiers are available.
- Keep local orders available regardless of result query or reconciliation outcome.

**Non-Goals:**

- Add a background poller, scheduler, webhook listener, or AP callback workflow.
- Implement AP-side code changes.
- Download or store full DICOM object bytes locally.
- Replace dcm4chee as the source of truth for PACS study/series/instance content.
- Claim weak patient/time-window matches as successful unless exactly one unambiguous active candidate exists.

## Decisions

1. Manual refresh is the first trigger.

   The operator should be able to refresh DICOM results from the patient/order workspace. The backend action should query dcm4chee, reconcile results, persist outcomes, and return updated patient/order result state. Background polling can be designed later after the reconciliation model is proven.

2. Result persistence should be separate from the MWL mapping row.

   The canonical MWL mapping remains the expected-identifier ledger. Returned results can include multiple series/instances, duplicate submissions, or mismatched candidates, so a dedicated result/reconciliation persistence shape is clearer than overloading the single mapping row.

3. Query the archive side for C-STORE results.

   MWL verification uses the `WORKLIST` application, but AP C-STORE results should be discovered from the dcm4chee archive DICOMweb/QIDO surface. The implementation should keep the profile distinction clear between MWL AE/web app and archive DICOMweb/query/retrieve endpoints.

4. Matching uses strongest identifiers first.

   Matching priority should be Study Instance UID, then Accession Number within profile/server namespace with Patient ID/Issuer validation, then Requested Procedure ID plus Scheduled Procedure Step ID. Patient ID, issuer, modality, and time-window matching are weak fallback signals and should produce ambiguity unless there is exactly one active candidate.

5. Diagnostics are first-class result states.

   Result refresh should record enough metadata to explain why a result did not match: empty query/no result, wrong patient, missing accession, duplicate study, ambiguous candidates, unlinked result, dcm4chee unreachable, and invalid profile/query configuration.

## Data Model Direction

Add local result/reconciliation persistence with fields such as:

- local Healthcare Lab patient id and order id when matched
- mapping id when matched to a canonical PACS/MWL mapping
- profile name, server identity, archive AE or DICOMweb source identity
- Study Instance UID, Series Instance UID, SOP Instance UID
- Accession Number, Patient ID, Issuer of Patient ID
- Requested Procedure ID and Scheduled Procedure Step ID when present
- modality, study date/time, series date/time, instance timestamp when available
- viewer URL, study retrieve URL, series retrieve URL, instance retrieve URL when derivable
- reconciliation status such as `matched`, `no_result`, `ambiguous`, `duplicate`, `wrong_patient`, `missing_accession`, `unlinked`, or `query_failed`
- match method, match confidence/strength, selected mapping/order id, diagnostics payload, raw or summarized query payload
- created/updated/refreshed timestamps

Refresh/reconciliation audit may either be a dedicated attempt table or a compact event trail attached to the result table, as long as repeated refreshes are debuggable.

## API / UI Direction

Backend options:

- Add a patient-level refresh endpoint such as `POST /api/patients/<id>/dcm4chee-results-refresh`.
- Optionally add an order-level endpoint if the existing DICOM order workspace is the simplest first UI entry point.
- Include patient-level `dicomResults` in the relevant patient/detail payload or in a dedicated patient DICOM results endpoint.
- Return both matched results and unresolved/mismatch diagnostics so operators can debug AP metadata issues.

Frontend direction:

- Add a refresh action near the patient DICOM/order area.
- Render DICOM results below the patient as an expandable/dropdown-style section.
- Group result rows by matched order where possible, with a separate section for unlinked/ambiguous results.
- Show key identifiers, modality, timestamps, reconciliation status, and viewer/open links.

## Risks / Trade-offs

- [Risk] AP may preserve identifiers differently than expected. -> Mitigation: record mismatch diagnostics and avoid weak automatic matches.
- [Risk] dcm4chee QIDO query behavior may differ between study, series, and instance endpoints. -> Mitigation: retain query targets and raw/summarized responses in refresh diagnostics.
- [Risk] Multiple returned studies can share weak patient/time criteria. -> Mitigation: require strong identifiers for automatic match and surface ambiguous results.
- [Risk] Patient-level UI can become noisy. -> Mitigation: group by order and use expandable sections instead of pushing every instance into the default view.

## Open Questions

- Should the first refresh endpoint be patient-level only, order-level only, or both?
- Should repeated refresh update existing result rows by DICOM UID keys, or append each refresh observation as history plus maintain current-state rows?
- Should unlinked results be discoverable globally, or only when refreshing a selected patient?
