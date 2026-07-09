---
change: verify-dcm4chee-mwl-queryability
date: 2026-07-09
---

## Context

ZAC-39 verifies that Healthcare Lab-created DICOM MWL orders are queryable from dcm4chee after creation. The local runtime investigation found two relevant boundaries: the MWL REST surface is served through the `WORKLIST` AE/web app, while the archive QIDO/WADO/STOW AE remains `DCM4CHEE`; dcm4chee also requires the referenced patient to exist before MWL creation/verification can succeed.

## Implementation

- Added mapping-level MWL verification metadata and `verify-mwl` attempt audit records in the local dcm4chee ledger.
- Added `POST /api/orders/<id>/dcm4chee-mwl-verify` to query dcm4chee MWL REST using stored order identifiers.
- Added DICOM JSON parsing and matching against Patient ID, Issuer, Accession Number, Requested Procedure ID, Scheduled Procedure Step ID, Scheduled Station AE Title, Study Instance UID, and Worklist Label.
- Added diagnostics for empty results, mismatches, ambiguous matches, missing patients, invalid profiles, unsupported endpoints, and dcm4chee query failures.
- Surfaced verification status/proof metadata in order payloads and added a DICOM order list `Verify` action.
- Updated README and active dcm4chee profile spec defaults to document `WORKLIST` as the local MWL REST target.

## Decisions

- Kept MWL verification separate from creation/read-back sync status so operators can distinguish "order posted" from "order queryable".
- Stored the verification query, selected match metadata, and error payload on the canonical mapping for quick inspection while keeping each verification as a distinct attempt.
- Used dcm4chee MWL REST as the first verification mechanism; AP changes and AP-side MWL query tooling remain out of scope.
- Treated live Docker `WORKLIST` queryability as an environment-specific check because automated unit tests mock dcm4chee responses.

## Validation Plan

- Compile backend modules: `python -m py_compile app.py backend\lab_store.py`.
- Check frontend syntax: `node --check frontend\static\app.js`.
- Run relevant backend tests: `python -m unittest tests.test_app tests.test_lab_store`.
- Validate OpenSpec change: `openspec validate verify-dcm4chee-mwl-queryability --strict`.
- Review diff hygiene: `git diff --check main...HEAD`.

## Follow-ups

- Run a live Docker lab smoke check against `WORKLIST` once dcm4chee is up and seeded with the expected patient/order preconditions.
- Use `$dev-done` to archive the OpenSpec change after review artifacts and devlog are committed.

## Code Review

### Round 1 (2026-07-09 09:52)

- Source: `openspec/changes/verify-dcm4chee-mwl-queryability/review/2026-07-09_codex-review.md`
- Verdict: no blocking issues found.
- Reviewed: MWL verification request path, error classification, matching logic, persistence schema migration, API response contract, and frontend Verify action.
- Residual risk: live dcm4chee `WORKLIST` queryability was not exercised during in-session review because it depends on the local Docker lab runtime.
