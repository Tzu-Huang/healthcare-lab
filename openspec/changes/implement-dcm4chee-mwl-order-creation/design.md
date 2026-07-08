## Context

ZAC-34 defines the dcm4chee MWL/order contract and identifier strategy. ZAC-35 adds a validated dcm4chee connection profile with local Docker defaults, AE titles, MWL settings, DICOMweb endpoints, and diagnostics.

ZAC-36 is the first runtime dcm4chee order integration. Healthcare Lab must create a local order intent and then create the corresponding dcm4chee MWL/order record without relying on manual dcm4chee UI entry.

## Goals / Non-Goals

**Goals:**

- Create a dcm4chee MWL/order record from a Healthcare Lab ECG order.
- Use the dcm4chee MWL REST API as the primary implementation path.
- Build a DICOM JSON payload with required patient demographics and Scheduled Procedure Step/order fields.
- Generate namespace-aware local identifiers and a valid DICOM Study Instance UID.
- Persist mapping/audit metadata for each dcm4chee creation attempt.
- Preserve local Healthcare Lab orders when dcm4chee creation fails.
- Return clear failure information for patient precondition, profile validation, HTTP, and payload errors.

**Non-Goals:**

- Implement HL7 ORM feeding into dcm4chee.
- Implement AP Modality Worklist query behavior.
- Implement C-STORE result reconciliation.
- Implement viewer-link consumption or DICOM viewer workflows.
- Implement production auth/TLS hardening beyond consuming the existing profile placeholders.
- Delete or roll back local orders when dcm4chee sync fails.

## Decisions

1. Use dcm4chee MWL REST creation for ZAC-36.

   The dcm4chee source exposes `POST /aets/{AETitle}/rs/mwlitems` for MWL item create/update with `application/dicom+json`. This route is easier to audit and debug from Healthcare Lab than introducing an HL7 ORM feed in the first runtime integration ticket.

2. Treat Patient existence as an explicit precondition.

   dcm4chee MWL REST creation checks patient identifiers and returns a not-found failure when the patient does not exist. ZAC-36 should not hide this as a generic sync failure. The implementation should either verify/prepare the patient before MWL creation or persist a clear failed sync state such as `patient_missing` with the dcm4chee response retained.

3. Healthcare Lab owns local intent and mapping/audit state.

   Local order creation must complete independently from dcm4chee sync. The dcm4chee attempt should record profile name, server identity, generated identifiers, outbound DICOM JSON, response status/body, attempt status, timestamps, and error details.

4. Identifier generation must follow the ZAC-34 contract.

   Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, and local order identifiers remain readable and sequential. Study Instance UID must use a configured UID root plus unique suffix, not a plain integer or local order id.

5. Profile diagnostics gate outbound requests.

   Before attempting dcm4chee MWL creation, the selected profile should be validated. Invalid or incomplete profile configuration should create a failed/pending dcm4chee attempt with a clear diagnostic result and should not delete the local order.

## DICOM JSON Payload

The MWL REST payload should include at minimum:

- `00100010` Patient's Name
- `00100020` Patient ID
- `00100021` Issuer of Patient ID
- `00100030` Patient's Birth Date
- `00100040` Patient's Sex
- `00080050` Accession Number
- `0020000D` Study Instance UID
- `00401001` Requested Procedure ID
- `00741202` Worklist Label
- `00400100` Scheduled Procedure Step Sequence containing:
  - `00400001` Scheduled Station AE Title
  - `00400009` Scheduled Procedure Step ID
  - scheduled date/time or status values when required by the selected dcm4chee behavior

## Risks / Trade-offs

- [Risk] dcm4chee local runtime may require a patient to exist before MWL REST creation. -> Mitigation: make patient precondition handling explicit and record the exact dcm4chee response.
- [Risk] REST payload details may vary by dcm4chee version/config. -> Mitigation: keep payload builder covered by tests and store outbound request/response for manual debugging.
- [Risk] Introducing local mapping tables can duplicate identifiers already present in generic order records. -> Mitigation: keep dcm4chee-specific identifiers and sync attempts in a dedicated dcm4chee mapping/audit shape.
- [Risk] A valid local order can have failed dcm4chee sync. -> Mitigation: show or return dcm4chee sync status separately from local order creation status.

## Open Questions

- Should ZAC-36 include a minimal dcm4chee Patient create/upsert path, or should missing patients remain a failed precondition until a dedicated patient sync ticket?
- What local lab-only `DCM4CHEE_UID_ROOT` should be used as the default Study Instance UID root?
- Should dcm4chee MWL sync run synchronously during order creation, or should it be persisted as an attempt and retried asynchronously in a later ticket?
