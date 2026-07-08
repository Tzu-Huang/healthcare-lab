---
change: define-dcm4chee-mwl-order-model
date: 2026-07-08
---

## Context

ZAC-34 defines the dcm4chee-arc MWL order-first contract before runtime implementation. The work clarifies that this is an order/worklist model, not a patient master-data feature, while patient demographics remain required MWL payload attributes.

## Implementation

- Added OpenSpec proposal, design, tasks, and spec delta for `healthcare-lab-dcm4chee-mwl-order-model`.
- Defined dcm4chee-arc as source of truth for PACS, MWL, DICOM study, and artifact state.
- Defined Healthcare Lab as owner of workflow UI intent, local order identity, generated identifiers, sync attempts, and mapping ledger metadata.
- Completed the task checklist after the contract, identifier strategy, mapping, reconciliation, and validation items were documented.

## Decisions

- Healthcare Lab generates sequential readable identifiers for local order, patient, accession, requested procedure, and scheduled procedure step values.
- Patient ID is always scoped by an explicit issuer namespace.
- Study Instance UID must be a valid DICOM UID using a configured UID root plus unique suffix; plain integer IDs are not valid complete Study Instance UID values.
- Result reconciliation prefers Study Instance UID, then Accession Number, then Requested Procedure ID plus Scheduled Procedure Step ID, with weak fallback matches treated as ambiguous unless exactly one active candidate exists.

## Validation Plan

- Run `openspec validate define-dcm4chee-mwl-order-model --strict`.
- Run `git diff --check main...HEAD`.
- Skip runtime/unit tests unless later implementation tickets add product code.

## Verification

### Round 1 (2026-07-08)

- `openspec validate define-dcm4chee-mwl-order-model --strict`: passed.
- `git diff --check`: passed during `/dev-test`.
- Runtime/unit tests: skipped because this change only adds OpenSpec contract artifacts and no product code.

## Code Review

### Round 1 (2026-07-08)

- Verdict: no findings.
- Must-fix items: none.
- Review file: `openspec/changes/define-dcm4chee-mwl-order-model/review/2026-07-08_codex-review.md`.
- Residual risk: future implementation tickets still need to choose/configure the concrete DICOM UID root and implement runtime behavior.

## Follow-ups

- Future dcm4chee implementation tickets should reference this contract when adding storage schema, dcm4chee calls, MWL order UI/API behavior, and result reconciliation.
