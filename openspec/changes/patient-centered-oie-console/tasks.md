## 1. Scope and Boundary

- [ ] 1.1 Confirm ZAC-20 scope against `repo/PROJECT_BOUNDARY.md` before implementation.
- [ ] 1.2 Decide whether listener settings are runtime-only or persisted.
- [ ] 1.3 Decide whether result counts include patient-only unmatched ORU results.

## 2. ORU Persistence and Matching

- [ ] 2.1 Add SQLite persistence for received ORU result records.
- [ ] 2.2 Parse `ORU^R01` and `ORU^W01` enough to extract `MSH-10`, `PID-3`, `OBR-2`, and `OBR-3`.
- [ ] 2.3 Match ORU messages to local orders by `PID-3 + OBR-2` and `PID-3 + OBR-3`.
- [ ] 2.4 Store patient-only and fully unmatched ORU messages without hiding them from the UI.
- [ ] 2.5 Add duplicate detection around `MSH-10` where practical.

## 3. Result Listener and ACKs

- [ ] 3.1 Add local MLLP listener lifecycle for OIE -> lab-app results, defaulting to port `6665`.
- [ ] 3.2 Add backend APIs for listener start, stop, status, and configuration.
- [ ] 3.3 Return successful ACKs for accepted ORU messages.
- [ ] 3.4 Return failure ACKs for parse failures and unsupported message types.

## 4. Patient-Centered OIE UI

- [ ] 4.1 Remove the OIE topbar mode selector and related unused mode state.
- [ ] 4.2 Add ADT Patients list with MRN, name, Taipei created time, order count, and result count.
- [ ] 4.3 Add Selected Patient workspace with nested Orders and Results.
- [ ] 4.4 Add ORM Preview and Send/Resend actions from order rows.
- [ ] 4.5 Add listener status/configuration controls.
- [ ] 4.6 Add Unmatched Results visibility.
- [ ] 4.7 Use one shared HL7 preview for ADT, ORM, and ORU payloads.

## 5. Verification

- [ ] 5.1 Add backend tests for ORU parsing, persistence, matching, and unmatched handling.
- [ ] 5.2 Add backend tests for listener lifecycle and ACK behavior.
- [ ] 5.3 Add API tests for patient/order/result OIE responses.
- [ ] 5.4 Add frontend syntax checks for the OIE page refactor.
- [ ] 5.5 Run the project test suite and OpenSpec validation for `patient-centered-oie-console`.
