## 1. E2E Fixture And Evidence Model

- [x] 1.1 Define a deterministic demo DICOM patient/order preset for production-like verification.
- [x] 1.2 Capture the identifiers used during verification: Patient ID, Issuer, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Study Instance UID, Series Instance UID, SOP Instance UID when available, AE titles, endpoints, and timestamps.
- [x] 1.3 Add or reuse a verification evidence object that records step statuses for patient sync, MWL create, MWL queryability, AP return/C-STORE, result reconciliation, and UI-visible result state.
- [x] 1.4 Keep fixture data virtual and safe for local lab use only.

## 2. Production-Like Workflow Verification

- [ ] 2.1 Verify Healthcare Lab creates the dcm4chee patient precondition and MWL/order automatically from the demo patient/order.
- [ ] 2.2 Verify the order is queryable from the configured dcm4chee MWL surface.
- [ ] 2.3 Define the live AP handoff values required for MWL query and C-STORE result return.
- [ ] 2.4 Verify Healthcare Lab can refresh/reconcile returned dcm4chee results after AP C-STORE.
- [ ] 2.5 Ensure failures preserve useful diagnostics without deleting local patient/order/evidence state.

## 3. Simulated AP Return Fixture

- [x] 3.1 Add a repeatable simulated AP-return path for a DICOM order.
- [x] 3.2 Support a PDF artifact return record with artifact URL/path, media type, role, order identifiers, and display metadata.
- [x] 3.3 Support DICOM-style result metadata or object record with Study/Series/SOP UIDs, modality, patient/order identifiers, and viewer/retrieve metadata when available.
- [x] 3.4 Ensure simulated AP-return records reconcile or display through the same patient/order DICOM result surface used by live results where practical.
- [x] 3.5 Prevent simulated fixtures from being confused with live dcm4chee evidence by labeling source/mode clearly.

## 4. UI Verification

- [x] 4.1 Show AP-returned result status in the DICOM patient/order workspace.
- [x] 4.2 Show PDF artifact link/open metadata for simulated or live PDF-style AP returns.
- [x] 4.3 Show DICOM Study/Series/Instance hierarchy and identifiers for simulated or live DICOM-style AP returns.
- [x] 4.4 Show matched order and reconciliation status without requiring raw JSON inspection.
- [x] 4.5 Keep raw diagnostic/evidence details available for troubleshooting.

## 5. Operator SOP

- [ ] 5.1 Document service startup and smoke checks for Healthcare Lab and dcm4chee.
- [ ] 5.2 Document required ports, AE titles, endpoints, and the `WORKLIST` versus `DCM4CHEE` DICOMweb distinction.
- [ ] 5.3 Document the full live AP production-like verification path.
- [ ] 5.4 Document the simulated AP-return PDF/DICOM fixture path for frontend verification.
- [ ] 5.5 Document expected identifiers and where operators should record or inspect them.
- [ ] 5.6 Document troubleshooting for patient precondition, MWL visibility, C-STORE return, reconciliation, and UI display failures.

## 6. Verification

- [x] 6.1 Add automated tests for demo fixture creation and evidence shape.
- [x] 6.2 Add automated tests for simulated PDF AP-return display/exposure.
- [x] 6.3 Add automated tests for simulated DICOM metadata AP-return display/exposure.
- [x] 6.4 Add API/response contract tests for E2E verification evidence and AP-return status.
- [x] 6.5 Add frontend static or helper tests for AP-return result UI hooks.
- [x] 6.6 Run OpenSpec validation.
- [ ] 6.7 Run the relevant Healthcare Lab Python test suite.
- [ ] 6.8 Execute or document manual live AP/dcm4chee production-like verification with exact identifiers.
