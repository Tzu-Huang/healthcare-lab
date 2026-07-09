## Context

The current dcm4chee local runtime is `dcm4che/dcm4chee-arc-psql:5.35.0`, backed by Postgres and LDAP. The container listens on HTTP `8080`, DICOM `11112`, HL7 `2575`, and TLS HL7 `12575`, but the current compose file exposes only HTTP and DICOM.

dcm4chee MWL REST creation is already implemented through:

```text
POST /dcm4chee-arc/aets/WORKLIST/rs/mwlitems
```

The dcm4chee `MwlRS` implementation reads Patient identifiers from the MWL payload and calls `patientService.findPatient(...)`. If the Patient is not found, it returns `Patient[id=...] does not exist.` and the Healthcare Lab sync state becomes `Patient missing`.

dcm4chee `PatientUpdateService` supports HL7 ADT messages including `ADT^A04` and `ADT^A08`, validates trusted Patient identifiers, and calls `patientService.updatePatient(...)`. That is the cleaner Patient master sync path for the local lab than STOW-RS or direct database access.

## Goals / Non-Goals

**Goals:**

- Sync local DICOM Patient records to dcm4chee at Patient creation time.
- Reuse the same Patient ID and issuer namespace that MWL creation uses.
- Record Patient sync attempts separately from MWL attempts.
- Make Patient sync status visible and actionable in the UI and API.
- Ensure DICOM MWL creation checks the Patient precondition before posting MWL items.
- Keep local Patients and orders available when dcm4chee is unreachable or rejects Patient sync.

**Non-Goals:**

- Replace MWL REST with HL7 ORM in this ticket.
- Use STOW-RS as a Patient master creation shortcut.
- Implement production auth/TLS beyond profile fields and diagnostics.
- Directly write dcm4chee Postgres or LDAP state.
- Delete local Patients or orders when dcm4chee sync fails.

## Decisions

1. Patient sync uses HL7 ADT.

   Healthcare Lab should create a dcm4chee Patient by sending an HL7 `ADT^A04` message to the dcm4chee HL7 receiver. Future Patient edits should use an update event such as `ADT^A08` when update workflows exist.

2. Patient sync is triggered when a local DICOM Patient is created.

   The user expectation is that creating a DICOM Patient prepares dcm4chee for later MWL order creation. Healthcare Lab should still keep the local Patient if outbound dcm4chee sync fails and show retryable status.

3. MWL creation performs a Patient precondition check.

   Before `POST /mwlitems`, Healthcare Lab should inspect the local Patient sync state. If the Patient is not synced, it should attempt a Patient sync preflight when possible. If that fails, it should preserve the local order and mark MWL sync as blocked by Patient sync.

4. Patient sync gets its own ledger.

   Patient sync is a Patient lifecycle concern, not only an order attempt. A dedicated local ledger should store one current dcm4chee Patient sync state per local Patient/profile/server namespace plus append-only attempt rows. The order/MWL status may include a compact precondition summary.

5. Issuer namespace must match MWL.

   Patient ADT should send the same Patient ID and assigning authority/issuer that MWL uses as `IssuerOfPatientID`. For the current local profile, this remains `local-dcm4chee` unless the profile is changed.

6. STOW-RS remains for real DICOM objects.

   Later DICOM ECG, Encapsulated PDF, Secondary Capture, or AP C-STORE workflows can use STOW-RS. This ticket should not upload fake objects just to create Patient master data.

## Data Model Direction

Add local persistence for dcm4chee Patient sync:

- local Patient record id
- profile name and server identity
- Patient ID and issuer/assigning authority
- HL7 endpoint host/port and receiving application/facility
- current sync status such as `Pending sync`, `Synced`, `Sync failed`
- retry count, last sync time, last attempt id
- last ACK status/body or error details
- created/updated timestamps

Add Patient sync attempt history:

- Patient sync mapping id or local Patient id
- operation type such as `adt-create`, `adt-update`, `preflight`
- request target
- raw HL7 payload
- ACK/control id or raw response when available
- status, error type/text, attempted/completed timestamps

## Integration Direction

The backend should implement a small MLLP client for dcm4chee HL7 sync or reuse an existing local helper if one is already present. The client must frame HL7 messages with the standard MLLP start/end bytes and parse the returned ACK enough to distinguish accepted, rejected, transport failure, and timeout.

For initial Patient creation:

1. Create the local Patient record.
2. If `mode == dicom`, create or update the dcm4chee Patient sync mapping.
3. Send `ADT^A04` to dcm4chee.
4. Store ACK/error result.
5. Return the local Patient with sync status, regardless of outbound success.

For DICOM MWL order creation:

1. Create the local DICOM MWL order intent.
2. Check the selected Patient's dcm4chee Patient sync status.
3. If not synced, attempt Patient sync preflight.
4. If Patient sync is still not synced, record MWL status as Patient precondition failure and do not POST MWL.
5. If Patient is synced, proceed with existing MWL REST create/read-back flow.

## Risks / Trade-offs

- [Risk] dcm4chee may require trusted assigning authority configuration for `local-dcm4chee`. -> Mitigation: expose issuer/assigning authority in profile settings and make ACK errors visible.
- [Risk] HL7 receiver port is available inside the dcm4chee container but not exposed by compose. -> Mitigation: add `2575` to compose and document container vs host defaults.
- [Risk] MLLP transport handling adds protocol complexity. -> Mitigation: keep the client narrow, tested, and focused on sending one ADT message and parsing ACK status.
- [Risk] MWL creation can still fail after Patient sync due to profile or endpoint issues. -> Mitigation: keep existing MWL diagnostics and separate Patient sync errors from MWL errors.

## Open Questions

- Should future Patient edit workflows send `ADT^A08` immediately, or remain out of scope until Patient update UI exists?
- Should Patient sync retry be exposed as a separate Patient-page action in the first implementation, or only retried as MWL preflight?
- Should the connection profile eventually support TLS HL7 `12575`, or keep plaintext `2575` for the local lab until auth/TLS work is scheduled?
