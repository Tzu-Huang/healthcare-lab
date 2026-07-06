## 1. Scope and Boundary

- [x] 1.1 Confirm ZAC-20 scope against `PROJECT_BOUNDARY.md` before implementation.
- [x] 1.2 Decide whether listener settings are runtime-only or persisted.
- [x] 1.3 Decide whether result counts include patient-only unmatched ORU results.

## 2. ORU Persistence and Matching

- [x] 2.1 Add SQLite persistence for received ORU result records.
- [x] 2.2 Parse `ORU^R01` and `ORU^W01` enough to extract `MSH-10`, `PID-3`, `OBR-2`, and `OBR-3`.
- [x] 2.3 Match ORU messages to local orders by `PID-3 + OBR-2` and `PID-3 + OBR-3`.
- [x] 2.4 Store patient-only and fully unmatched ORU messages without hiding them from the UI.
- [x] 2.5 Add duplicate detection around `MSH-10` where practical.

## 3. Result Listener and ACKs

- [x] 3.1 Add local MLLP listener lifecycle for OIE -> lab-app results, defaulting to port `6665`.
- [x] 3.2 Add backend APIs for listener start, stop, status, and configuration.
- [x] 3.3 Return successful ACKs for accepted ORU messages.
- [x] 3.4 Return failure ACKs for parse failures and unsupported message types.

## 4. Patient-Centered OIE UI

- [x] 4.1 Remove the OIE topbar mode selector and related unused mode state.
- [x] 4.2 Add ADT Patients list with MRN, name, Taipei created time, order count, and result count.
- [x] 4.3 Add Selected Patient workspace with nested Orders and Results.
- [x] 4.4 Add ORM Preview and Send/Resend actions from order rows.
- [x] 4.5 Add listener status/configuration controls.
- [x] 4.6 Add Unmatched Results visibility.
- [x] 4.7 Use one shared HL7 preview for ADT, ORM, and ORU payloads.

## 5. Verification

- [x] 5.1 Add backend tests for ORU parsing, persistence, matching, and unmatched handling.
- [x] 5.2 Add backend tests for listener lifecycle and ACK behavior.
- [x] 5.3 Add API tests for patient/order/result OIE responses.
- [x] 5.4 Add frontend syntax checks for the OIE page refactor.
- [x] 5.5 Run the project test suite and OpenSpec validation for `patient-centered-oie-console`.
