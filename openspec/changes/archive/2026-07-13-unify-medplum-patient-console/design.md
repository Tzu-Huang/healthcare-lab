## Context

The current Medplum page already loads a Patient-centered inventory and supports Patient selection, ServiceRequest and DiagnosticReport controls, live DiagnosticReport reads, related resource navigation, retry, and raw JSON preview. Unlike the OIE, GDT, and dcm4chee pages, its Patient table is only a selector: Orders and Results are discovered later through a dense selected-Patient panel. The change is frontend-only and must keep every existing API and canonical-data rule intact.

## Goals / Non-Goals

**Goals:**

- Give Medplum the same `Patient-Centered Console` visual and interaction rhythm used by the other server pages.
- Make the Patient list the primary navigation surface and disclose each Patient's FHIR Orders and Results inline.
- Keep Patient selection independent from disclosure so preview context is predictable.
- Separate Patient identity, workflow controls, related resources, and raw JSON into scan-friendly regions.
- Preserve live Medplum reads, local fallback labels, retry, status filtering, and responsive behavior.

**Non-Goals:**

- No API, persistence, OAuth, sync, FHIR search, or resource-mapping changes.
- No new rich FHIR viewer and no destructive Medplum actions.
- No attempt to make protocol-specific details identical across all server pages.

## Decisions

### 1. Reuse the established selection-plus-disclosure model

`selectedMedplumPatientId` remains the selected Patient for the summary and workflow panels. A separate `expandedMedplumPatientIds` set controls inline disclosure. Clicking a row selects it; clicking the leading disclosure button stops propagation and only expands or collapses that Patient.

This follows the dcm4chee/OIE interaction and avoids a row click unexpectedly changing both navigation and layout state.

### 2. Group resources by operator intent

Expanded Patient rows contain two sections. `ServiceRequest` and `Task` are presented as FHIR Orders; `DiagnosticReport`, `Observation`, and `DocumentReference` are presented as FHIR Results. Each resource remains a normal Medplum inventory record and continues to use existing reference-matching logic.

Grouping by workflow is more useful than one mixed resource list, while retaining the actual resource type in every row avoids hiding FHIR semantics.

### 3. Keep live results in the workflow panel and raw JSON at the bottom

The right-side workflow panel retains ServiceRequest/DiagnosticReport controls, live result rollup, and related resources. The selected Patient summary becomes a separate compact panel. The existing raw JSON console remains the only full payload preview and spans the page below the patient-focused area.

This preserves the existing live-fetch state machine and avoids duplicating payload previews inside expanded rows.

### 4. Build on existing rendering and retry functions

New nested rows call the current local/live preview functions and reuse `retryButtonForMedplumRecord`. Existing Medplum record filtering and relationship helpers remain the source of truth. Template IDs required by existing fetch and selection handlers are retained.

### 5. Use local overflow and responsive collapse

Nested tables scroll within their own wrappers when necessary. Desktop uses a Patient-dominant two-column grid; narrower widths collapse Patient, summary/workflow, and JSON regions into a single column without page-level horizontal overflow.

## Risks / Trade-offs

- **A Patient with many resources can create a tall disclosure row** -> Rows start collapsed and disclosure remains explicit and independent per Patient.
- **Live reports are not always present in the local inventory** -> The workflow panel remains the canonical live report surface; inline Results show available local ledger resources and the live report count already associated with the selected fetch state.
- **Action clicks could also select the Patient row** -> Disclosure, Preview, and Retry handlers stop propagation.
- **Existing tests depend on stable DOM IDs** -> Retain functional IDs and update/add contract assertions around the new wrappers and render helpers.

## Migration Plan

1. Restructure the Medplum template while retaining functional element IDs.
2. Add independent disclosure state and nested Order/Result renderers.
3. Recompose selected Patient and workflow panels around the existing controls.
4. Add responsive and nested-table styles.
5. Update frontend contract tests and run JavaScript, Python, and strict OpenSpec validation.

Rollback is a normal revert of the frontend and test commits; no data migration is involved.

## Open Questions

None. The target layout and retained functionality were confirmed before implementation.
