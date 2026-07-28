## Context

ZAC-92 through ZAC-95 delivered the parser, framework-independent renderer,
WADO-RS retrieval APIs, and dedicated viewer UI that satisfy the individual
parts of parent ZAC-91. The repository also contains
`dicom-formats/12lead_ecg_waveform.dcm` and
`dicom-formats/general_ecg_waveform.dcm`, but their safe distribution status
must be established before they can become packaged test inputs. ZAC-96 is the
cross-capability closure gate and must distinguish reproducible automated
coverage from environment-dependent live evidence.

## Goals / Non-Goals

**Goals:**

- Prove both supported SOP Classes across the persisted-result-to-viewer path.
- Make fixture provenance, de-identification, expected waveform shape, and
  packaging policy explicit and reviewable.
- Exercise success, failure, compatibility, authorization, configuration, and
  disclosure-safety paths with deterministic tests where possible.
- Provide a short manual checklist and operating guidance matching the shipped
  UI, API, deployment path, and demonstration-only classification.

**Non-Goals:**

- Add zoom, calipers, annotations, print layout, export, or diagnostic use.
- Broaden the supported SOP Class, lead-layout, unit, or sample representation
  contracts.
- Repair unrelated defects silently inside this verification change.
- Capture real PHI, credentials, internal paths, or unbounded upstream payloads
  as test or verification evidence.

## Decisions

### Gate fixture use on an explicit safety manifest

Each source fixture will have a reviewable manifest containing provenance,
cryptographic identity, de-identification outcome, expected SOP Class, and
normalized waveform invariants. A source instance that cannot be proven
de-identified will not be packaged; a sanitized derivative may replace it only
when waveform and channel metadata invariants are preserved and documented.
This is preferred to assuming that filenames or current tag values establish
safety.

### Split deterministic end-to-end tests from live dcm4chee evidence

Automated tests will use controlled persisted results and WADO-RS responses to
exercise bare and multipart retrieval, parsing, rendering, APIs, and viewer
behavior for both formats. A bounded manual checklist will witness the
user-visible flow against a configured dcm4chee profile. This keeps CI
repeatable while retaining proof of the real operator journey.

### Assert the assembled contract at stable boundaries

The release matrix will assert persisted result identity and capability,
retrieval media handling, normalized waveform invariants, SVG labels and safety
notice, viewer summary and accessibility state, plus existing result action
compatibility. Tests will avoid implementation-private call sequences so the
four underlying capabilities can evolve without weakening the release gate.

### Treat failures as safe product states

Negative cases will assert stable status and error categories at the API and
viewer boundaries and scan responses for fixture identifiers, credentials,
internal paths, raw metadata, and upstream payload fragments. Raw DICOM dumps
or upstream bodies are not acceptable evidence.

### Route new product behavior to follow-up issues

Any missing behavior required by the existing four capability specs blocks
closure and is fixed through the normal workflow. Optional interaction or
format expansion becomes a separate Linear issue. This keeps ZAC-96 focused on
acceptance rather than unbounded feature growth.

## Risks / Trade-offs

- **Fixture de-identification cannot be proven** → keep the source local and
  generate a documented sanitized derivative or rely on constructed datasets
  until review is complete.
- **Mocked WADO-RS coverage diverges from dcm4chee framing** → retain a bounded
  live checklist for both bare and multipart-compatible responses and record
  exact environment-dependent skips.
- **Large SVG or waveform assertions make tests brittle** → assert stable
  waveform invariants, required labels, media types, and safety text rather
  than byte-for-byte graph output.
- **Regression checks uncover a product defect** → record a minimal,
  disclosure-safe reproduction and route it to a linked issue before rerunning
  the affected acceptance path.
- **Manual evidence leaks sensitive data** → use synthetic records, bounded
  output, and explicit inspection before committing evidence.

## Migration Plan

This change introduces no schema or runtime migration. Land the safe fixture
contract, automated release gate, documentation, and bounded evidence
together. Rollback is a normal Git revert. A blocking defect keeps ZAC-96 open
until the linked fix is merged and the affected matrix is rerun.

## Open Questions

- Can both current source fixtures be positively certified as de-identified,
  or must sanitized derivatives be generated?
- Which supported deployment environment will provide the recorded live
  dcm4chee witness?
