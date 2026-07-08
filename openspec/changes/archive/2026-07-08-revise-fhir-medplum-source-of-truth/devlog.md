---
change: revise-fhir-medplum-source-of-truth
date: 2026-07-08
---

## Context

ZAC-33 clarifies the FHIR architecture boundary after ZAC-25 established the local FHIR sync foundation. The goal is to prevent later Patient, Order, Task, Result, Medplum inventory, and E2E tickets from treating Healthcare Lab as a full local FHIR/EMR shadow database.

## Implementation

- Added an OpenSpec proposal for Medplum-backed FHIR source ownership.
- Added a design note defining Medplum as the canonical FHIR source of truth and Healthcare Lab local storage as a workflow ledger for intent, retry, audit, OperationOutcome, and Medplum references.
- Added spec deltas for live Medplum reads, unsynced local intent handling, successful Medplum identity reconciliation, and avoidance of full local FHIR shadow ownership.
- Added follow-up ticket alignment for ZAC-26 through ZAC-32.
- Added a Codex review artifact.

## Decisions

- Medplum owns canonical synced FHIR resources and server-side query behavior.
- Healthcare Lab owns local workflow intent, sync status, retry/idempotency metadata, request/response audit, OperationOutcome details, AP/demo audit trails, and UI projection metadata.
- FHIR inventory, patient-centered panels, AP worklist, and result history should default to live Medplum API reads joined with local ledger metadata when available.
- Pending or failed local workflow intents remain visible, but must not be presented as canonical Medplum clinical data.

## Validation Plan

- Run `openspec validate --changes revise-fhir-medplum-source-of-truth`.
- Confirm no product runtime tests are required because this change only updates OpenSpec artifacts.

## Verification

### Round 1 (2026-07-08)

- `openspec validate --changes revise-fhir-medplum-source-of-truth`: passed.
- Product runtime tests: skipped; this change only updates OpenSpec proposal, design, spec, tasks, mapping, devlog, and review artifacts.

## Code Review

### Round 1 (2026-07-08)

- Review source: `openspec/changes/revise-fhir-medplum-source-of-truth/review/2026-07-08_codex-review.md`.
- Verdict: no findings.
- Residual risk: later implementation tickets still need concrete tests for live Medplum query behavior, local ledger joins, retry/idempotency, and clear UI labeling for pending or failed local intents.

## Follow-ups

- ZAC-26 through ZAC-32 should reference this boundary while implementing Patient creation, Medplum inventory, FHIR order creation, AP worklist, result return, patient-centered FHIR panels, and E2E demo coverage.
