---
change: add-dcm4chee-pacs-ledger
date: 2026-07-09
---

## Context

ZAC-37 extends the dcm4chee MWL order work from an attempt-level audit trail into a canonical local PACS/MWL ledger. The purpose is to preserve Healthcare Lab order identity, AP-facing identifiers, and dcm4chee-confirmed identifiers so future DICOM studies/results can be reconciled back to the original local order.

## Implementation

- Added `local_dcm4chee_mwl_mappings` as the canonical mapping table for one local dcm4chee order and its current PACS/MWL identifiers.
- Linked `local_dcm4chee_mwl_attempts` to mappings with `mapping_id` and `operation_type`, preserving create/read-back attempt audit history.
- Added mapping upsert/update/read helpers, response/read-back identifier parsing, and reconciliation lookup by Study Instance UID, Accession Number, and Requested Procedure ID plus SPS ID.
- Updated dcm4chee order sync to create/update the canonical mapping, run best-effort read-back, avoid duplicate POSTs after confirmed success, and retry read-back before creating another MWL item for failed/ambiguous mappings.
- Added migration backfill from historical attempt rows into canonical mappings.
- Updated the order table to prefer canonical mapping values for DICOM MWL status and identifiers.
- Documented the ledger, read-back, retry/idempotency, and reconciliation boundary in `README.md`.

## Decisions

- Keep canonical mapping state separate from append-style attempt audit records.
- Treat successful create plus failed or empty read-back as pending confirmation, not a fully confirmed mapping.
- Preserve stable local identifiers across retries to avoid duplicate dcm4chee MWL orders.
- Keep full AP C-STORE result ingestion/display out of scope; this change supplies the mapping foundation.

## Validation Plan

- Validate the OpenSpec change with strict mode.
- Run JavaScript syntax validation for the updated frontend file.
- Run focused dcm4chee unit tests for mapping creation, read-back persistence, retry/idempotency, empty read-back handling, and lookup behavior.
- Run store-level migration/backfill regression coverage.
- Run full Python test discovery under `tests/`.

## Follow-ups

- Validate the dcm4chee read-back endpoint and query parameter shape against the local Docker runtime.
- Connect the ledger lookup to future AP C-STORE result ingestion/display work.

## Code Review

### Round 1 (2026-07-09)

- Review file: `openspec/changes/add-dcm4chee-pacs-ledger/review/2026-07-09_codex-review.md`
- Verdict: changes requested.
- Findings: read-back failures after successful create were not retryable; historical dcm4chee attempts were not backfilled into canonical mappings.
- Resolution: fixed by `4e7a5ba fix(ZAC-37): retry readback and backfill mappings`.

### Round 2 (2026-07-09)

- Review file: `openspec/changes/add-dcm4chee-pacs-ledger/review/2026-07-09_codex-review-r2.md`
- Verdict: changes requested.
- Finding: empty successful read-back responses were still marked confirmed.
- Resolution: fixed by `bde78ce fix(ZAC-37): keep empty readback retryable`.

### Round 3 (2026-07-09)

- Review file: `openspec/changes/add-dcm4chee-pacs-ledger/review/2026-07-09_codex-review-r3.md`
- Verdict: no blocking issues found.
- Residual risk: validate the dcm4chee read-back endpoint/query shape against the local Docker runtime.
