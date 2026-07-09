## Context

ZAC-34 defined the dcm4chee MWL/order contract. ZAC-36 implemented MWL creation attempts. ZAC-37 added the canonical PACS/MWL mapping ledger. ZAC-38 added retry and attempt inspection.

ZAC-39 adds a distinct verification concept: Healthcare Lab should prove that a local order, once created or attempted in dcm4chee, is queryable from the dcm4chee MWL surface. Creation/read-back answers "did the sync workflow run"; verification answers "can the AP-facing MWL query find this order."

Local runtime exploration showed:

- `DCM4CHEE` exposes QIDO/WADO/STOW services, but the dcm4chee MWL REST application is exposed through the `WORKLIST` AE/web app.
- The local dcm4chee archive requires the referenced Patient ID to exist before MWL creation succeeds.
- A valid DICOMweb archive endpoint can return `204 No Content` for empty study queries, while MWL query failures can be more specific, such as missing web app or missing patient.

## Goals / Non-Goals

**Goals:**

- Add an explicit backend verification operation for dcm4chee MWL queryability.
- Reuse canonical ledger identifiers as the source of verification query criteria.
- Store verification attempts with operation type, query target, request criteria, response status/body, found metadata, mismatch details, timestamps, and diagnostic status.
- Update the canonical PACS/MWL ledger with latest verification status and proof metadata.
- Expose actionable diagnostics that distinguish infrastructure, configuration, precondition, empty result, mismatch, and ambiguity failures.
- Keep local orders available regardless of verification outcome.

**Non-Goals:**

- Implement AP-side code changes.
- Implement full AP C-STORE result ingestion, study polling, or viewer workflow.
- Replace dcm4chee as PACS/MWL source of truth.
- Hide missing-patient failures by silently creating archive patients unless that behavior is explicitly designed in another change.

## Decisions

1. Verification is separate from creation/read-back.

   Creation and read-back attempts remain sync/audit history. Verification should use a distinct operation type such as `verify-mwl` so operators can tell whether an order was merely posted, read back, or proven queryable.

2. Verification starts from the canonical ledger.

   The verification request should derive identifiers from the canonical mapping: Patient ID, Issuer of Patient ID, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Scheduled Station AE Title, Worklist Label, Study Instance UID when available, profile name, and MWL AE title.

3. The automated default uses dcm4chee MWL REST.

   For the local Docker profile, the backend should query `/dcm4chee-arc/aets/WORKLIST/rs/mwlitems` using dcm4chee-supported query parameters. If DIMSE MWL tooling is added later, it should be represented as another verification method with comparable attempt/proof fields.

4. Match proof must validate returned identifiers.

   A non-empty MWL response is not enough. Healthcare Lab should parse the returned DICOM JSON and confirm that at least one returned item matches the expected identifiers strongly enough to prove it is the local order. Strong matches should prefer Accession Number, Requested Procedure ID plus SPS ID, Patient ID plus issuer, and Scheduled Station AE Title. Worklist Label is useful proof context but should not be the sole identifier.

5. Diagnostics should be operator-facing.

   Verification failures should map raw dcm4chee errors into clear local status/error types: `dcm4chee_unreachable`, `mwl_profile_invalid`, `patient_missing`, `mwl_empty`, `mwl_mismatch`, `mwl_ambiguous`, and `mwl_endpoint_unsupported` are expected starting categories.

## Data Model Direction

Extend the local dcm4chee MWL persistence with latest verification metadata on the canonical mapping and append-only verification attempt rows.

Latest mapping metadata should include:

- verification status such as `not_verified`, `verified`, `verification_failed`, or `verification_ambiguous`
- verification method such as `dcm4chee-mwl-rest`
- verification timestamp
- verification query target and criteria summary
- matched returned identifiers and proof metadata
- latest verification error type/text/payload

Attempt audit should include:

- operation type `verify-mwl`
- profile/server/MWL AE namespace
- request target and query criteria
- HTTP status or tooling exit status when available
- raw response body or parsed response summary
- match count and selected match metadata
- mismatch/ambiguity diagnostics
- timestamps and status

## API / UI Direction

Backend options:

- Add an explicit endpoint such as `POST /api/orders/<id>/dcm4chee-mwl-verify`.
- Include verification status in existing order payloads under `item.dcm4chee.mwl.verification`.
- Include verification attempts in existing attempt history or a filtered view, as long as operation type is clear.

Frontend direction:

- At minimum, selected DICOM order inspection should display latest verification status and diagnostics when available.
- If practical, add a verify action next to retry for DICOM MWL orders that have enough identifiers to query.

## Risks / Trade-offs

- [Risk] dcm4chee MWL REST query parameters may not support every desired identifier consistently. -> Mitigation: start with supported local REST behavior and keep raw criteria/response in attempts for troubleshooting.
- [Risk] Patient precondition failures prevent order creation, so verification will correctly fail or be skipped. -> Mitigation: expose `patient_missing` as a non-retryable precondition until patient creation/sync is designed.
- [Risk] Empty query responses may be caused by wrong AE/web app rather than missing order. -> Mitigation: validate profile target and retain request URL/status diagnostics.
- [Risk] Multiple returned MWL items can match weak criteria. -> Mitigation: require strong identifier match and report ambiguity instead of claiming success.

## Open Questions

- Should this change add a manual/operator-run DIMSE `findscu` command path, or defer that until REST verification is proven?
- Should verification run automatically after successful create/read-back, or remain an explicit operator action first?
- Should missing dcm4chee patient creation/sync be pulled into this change, or handled as a separate precondition ticket?
