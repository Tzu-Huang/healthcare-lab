## Why

Healthcare Lab already has local ADT patient inventory and local ORM order sending to OIE. The next useful integration loop is patient-centered: select a patient, inspect their local orders, send or resend ORM messages, receive OIE-routed ORU results back into the lab app, and preview the relevant raw HL7 payloads in one workspace.

Today the OIE page still behaves like separate protocol/inventory surfaces. It does not provide a patient-first workspace, nested order/result visibility, an OIE-to-lab result listener lifecycle, ORU persistence, or ORU-to-patient/order matching.

## What Changes

- Remove the OIE topbar mode selector and make the OIE page a patient-centered workflow.
- Show an ADT Patients list with MRN, name, Taipei created time, order count, and result count.
- Show a Selected Patient workspace containing that patient's Orders and Results.
- Keep one shared HL7 preview for ADT, ORM, and ORU payloads plus parsed summary information.
- Allow ORM preview and send/resend actions from the selected patient's Orders section.
- Persist ORM send ACK/status and display it on each order row.
- Add a lab-app MLLP result listener for OIE -> lab-app ORU messages, defaulting to port `6665`.
- Expose listener host, port, MLLP framing, start, stop, and status controls in the UI.
- Accept and persist `ORU^R01` and `ORU^W01` result messages.
- Match ORU results by `PID-3` plus `OBR-2` or `OBR-3` when possible, falling back to patient-only unmatched results when only the patient can be resolved.
- Keep unknown or unmatchable ORU messages visible in an Unmatched Results area.
- Return successful HL7 ACKs for accepted ORU messages and failure ACKs for parse or unsupported-message errors.

## Non-Goals

- No OIE channel provisioning or automatic OIE route configuration.
- No production result interpretation or ECG waveform rendering.
- No full order placer/filler reconciliation beyond the local matching rules.
- No automatic background service installation for the listener.
- No formal Cortex project brief or memory update in this change.

## Boundary Note

`repo/PROJECT_BOUNDARY.md` currently lists AP MLLP listener and ORU result generation as out of scope for Healthcare Lab. ZAC-20 intentionally revisits the receive-result side of that boundary for this project-local OIE console loop. The implementation should either update the project boundary in a later approved step or keep the listener scoped narrowly as a local OIE console test harness.

## Capabilities

### New Capabilities

- `healthcare-lab-patient-centered-oie-console`: Define patient-centered OIE console behavior for local ADT patient selection, ORM send/resend, ORU listener lifecycle, ORU persistence, matching, preview, and ACK handling.

### Modified Capabilities

- None.

## Impact

- Affected code: Healthcare Lab OIE page, local SQLite store, HL7 parsing/matching helpers, MLLP listener/server lifecycle, backend APIs, frontend state, backend tests, frontend syntax checks.
- Affected runtime: local lab app may listen for OIE result messages on `localhost:6665` by default.
- Affected workflow: developers can validate the local ADT -> ORM -> OIE -> ORU loop around a selected patient without switching OIE page modes.
