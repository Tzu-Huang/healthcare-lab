## Why

Healthcare Lab already has the backend pieces needed to create dcm4chee MWL orders, retry and inspect MWL sync attempts, verify MWL queryability, refresh AP C-STORE results from dcm4chee-arc, reconcile returned DICOM metadata, and expose viewer/retrieve links. The remaining gap is presentation: users need a patient/order-centered frontend that makes the full dcm4chee order and PACS result state readable without switching mental models between local orders, MWL verification, and PACS study metadata.

The UI should keep Healthcare Lab's visual language for colors, spacing, panels, status pills, and buttons. For the DICOM result browser itself, it should borrow the dcm4chee-arc style of hierarchical PACS browsing: expandable Study rows, nested Series tables, and nested Instance details with DICOM field labels.

## What Changes

- Refine the DICOM order detail view so one selected order clearly shows MWL sync, MWL queryability, AP C-STORE result, reconciliation, identifiers, retry actions, verification actions, and diagnostics.
- Add a result refresh entry point close to the DICOM order/patient workflow, not only as a generic patient table action.
- Replace the current flat patient DICOM result table with an expandable PACS-style browser grouped by matched order and unresolved diagnostics.
- Present returned DICOM results as Study -> Series -> Instance hierarchy with DICOM/dcm4chee-style labels while preserving Healthcare Lab colors and layout.
- Surface viewer links and retrieve links where available without hiding reconciliation problems such as no result, ambiguous match, duplicate study, wrong patient, unlinked result, or query failure.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Improve frontend inspection of dcm4chee MWL/order state and AP C-STORE PACS result state with Healthcare Lab styling and dcm4chee-like Study/Series/Instance browsing.

## Impact

- Affected code: likely `frontend/static/app.js`, `frontend/static/styles.css`, frontend template hooks if extra containers are needed, and tests under `tests/`.
- Affected backend: expected to be minimal because result refresh, MWL retry, MWL verification, attempt history, result metadata, and viewer/retrieve links already exist.
- Affected users: operators inspecting whether a local DICOM MWL order is synced to dcm4chee, visible to AP, and completed by AP C-STORE result return.
- Visual constraint: Healthcare Lab remains the primary visual system; dcm4chee-arc influences only the PACS result hierarchy, dropdown/expand interaction, and table vocabulary.
