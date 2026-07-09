## Context

ZAC-41 sits after the dcm4chee backend workflow is mostly present:

- Healthcare Lab can create DICOM MWL orders and persist canonical dcm4chee mapping identifiers.
- Order sync retry, MWL verification, and attempt history APIs exist.
- Patient-level dcm4chee result refresh and reconciliation APIs exist.
- Patient payloads can expose `dcm4chee.dicomResults` and `resultCount`.
- Current frontend hooks render a basic DICOM result section and order MWL details, but the result view is flat and not yet close to the original dcm4chee-arc PACS browsing model.

User preference from exploration:

- Use Healthcare Lab colors, spacing, cards/panels, buttons, and status treatment.
- Use dcm4chee-arc-like dropdown/expand interaction and table structure for PACS result metadata.
- Do not clone dcm4chee-arc's full UI chrome.

## Goals / Non-Goals

**Goals:**

- Make the selected DICOM order detail the clearest place to answer:
  - Did MWL sync to dcm4chee succeed?
  - Is the MWL order queryable/visible for AP?
  - Has AP returned a C-STORE result?
  - Did reconciliation match the result to this order?
- Add a patient/order-centered PACS result browser using Study -> Series -> Instance hierarchy.
- Preserve key DICOM identifiers and dcm4chee-style field names in tables.
- Keep diagnostics readable through Healthcare Lab status pills and detail blocks.
- Keep result refresh manual.

**Non-Goals:**

- No new background polling, scheduler, AP callback, or websocket updates.
- No backend result model redesign unless a small response-shaping helper is needed.
- No replacement of Healthcare Lab styling with a dcm4chee-arc clone.
- No local DICOM object download or image viewer implementation.

## UX Direction

The order detail should show a compact status strip or detail blocks for:

- `MWL Sync`: synced, pending, retry needed, failed, or patient precondition failed.
- `MWL Queryable`: verified, not verified, verification failed, ambiguous, or blocked by patient/profile failure.
- `AP C-STORE Result`: result returned, no result, query failed, or needs review.
- `Reconciliation`: matched, ambiguous, duplicate, wrong patient, unlinked, missing accession, or no result.

The patient DICOM results area should be a Healthcare Lab panel containing a PACS-style browser:

- Matched order groups first.
- Each order group contains Study rows.
- Each Study row can expand to Series rows.
- Each Series row can expand to Instance rows.
- Unlinked or ambiguous diagnostics appear in a separate group after matched orders.

## Table Vocabulary

Prefer DICOM/dcm4chee field names in result tables:

- Patient ID
- Issuer of Patient ID
- Accession Number
- Study Instance UID
- Series Instance UID
- SOP Instance UID
- Modality
- Study Date/Time
- Series Date/Time
- Instance Date/Time
- Requested Procedure ID
- Scheduled Procedure Step ID
- Scheduled Station AE Title

Healthcare Lab labels can wrap these fields at the workflow layer:

- MWL Sync
- MWL Queryable
- AP C-STORE Result
- Reconciliation
- Diagnostics

## Data Shape Direction

The frontend can group existing `patient.dcm4chee.dicomResults` client-side by:

- `orderRecordId` or unresolved status group
- `studyInstanceUid`
- `seriesInstanceUid`
- `sopInstanceUid`

When the backend already returns study, series, and instance result rows separately, the UI should merge them into a navigable hierarchy without discarding rows that only have partial identifiers. Diagnostic rows such as `no_result` and `query_failed` should remain visible even when no Study UID exists.

## Risks / Trade-offs

- Existing result rows may not always include enough identifiers to form a complete hierarchy. The UI should degrade to a diagnostic row instead of hiding the result.
- Multiple rows can represent the same study at different levels. The grouping logic must avoid visually duplicating a study while still showing available Series/Instance detail.
- dcm4chee-like tables can become wide. Use horizontal scrolling inside the result browser while keeping Healthcare Lab page layout stable.
- Status names must remain operator-friendly. Use workflow status labels in summary blocks and DICOM field names inside PACS tables.
