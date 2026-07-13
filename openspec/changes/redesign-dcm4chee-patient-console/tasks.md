## 1. Patient-Centered Structure

- [ ] 1.1 Restructure the dcm4chee template so the Patient list is the dominant, longer workspace and one selected Patient preview sits below the complete list.
- [ ] 1.2 Remove the standalone `MWL Selected Patient Orders` heading and table without removing required order workflow actions.
- [ ] 1.3 Update Patient row selection so it refreshes the below-list preview without changing disclosure state.
- [ ] 1.4 Update the leading Patient disclosure control, accessible expanded state, and event propagation so it independently expands or collapses inline details.

## 2. Inline Orders And Results

- [ ] 2.1 Render each expanded Patient's Orders in an inline structured table with existing send, retry, verify, preview, and inspection actions where applicable.
- [ ] 2.2 Render each expanded Patient's DICOM Results as structured DICOM-field tables, preserving Study/Series/Instance hierarchy and unresolved diagnostic rows.
- [ ] 2.3 Remove normal-path raw object or JSON printing from the DICOM Result presentation while retaining operator-readable missing-value and diagnostic handling.
- [ ] 2.4 Confirm order/result actions do not unintentionally toggle disclosure or select the wrong Patient.

## 3. Layout And Responsive Behavior

- [ ] 3.1 Increase the usable Patient list width and height to match the OIE-style workspace proportions at desktop widths.
- [ ] 3.2 Constrain `dcm4chee Patient Sync` fields with reflow and long-value wrapping for endpoint, timestamp, Error Type, and Error content.
- [ ] 3.3 Keep any unavoidable wide DICOM table scrolling inside its local table wrapper and prevent page-level horizontal overflow.
- [ ] 3.4 Verify Patient list, preview, expanded tables, workflow controls, and sync card reflow at the repository's supported responsive breakpoints.

## 4. Verification

- [ ] 4.1 Update frontend contract tests for the dominant Patient workspace, separate preview placement, disclosure hooks, and removal of `MWL Selected Patient Orders`.
- [ ] 4.2 Add or update tests that assert structured DICOM Result fields are rendered without raw object/JSON output.
- [ ] 4.3 Add or update tests for sync-card containment and selection-versus-disclosure behavior using the available test tooling.
- [ ] 4.4 Run the relevant Python test suite and frontend syntax or browser checks available in the repository.
- [ ] 4.5 Run strict OpenSpec validation and record verification evidence in the change workflow.
