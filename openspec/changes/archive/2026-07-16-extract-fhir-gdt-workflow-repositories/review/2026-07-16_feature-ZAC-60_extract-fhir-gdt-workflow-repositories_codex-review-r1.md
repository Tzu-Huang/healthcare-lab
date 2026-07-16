---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-60_extract-fhir-gdt-workflow-repositories
base: main
reviewed_head: 20406dca8f10181d0a3502f974b9dd68ea90ee57
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P2][REV-001] Compatibility composition bypasses the declared service dependency matrix

- Evidence: `backend/services/protocol_compatibility.py:31`, `:60`, and `:86` call `import_module()` with concrete repository and template module names. The declared matrix in `tests/test_architecture_contract.py:30-38` does not allow `services` to depend on `repositories` or `templates`, but its AST import scan cannot see these string-based runtime imports, so all architecture tests pass while the runtime dependency still exists.
- Impact: a service-layer module owns concrete repository/template construction and can add outward dependencies without the architecture gate observing them. This contradicts the explicit narrow-capability/composition-root decision and makes the dependency-direction acceptance criterion non-enforceable.
- Classification: introduced by the reviewed change; P2 and blocking because it violates the explicit architecture requirement.
- Required resolution: move compatibility construction to an explicit composition-layer module that may directly import repositories, services, and templates; remove the dynamic imports from `backend/services`; and add a regression check that responsibility packages cannot hide `backend.*` dependencies through dynamic module loading.

### [P2][REV-002] The architecture suite does not enforce exclusive FHIR/GDT table ownership

- Evidence: the only ZAC-60 additions to `tests/test_architecture_contract.py` are compatibility-delegate mappings (`:123-180`), while `tests/services/test_protocol_repository_wiring.py:73-83` checks composition with source-string containment. Neither test names or scans `local_fhir_workflow_records`, `local_fhir_sync_attempts`, or the five `local_gdt_*` tables. A repository-wide inspection currently finds operational SQL only in the intended owners, but no automated gate would fail if a second module began issuing SQL against those tables.
- Impact: the core requirement that FHIR/GDT tables have one discoverable owner can regress silently, and task 6.3 is marked complete without the requested table-ownership enforcement.
- Classification: introduced omission in the reviewed change; P2 and blocking because table-ownership architecture checks are an explicit acceptance item.
- Required resolution: add a deterministic architecture test that permits schema declarations but rejects operational SQL references to each protected table outside `backend/repositories/fhir_ledger.py` or `backend/repositories/gdt_workflow.py`, as appropriate.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...20406dca8f10181d0a3502f974b9dd68ea90ee57`, the active OpenSpec proposal/design/spec/tasks, all changed production paths, and the architecture/test deltas.
- Independent verification from the pinned head passed: 82 focused tests, 38 architecture tests, compilation, 337 full-suite tests, and strict OpenSpec validation.
- Repository search confirms current FHIR/GDT operational SQL is located in the intended repositories; REV-002 concerns the missing regression gate, not a presently duplicated SQL owner.
- Product code and tests remained committed and unchanged during review. The pre-existing dirty devlog verification record and this new review artifact are workflow records only.

## Next Action

`/dev-fix --review "openspec/changes/extract-fhir-gdt-workflow-repositories/review/2026-07-16_feature-ZAC-60_extract-fhir-gdt-workflow-repositories_codex-review-r1.md"`

Reason: REV-001 and REV-002 are blocking explicit architecture-acceptance findings.
