## 1. Connection Profile And Docker Defaults

- [ ] 1.1 Add dcm4chee HL7 receiver settings to app config and `.env.example`.
- [ ] 1.2 Expose dcm4chee HL7 port `2575` in `deploy/docker-compose.yml`.
- [ ] 1.3 Include HL7 Patient sync settings in profile diagnostics.

## 2. Patient Sync Data Model

- [ ] 2.1 Add local persistence for dcm4chee Patient sync mapping/status per local Patient/profile/server namespace.
- [ ] 2.2 Add append-only Patient sync attempt history with HL7 payload, endpoint, ACK/error details, and timestamps.
- [ ] 2.3 Include dcm4chee Patient sync status in Patient API responses.

## 3. HL7 ADT Sync

- [ ] 3.1 Build dcm4chee ADT Patient payloads that use the same Patient ID and issuer namespace as MWL.
- [ ] 3.2 Add an MLLP client for sending ADT to dcm4chee and parsing ACK status.
- [ ] 3.3 Trigger ADT sync when a local DICOM Patient is created.
- [ ] 3.4 Preserve local Patient records and mark sync failure when dcm4chee is unreachable or rejects the ADT.

## 4. MWL Patient Precondition

- [ ] 4.1 Before dcm4chee MWL create, check the referenced Patient's dcm4chee sync status.
- [ ] 4.2 Attempt Patient sync preflight before MWL create when the Patient is not synced.
- [ ] 4.3 If Patient sync fails, preserve the local order and record a Patient precondition failure without POSTing MWL.
- [ ] 4.4 Keep `patient_missing` or a specific Patient sync error visible as the root cause during MWL verify.

## 5. UI And Documentation

- [ ] 5.1 Show dcm4chee Patient sync status on the Patient page.
- [ ] 5.2 Show Patient precondition status in the DICOM order workspace.
- [ ] 5.3 Document the dcm4chee Patient ADT sync flow, HL7 port defaults, and why STOW-RS is not used for Patient master sync.

## 6. Verification

- [ ] 6.1 Add tests for ADT payload generation and issuer alignment with MWL payload.
- [ ] 6.2 Add tests for successful Patient sync attempt recording.
- [ ] 6.3 Add tests for Patient sync failure preserving the local Patient.
- [ ] 6.4 Add tests for MWL create after Patient sync succeeds.
- [ ] 6.5 Add tests for MWL precondition failure preserving the local order without posting MWL.
- [ ] 6.6 Run OpenSpec validation and the relevant Healthcare Lab Python test suite.
