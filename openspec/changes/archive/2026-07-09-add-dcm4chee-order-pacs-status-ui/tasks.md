## 1. DICOM Order Status Detail

- [ ] 1.1 Update selected DICOM order detail to show MWL Sync, MWL Queryable, AP C-STORE Result, and Reconciliation status.
- [ ] 1.2 Keep retry, verify, and attempt history actions visible from the DICOM order workflow.
- [ ] 1.3 Show key MWL/order identifiers in a stable Healthcare Lab detail block.
- [ ] 1.4 Surface latest sync, verification, result refresh, and reconciliation diagnostics without requiring raw JSON parsing.

## 2. PACS-Style Result Browser

- [ ] 2.1 Group patient DICOM results by matched order, with a separate unresolved diagnostics group.
- [ ] 2.2 Render expandable Study rows with Accession Number, Study Instance UID, Modality, Study Date/Time, reconciliation status, and viewer action.
- [ ] 2.3 Render nested Series rows with Series Instance UID, Modality, Series Date/Time, and retrieve action when available.
- [ ] 2.4 Render nested Instance rows with SOP Instance UID, Modality, Instance Date/Time, and retrieve action when available.
- [ ] 2.5 Keep Healthcare Lab visual styling while using dcm4chee-like dropdown/table interaction for Study -> Series -> Instance.

## 3. Refresh And Actions

- [ ] 3.1 Add or refine a manual result refresh action close to the patient/order DICOM result browser.
- [ ] 3.2 Ensure refresh updates selected patient/order detail without forcing users to leave the workflow.
- [ ] 3.3 Preserve viewer/open link behavior for matched studies.
- [ ] 3.4 Preserve copy/retrieve link behavior where URLs are available.

## 4. Verification

- [ ] 4.1 Add or update frontend static tests for DICOM order status labels and result browser hooks.
- [ ] 4.2 Add or update tests for Study/Series/Instance grouping behavior if a pure helper is introduced.
- [ ] 4.3 Run relevant Python tests.
- [ ] 4.4 Run OpenSpec validation for this change.
