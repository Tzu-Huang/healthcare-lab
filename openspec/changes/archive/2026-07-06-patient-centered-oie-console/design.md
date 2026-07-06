## Overview

The OIE page becomes a patient-centered integration console. The primary object is a local ADT patient; orders and results are nested under the selected patient, and the preview pane shows the currently selected ADT, ORM, or ORU message.

## Data Model

Add persisted ORU result records with enough normalized fields to support matching and display:

- local result id
- raw HL7 payload
- message type, message control id, received time
- patient identity from `PID-3`
- placer order number from `OBR-2`
- filler order number from `OBR-3`
- matched local patient id when known
- matched local order id when known
- match status: `order-matched`, `patient-only`, or `unmatched`
- ACK status and parse/error detail

Existing local patients and orders remain the source of truth for patient/order identity.

## Matching Rule

ORU matching priority:

1. `PID-3` plus `OBR-2` matches a local ORM placer order.
2. `PID-3` plus `OBR-3` matches a local ORM filler/order identifier when available.
3. `PID-3` matches a local patient, but no order matches: store under that patient as patient-only unmatched order result.
4. Missing or unknown `PID-3`: store in Unmatched Results.

`MSH-10` is retained for message control and duplicate detection, but it is not the primary order matching key.

## Listener Lifecycle

The backend owns an in-process local MLLP listener for OIE -> lab-app results. The first version defaults to `localhost:6665`, exposes start/stop/status APIs, and returns HL7 ACKs after parsing and persistence decisions.

Unsupported message types and parse failures should return failure ACKs while preserving enough diagnostic information for the UI.

## UI Shape

The OIE page removes the topbar mode selector and uses:

- listener/status strip
- ADT Patients list
- Selected Patient workspace with Orders and Results sections
- Unmatched Results area
- shared HL7 preview

Timestamps shown for patient creation, order send, and result receipt must be unambiguous Taipei-time timestamps.

## Open Questions

- Should listener settings persist to SQLite or remain runtime-only in the first version?
- Should the listener auto-start when configured, or require explicit Start each app run?
- Should result count include patient-only unmatched ORU results, or only order-matched results?
- Should the project boundary be updated before implementation, or documented in the implementation devlog first?
