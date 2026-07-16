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

### Round 2 (2026-07-16 10:48:07 +08:00)

- Tested head: `20406dca8f10181d0a3502f974b9dd68ea90ee57` with a clean pre-check worktree.
- PASS — focused protocol verification: `python -m unittest tests.test_gdt_adapter tests.domain.test_gdt_protocol tests.domain.test_fhir tests.domain.test_fhir_ledger tests.domain.test_fhir_order tests.templates.test_fhir tests.repositories.test_fhir_ledger tests.repositories.test_fhir_workflow_characterization tests.repositories.test_gdt_workflow tests.repositories.test_gdt_workflow_characterization tests.repositories.test_lab_store tests.services.test_fhir_coordination tests.services.test_gdt_coordination tests.services.test_protocol_repository_wiring tests.runtime.test_gdt_bridge_watcher -q`; 82 tests passed in 10.391 seconds.
- PASS — architecture verification: `python -m unittest discover -s tests -p "test_architecture_contract.py" -q`; 38 tests passed in 1.957 seconds.
- PASS — compilation: `python -m compileall -q backend tests`; no errors.
- PASS — complete regression: `python -m unittest discover -s tests -q`; 337 tests passed in 56.130 seconds (56.639 seconds wall time).
- PASS — OpenSpec: `openspec validate extract-fhir-gdt-workflow-repositories --strict`; change is valid.
- Skips: none; no manual or environment-specific acceptance check was required.
- Post-check state: product code, tests, requirements/specs, generated product artifacts, and runtime configuration remained identical to the tested head; only this verification record is dirty.
- Unresolved failures: none.
- Next action: `/dev-review`.

### Round 3 (2026-07-16 11:08:33 +08:00)

- Tested head: `c2ae603ab5e297d0921f956e46d4fd8bdc81d1a6`; the pre-check worktree contained only the existing dirty devlog and review workflow records.
- PASS — focused protocol verification: `python -m unittest tests.test_gdt_adapter tests.domain.test_gdt_protocol tests.domain.test_fhir tests.domain.test_fhir_ledger tests.domain.test_fhir_order tests.templates.test_fhir tests.repositories.test_fhir_ledger tests.repositories.test_fhir_workflow_characterization tests.repositories.test_gdt_workflow tests.repositories.test_gdt_workflow_characterization tests.repositories.test_lab_store tests.services.test_fhir_coordination tests.services.test_gdt_coordination tests.services.test_protocol_repository_wiring tests.runtime.test_gdt_bridge_watcher -q`; 82 tests passed in 9.992 seconds.
- PASS — architecture verification: `python -m unittest discover -s tests -p "test_architecture_contract.py" -q`; 42 tests passed in 3.282 seconds.
- PASS — compilation: `python -m compileall -q backend tests`; no errors.
- PASS — complete regression: `python -m unittest discover -s tests -q`; 341 tests passed in 55.318 seconds.
- PASS — OpenSpec: `openspec validate extract-fhir-gdt-workflow-repositories --strict`; change is valid.
- Skips: none; no manual or environment-specific acceptance check was required.
- Post-check state: product code, tests, requirements/specs, generated product artifacts, and runtime configuration remained identical to the tested head; only the pre-existing devlog and review workflow records are dirty.
- Unresolved failures: none.
- Next action: `/dev-review` for closure review.

## Follow-ups

- Run `/dev-test ZAC-60` against committed product state.

## Code Review

### Round 1 (2026-07-16 10:52:36 +08:00)

- Source: `openspec/changes/extract-fhir-gdt-workflow-repositories/review/2026-07-16_feature-ZAC-60_extract-fhir-gdt-workflow-repositories_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `20406dca8f10181d0a3502f974b9dd68ea90ee57`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/extract-fhir-gdt-workflow-repositories/review/2026-07-16_feature-ZAC-60_extract-fhir-gdt-workflow-repositories_codex-review-r1.md"`

### Round 2 (2026-07-16 11:12:43 +08:00)

- Source: `openspec/changes/extract-fhir-gdt-workflow-repositories/review/2026-07-16_feature-ZAC-60_extract-fhir-gdt-workflow-repositories_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `c2ae603ab5e297d0921f956e46d4fd8bdc81d1a6`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: `none`
- Follow-ups: `none`
- Next action: commit only the review and devlog workflow records, then run `/dev-done`.
