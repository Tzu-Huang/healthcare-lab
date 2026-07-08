---
change: implement-dcm4chee-mwl-order-creation
date: 2026-07-08
---

## Context

ZAC-36 implements the first runtime dcm4chee MWL order creation path after ZAC-35 established the local dcm4chee connection profile. The selected route is the dcm4chee MWL REST endpoint:

`POST /dcm4chee-arc/aets/{AETitle}/rs/mwlitems`

HL7 ORM feeding, AP MWL query behavior, C-STORE reconciliation, and viewer-link consumption remain out of scope.

## Implementation

- Added DICOM mode order creation through `/api/orders` using the selected dcm4chee profile.
- Built `application/dicom+json` MWL payload generation with patient demographics, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Scheduled Station AE Title, Worklist Label, and Study Instance UID.
- Added configurable `DCM4CHEE_UID_ROOT` and UID validation/generation.
- Added `local_dcm4chee_mwl_attempts` persistence for request payloads, response body/status, generated identifiers, profile metadata, attempt status, timestamps, and error details.
- Preserved local Healthcare Lab orders when dcm4chee sync fails.
- Classified missing dcm4chee patient responses as `Patient missing` while retaining the raw response body.
- Recorded invalid dcm4chee profile attempts without sending outbound requests.
- Surfaced dcm4chee MWL sync status in the order UI and documented the route, defaults, and future-work boundaries.

## Decisions

- Use dcm4chee MWL REST creation for ZAC-36 instead of HL7 ORM feed.
- Treat dcm4chee patient existence as an explicit precondition, not a local order failure.
- Keep dcm4chee sync state separate from the Healthcare Lab local order status.
- Defer production auth/TLS hardening to future work; this implementation targets the local unauthenticated lab profile.

## Validation Plan

- Compile backend and test modules.
- Syntax-check frontend JavaScript.
- Run OpenSpec strict validation.
- Run the relevant Healthcare Lab unittest suite.
- Confirm the dcm4chee MWL REST endpoint against Docker runtime when the local service is available.

## Verification

### Round 1 (2026-07-08)

- `python -m py_compile app.py backend\lab_store.py tests\test_app.py`: PASS.
- `node --check frontend\static\app.js`: PASS.
- `openspec validate implement-dcm4chee-mwl-order-creation --strict`: PASS.
- `python -m unittest tests.test_app -v`: PASS, 84 tests.
- dcm4chee Docker runtime endpoint confirmation: SKIP because local `127.0.0.1:8082` was unavailable.

## Code Review

### Round 1 (2026-07-08)

- Review file: `openspec/changes/implement-dcm4chee-mwl-order-creation/review/2026-07-08_codex-review.md`.
- Verdict: changes requested.
- Finding: invalid dcm4chee profile states could bypass MWL attempt recording when payload construction failed before the invalid-profile branch.

### Round 2 (2026-07-08)

- Review file: `openspec/changes/implement-dcm4chee-mwl-order-creation/review/2026-07-08_codex-review-round2.md`.
- Verdict: no issues found.
- The previous P1 finding was fixed by recording invalid-profile attempts before payload construction.
- Residual risk: Docker runtime endpoint confirmation remains deferred until local dcm4chee is running.

## Follow-ups

- Run the live Docker dcm4chee MWL REST confirmation when the archive is available at `127.0.0.1:8082`.
- Decide in a future ticket whether Healthcare Lab should create/upsert dcm4chee patients before MWL creation.
- Keep AP MWL query, C-STORE reconciliation, and viewer-link workflows for later tickets.
