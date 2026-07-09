## 1. Result Model And Persistence

- [x] 1.1 Add local persistence for dcm4chee result/reconciliation records separate from the canonical MWL mapping.
- [x] 1.2 Store study, series, and instance identifiers plus modality, timestamps, profile/server source, viewer/retrieve links, and reconciliation diagnostics.
- [x] 1.3 Add migration/backfill behavior that preserves existing MWL mapping and attempt data.
- [x] 1.4 Make repeated refresh idempotent by stable DICOM UID keys where available.

## 2. Backend Refresh And Query

- [x] 2.1 Add a manual dcm4chee result refresh backend operation.
- [x] 2.2 Query the configured dcm4chee archive DICOMweb/QIDO study, series, and instance endpoints using strongest available patient/order identifiers.
- [x] 2.3 Parse dcm4chee DICOM JSON responses into normalized result metadata.
- [x] 2.4 Generate viewer and retrieval links from the dcm4chee profile when enough identifiers are available.
- [x] 2.5 Preserve local orders and prior result state when dcm4chee query fails.

## 3. Reconciliation Logic

- [x] 3.1 Match by Study Instance UID first.
- [x] 3.2 Match by Accession Number within profile/server namespace and validate Patient ID/Issuer.
- [x] 3.3 Match by Requested Procedure ID plus Scheduled Procedure Step ID when Study UID/Accession are unavailable.
- [x] 3.4 Treat weak patient/modality/time-window fallback as ambiguous unless exactly one active candidate exists.
- [x] 3.5 Classify no-result, wrong-patient, missing-accession, duplicate, ambiguous, unlinked, and query-failed states.

## 4. API / UI Surface

- [x] 4.1 Add a patient-level and/or order-level result refresh API.
- [x] 4.2 Expose DICOM results under patient payloads or a patient DICOM results endpoint.
- [x] 4.3 Add a refresh action in the patient/order workspace.
- [x] 4.4 Render patient-level expandable/dropdown DICOM results grouped by matched order and unresolved diagnostics.
- [x] 4.5 Show identifiers, modality, timestamps, reconciliation status, and viewer/open links.

## 5. Documentation

- [x] 5.1 Document the manual refresh workflow and why background polling is deferred.
- [x] 5.2 Document the archive DICOMweb query surface used for AP C-STORE results versus the MWL `WORKLIST` surface.
- [x] 5.3 Document expected AP metadata preservation and how mismatch diagnostics should be interpreted.

## 6. Verification

- [x] 6.1 Add tests for successful result reconciliation by Study Instance UID.
- [x] 6.2 Add tests for Accession Number plus Patient ID/Issuer matching.
- [x] 6.3 Add tests for Requested Procedure ID plus SPS ID matching.
- [x] 6.4 Add tests for ambiguous, duplicate, wrong-patient, missing-accession, unlinked, no-result, and query-failed diagnostics.
- [x] 6.5 Add API/response contract tests for patient-level DICOM result exposure.
- [x] 6.6 Add frontend coverage or static contract checks for refresh controls and expandable patient DICOM results.
- [x] 6.7 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
