## Context

The dcm4chee page already has Patient, MWL Order, Patient sync, and PACS result data, but its current composition distributes one workflow across a short Patient table, a standalone selected-Patient Orders block, a separate workflow card, and raw preview output. This conflicts with the OIE page's clearer patient-centered rhythm and creates two concrete usability failures: Patient context is easy to lose, and long dcm4chee metadata can escape the card boundary.

This change is frontend-only. Existing API responses and client-side dcm4chee result grouping remain the data source. The implementation must preserve order retry/send/verify actions, manual result refresh, viewer/retrieve actions, unresolved diagnostics, and responsive behavior.

## Goals / Non-Goals

**Goals:**

- Give the Patient list the dominant width and visual density used by the OIE console.
- Separate Patient selection from per-row Order/Result disclosure.
- Put one selected Patient preview directly below the complete Patient list.
- Remove the duplicate standalone `MWL Selected Patient Orders` presentation.
- Present DICOM result metadata in structured, labeled tables.
- Keep Patient sync fields and diagnostics inside their card at every supported width.

**Non-Goals:**

- No backend API, persistence, reconciliation, or dcm4chee integration changes.
- No redesign of the OIE console itself.
- No automatic polling or new result refresh behavior.
- No replacement DICOM viewer or raw DICOM parser.
- No removal of existing order, retry, verify, refresh, viewer, or retrieve capabilities.

## Decisions

### 1. Maintain selection and disclosure as independent client state

`selectedDcm4cheePatientId` remains the single Patient whose preview is shown. A separate set of expanded Patient identifiers controls inline disclosure. Clicking the Patient row updates selection and preview without toggling disclosure; clicking the leading chevron stops row propagation and only expands or collapses that Patient's details.

This mirrors the confirmed interaction contract and avoids the ambiguity of a row click both navigating and expanding. Reusing one state variable for both behaviors was rejected because it would make preview updates collapse unrelated content and prevent multiple rows from remaining inspectable.

### 2. Use one dominant Patient panel with a preview after the list

The Patient list occupies the wider console column and is allowed more vertical space than the current short scroll region. Expanded Order and Result content is inserted as a full-width detail row immediately after its Patient row. The selected Patient preview is rendered once after the entire Patient table, not inside an expanded row.

The standalone `MWL Selected Patient Orders` heading and table are removed. Existing order actions move with the Order table inside the expanded Patient detail. Any surviving workflow controls may still consume the selected Patient/order state, but they must not recreate a second selected-Patient Orders list.

### 3. Render DICOM results from field projections, not serialized objects

The result renderer projects each Study, Series, Instance, or diagnostic record into explicit columns with DICOM-oriented labels. Existing grouping and identifiers remain available, including Accession Number, Study/Series/SOP Instance UID, Modality, Patient ID, Issuer, Requested Procedure ID, and Scheduled Procedure Step ID. Missing values render as a stable placeholder.

The normal Result presentation never assigns `JSON.stringify(result)` or an equivalent serialized object to visible output. Retained low-level diagnostic payloads, if still needed, must be behind a deliberate diagnostic action and are not a substitute for the table.

### 4. Constrain sync details at the field and grid-item boundaries

The Patient sync card uses `min-width: 0` on grid/flex children and `overflow-wrap: anywhere` (with normal whitespace) on field values that can be long, including Last Sync, endpoint, Error Type, and Error. The layout may collapse from two columns to one when space is insufficient. Page-level horizontal scrolling is not used as the fix.

Clipping the values was rejected because timestamps and diagnostics are operator evidence. Unconditional ellipsis was also rejected because it hides the error content users need to act on.

### 5. Verify DOM contracts and interaction behavior

Static tests will assert that the obsolete Orders section is absent and the new preview/table hooks are present. Where practical with existing tooling, behavior tests will cover row selection versus disclosure, structured result rendering, and sync-card wrapping rules. The relevant Python suite and strict OpenSpec validation remain the proposal gates.

## Risks / Trade-offs

- **Wide nested DICOM tables can exceed the Patient panel** → Keep overflow local to the nested table wrapper while preventing the page or sync card from overflowing.
- **Multiple expanded Patients can produce a very tall page** → Preserve independent disclosure as confirmed, while defaulting all rows to collapsed and keeping each chevron explicit.
- **Moving Order actions can break event propagation** → Stop action-button propagation and test that actions do not unintentionally select or collapse a Patient.
- **Partial result records may not populate every column** → Render placeholders and retain unresolved diagnostic rows instead of dumping raw data or hiding the record.
- **Existing selectors/workflow controls may duplicate context after the move** → Remove only duplicated list presentation and review remaining controls against a single-responsibility layout during implementation.

## Migration Plan

1. Update the template structure and stable DOM hooks.
2. Refactor Patient selection/disclosure and move Order/Result rendering into the expanded row.
3. Add the selected Patient preview below the list and remove the standalone Orders block.
4. Replace raw DICOM Result output with structured field tables.
5. Apply responsive width/wrapping rules to the Patient and sync panels.
6. Update tests and verify the complete console behavior.

Rollback is a normal revert of the frontend and test commit because no data or API migration is involved.

## Open Questions

None. Patient row selection, chevron disclosure, preview placement, result-table format, and removal of the standalone Orders section were explicitly confirmed during exploration.
