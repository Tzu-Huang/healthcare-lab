---
change: extract-patient-identifier-order-repositories
date: 2026-07-15
---

# Development Log

## Context

Extract Patient records, transaction-safe MRN allocation, generic Order records,
and send-result persistence from `DemoStore` while preserving API, protocol,
identifier, payload, transaction, and existing-database behavior for ZAC-58.

## Implementation

- Added dedicated Patient, Order, identifier, and projection-enrichment
  repository collaborators using the shared SQLite connection and write lock.
- Moved Patient/Order validation and projections into domain modules and payload
  generation into framework-independent template modules.
- Replaced Patient/Order workflow access to the general facade with explicit
  ledger and typed protocol-coordination ports and adapters.
- Retained enumerated `DemoStore` compatibility delegates and removed the
  corresponding reviewed architecture-baseline entries.

## Decisions

- Identifier allocation remains connection-bound to the Patient creation
  transaction; no uniqueness constraint or schema migration was introduced.
- Generic Order identifiers remain derived from the inserted row ID and are
  finalized atomically with payload generation.
- FHIR and dcm4chee ledger ownership remains outside the extracted core
  repositories and is exposed only through explicit coordination contracts.

## Validation Plan

- Run focused domain, template, repository, service, architecture, API, and
  integration tests with disposable databases and external-service doubles.
- Run the full regression suite, Python compilation, frontend syntax, strict
  OpenSpec validation, and scope/data-safety audit.
- Require closure review approval of the final committed product head before
  archival.

## Follow-ups

None.

## Code Review

### Round 3 (2026-07-15 16:13:08 +08:00)

- Source: `openspec/changes/extract-patient-identifier-order-repositories/review/2026-07-15_feature-ZAC-58_extract-patient-identifier-order-repositories_codex-review-r3.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `15c6f31ef70bf73f2711b5614f41ee2101e98cfa`
- Transitions: `REV-003 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: `/dev-done`
