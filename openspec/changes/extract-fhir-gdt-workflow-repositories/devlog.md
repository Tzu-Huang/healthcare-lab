---
change: extract-fhir-gdt-workflow-repositories
date: 2026-07-16
---

## Context

Extract the FHIR ledger and GDT workflow persistence from `DemoStore` without changing public API, serialized payload, transaction, matching, or runtime behavior.

## Implementation

- Added pure FHIR ledger/order and GDT protocol collaborators with deterministic tests.
- Added cohesive `FhirLedgerRepository` and `GdtWorkflowRepository` owners using the shared connection factory and write lock.
- Added narrow FHIR/GDT coordinators and explicit service ports, assembled in `app_factory.py`.
- Reduced retained `DemoStore` FHIR/GDT methods to enumerated compatibility delegates.
- Removed only extracted legacy architecture-baseline entries.

## Decisions

- Kept `local_order_records` ownership in `OrderRepository` and coordinated FHIR ledger creation above it.
- Preserved local-first FHIR order semantics: a later ledger failure does not remove the committed local order.
- Kept raw GDT parsing/rendering outside persistence and retained multi-table GDT transactions in one repository owner.
- Preserved the existing `DemoStore.__init__` composition fingerprint and added no allowlist, dependency, schema, or migration changes.

## Validation Plan

- Run focused FHIR/GDT domain, template, repository, service, runtime, and compatibility tests on disposable resources.
- Run architecture checks, compilation, the complete unittest suite, and strict OpenSpec validation.
- Audit the final diff and commit history for scope, baseline direction, and forbidden external or schema changes.

## Verification

### Round 1 (2026-07-16 10:44:28 +08:00)

- Checks: 82 focused FHIR/GDT/Lab Store/runtime tests; 38 architecture tests; `python -m compileall -q backend tests`.
- Result: passed; compatibility behavior, transaction rollback, matching precedence, event/attachment projection, service ports, and composition checks are green.
- Checks: `python -m unittest discover -s tests -v`.
- Result: 337 tests passed in 66.111 seconds with no skips or weakened assertions.
- Checks: `openspec validate extract-fhir-gdt-workflow-repositories --strict`.
- Result: change is valid.
- Direct remediation: updated four failure-injection characterizations to target the new repository/coordinator seams and removed a service-to-template dependency by injecting the FHIR resource builder.
- Unresolved failures: none.
- Next action: `/dev-test ZAC-60`.

## Follow-ups

- Run `/dev-test ZAC-60` against committed product state.
