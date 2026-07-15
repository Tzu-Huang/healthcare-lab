---
change: split-dcm4chee-persistence-repositories
date: 2026-07-15
---

# Development Log

## Context

Split the remaining dcm4chee Patient Sync, MWL, and result persistence out of
`DemoStore` while preserving public behavior, SQLite data formats, retry and
reconciliation policy, refresh visibility, and deterministic historical
backfill.

## Implementation

- Added dedicated patient-sync, MWL, and result repositories using the shared
  connection factory and application write lock.
- Moved DICOM payload, parsing, identifier, status, and reconciliation rules to
  domain/template collaborators.
- Added explicit cross-ledger workflow coordination and narrow service-facing
  capability views.
- Retained mechanical `DemoStore` compatibility delegates.
- Added disposable-database and transport-double coverage for persistence,
  backfill, reconciliation, refresh publication, and architecture boundaries.

## Decisions

- Keep startup maintenance sequencing and transaction ownership in
  `SQLiteDatabase`; inject pure historical identifier projection into MWL
  backfill.
- Prepare MWL attempt payloads in a named coordinator before persistence.
- Bind broad cross-ledger work behind `ConfiguredWorkflowOperations` while
  exposing only narrow named capabilities to patient/order services.
- Preserve call-time HL7 sender lookup and the legacy order precondition
  callback shape for integration compatibility.

## Validation Plan

- Run focused domain, template, repository, service, API/integration, and
  architecture tests using disposable resources and transport doubles.
- Run full `unittest` discovery, Python compilation, strict OpenSpec
  validation, whitespace checks, schema immutability, and forbidden-scope
  audits.
- Require closure review approval after all review fixes and verification-fix
  commits.

## Verification

### Round 1 (2026-07-15)

- HEAD: `5f3db4d480c1780fcac025763429993f3f7cbb8c`
- Result: pass.
- Checks: 290 full regression tests; 38 architecture tests; compileall; strict
  OpenSpec; diff hygiene; schema/scope audit.
- Next action: `/dev-review`.

### Round 2 (2026-07-15)

- HEAD: `e45c195fadc885b003e8ae07dc8494bc24956fd2`
- Result: fail.
- Checks: 293 tests ran with two errors and two failures in configured
  patient/order DICOM binding paths.
- Resolution: fixed callback double-binding and restored call-time HL7 sender
  injection in `d3ad20a`.
- Next action: `/dev-test`.

### Round 3 (2026-07-15)

- HEAD: `d3ad20a36512748720e0feb635c9fc1afd926072`
- Result: pass.
- Checks: 293 full regression tests; 38 architecture tests; compileall; strict
  OpenSpec; committed/worktree diff checks; schema immutability and
  forbidden-scope audits.
- Unresolved failures: none.
- Next action: `/dev-review` closure.

## Code Review

### Round 1 (2026-07-15)

- Source: `openspec/changes/split-dcm4chee-persistence-repositories/review/2026-07-15_feature-ZAC-59_split-dcm4chee-persistence-repositories_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `5f3db4d480c1780fcac025763429993f3f7cbb8c`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`, `REV-003`, `REV-004`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/split-dcm4chee-persistence-repositories/review/2026-07-15_feature-ZAC-59_split-dcm4chee-persistence-repositories_codex-review-r1.md"`

### Round 2 (2026-07-15)

- Source: `openspec/changes/split-dcm4chee-persistence-repositories/review/2026-07-15_feature-ZAC-59_split-dcm4chee-persistence-repositories_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `d3ad20a36512748720e0feb635c9fc1afd926072`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved; REV-004 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: `/dev-done`

## Follow-ups

None.
