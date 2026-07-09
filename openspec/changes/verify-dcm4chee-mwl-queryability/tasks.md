## 1. Verification Model

- [x] 1.1 Add or extend local persistence for latest MWL verification status on the canonical PACS/MWL mapping.
- [x] 1.2 Add verification attempt audit support with operation type, method, request target, query criteria, response status/body, match metadata, and diagnostics.
- [x] 1.3 Preserve existing create/read-back/retry attempt behavior and keep verification distinguishable from sync status.

## 2. Backend Verification

- [x] 2.1 Add a backend MWL verification operation for local DICOM MWL orders.
- [x] 2.2 Build dcm4chee MWL REST query criteria from canonical ledger identifiers.
- [x] 2.3 Query the configured MWL REST endpoint and parse returned DICOM JSON.
- [x] 2.4 Match returned MWL items against expected identifiers and record proof metadata for the selected match.
- [x] 2.5 Classify verification failures into actionable diagnostic categories such as unreachable, invalid profile, patient missing, empty result, mismatch, ambiguity, or unsupported endpoint.
- [x] 2.6 Keep local orders and existing mappings available when verification fails.

## 3. API / UI Surface

- [x] 3.1 Add an explicit verification API endpoint or equivalent backend action for a local DICOM order.
- [x] 3.2 Include latest verification status and proof/diagnostic metadata in order payloads.
- [x] 3.3 Surface latest verification status in the DICOM order inspection UI where practical.
- [x] 3.4 Ensure attempt history clearly identifies verification attempts.

## 4. Documentation

- [x] 4.1 Document the local dcm4chee `WORKLIST` MWL REST target and how it differs from the `DCM4CHEE` archive QIDO/WADO/STOW target.
- [x] 4.2 Document patient precondition behavior and expected diagnostics when a patient is missing from dcm4chee.
- [x] 4.3 Document how operators can prove which order was found.

## 5. Verification

- [x] 5.1 Add backend tests for successful MWL verification with matching returned identifiers.
- [x] 5.2 Add tests for empty MWL response and identifier mismatch diagnostics.
- [x] 5.3 Add tests for ambiguous matches.
- [x] 5.4 Add tests for patient-missing and endpoint/profile failure diagnostics.
- [x] 5.5 Add API/response contract tests for verification status exposure.
- [x] 5.6 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
