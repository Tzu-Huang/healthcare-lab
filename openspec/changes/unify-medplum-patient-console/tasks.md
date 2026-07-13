## 1. Patient-Centered Structure

- [x] 1.1 Rename and restructure the Medplum template into a Patient list, selected Patient summary, workflow panel, and full-width bottom JSON preview while retaining functional DOM IDs.
- [x] 1.2 Add independent Patient selection and disclosure state with accessible disclosure controls.
- [x] 1.3 Render inline FHIR Orders and Results sections for expanded Patients using existing Patient-reference matching.

## 2. Workflow And Actions

- [x] 2.1 Preserve ServiceRequest and DiagnosticReport selection, live DiagnosticReport status, and related-resource navigation in the workflow panel.
- [x] 2.2 Wire inline Preview and non-destructive Retry actions without unintended Patient selection or disclosure changes.
- [x] 2.3 Preserve correct live, local submitted, fallback, and failed source labels in the bottom JSON console.

## 3. Layout And Responsive Behavior

- [x] 3.1 Add Medplum-specific Patient disclosure, nested table, summary/workflow, and local-overflow styles consistent with the other server consoles.
- [x] 3.2 Ensure desktop Patient-focused proportions and narrow-screen single-column reflow without page-level horizontal overflow.

## 4. Verification

- [x] 4.1 Update frontend contract tests for the Patient-Centered heading, disclosure state, inline Order/Result rollups, separated panels, actions, and bottom JSON console.
- [x] 4.2 Run JavaScript syntax checks and the relevant Python test suite.
- [x] 4.3 Run strict OpenSpec validation for the completed change.
