---
issue: ZAC-61
change: separate-validation-payload-presentation
branch: feature/ZAC-61_separate-validation-payload-presentation
proposal_commit: 6768d8955422522955bff143f2ad0001a972327b
next_command: /dev-apply ZAC-61
created_at: 2026-07-16
---

# ZAC-61 Dev Apply Handoff

## Objective

Implement the approved OpenSpec change `separate-validation-payload-presentation` for ZAC-61. Complete the responsibility cleanup after ZAC-56 through ZAC-60: validation and normalization belong to domain modules, outbound protocol construction belongs to templates, reusable row/boundary presentation belongs to mappers, and repositories retain SQL, transactions, persistence ordering, and calls to injected pure collaborators.

This is a behavior-preserving refactor. Do not reinterpret the ticket as another repository extraction or as permission to begin ZAC-62 through ZAC-65.

## Required Context

Read these files completely before implementation:

1. `openspec/changes/separate-validation-payload-presentation/proposal.md`
2. `openspec/changes/separate-validation-payload-presentation/design.md`
3. `openspec/changes/separate-validation-payload-presentation/specs/healthcare-lab-typed-application-architecture/spec.md`
4. `openspec/changes/separate-validation-payload-presentation/tasks.md`
5. `openspec/changes/separate-validation-payload-presentation/linear.yml`
6. `docs/architecture.md`
7. `openspec/specs/healthcare-lab-typed-application-architecture/spec.md`
8. `tests/test_architecture_contract.py`
9. `tests/architecture_legacy_baseline.py`

Read Linear issue ZAC-61 for the original goal and acceptance criteria. The OpenSpec artifacts are the implementation-ready refinement of that issue and resolve the scope questions discussed during exploration.

## Repository State at Handoff

- Branch: `feature/ZAC-61_separate-validation-payload-presentation`
- Proposal commit: `6768d8955422522955bff143f2ad0001a972327b`
- Proposal commit subject: `propose(ZAC-61): separate-validation-payload-presentation bootstrap`
- OpenSpec strict validation passed for `separate-validation-payload-presentation`.
- The branch was clean before this handoff record was created.
- The proposal was linked to ZAC-61 and a `[progress]` Linear comment was posted.
- No product implementation has started.

At the preceding main-branch audit, 341 complete unit/integration tests, 42 architecture-contract tests, Python compilation, 16 strict OpenSpec specs, and `git diff --check` passed. Treat these as historical baseline evidence, not a substitute for fresh task-scoped and final verification.

## Why This Scope Exists

The earlier sequence is directionally correct:

- ZAC-53 established responsibility-oriented packages and a thin process entrypoint.
- ZAC-55 established placement and architecture enforcement.
- ZAC-56 extracted shared SQLite infrastructure.
- ZAC-57 extracted Lab/OIE/OpenEMR persistence boundaries.
- ZAC-58 extracted Patient/identifier/Order persistence and already moved much Patient/Order validation and payload construction.
- ZAC-59 extracted dcm4chee Patient-sync/MWL/Result persistence.
- ZAC-60 extracted FHIR and GDT persistence.

ZAC-61 therefore finishes pure-responsibility ownership rather than repeating those extractions. `DemoStore` shrank from 8,021 to 1,214 lines, but compatibility constants, helpers, projectors, and delegates remain. Actual removal belongs to ZAC-65.

One historical process gap was found: the last ZAC-55 review artifact remained marked `Changes requested`, although its final facade-caller fix was committed and the current architecture tests prove the issue closed. Do not create a retroactive review artifact or expand ZAC-61 to repair historical workflow records.

## Current Responsibility Inventory

### Patient

- Validation/normalization already lives in `backend/domain/patient.py`.
- Protocol payload construction already lives in `backend/templates/patient.py`.
- Move reusable row presentation from the domain module to the Patient mapper.
- Preserve Patient API shape, protocol filters, FHIR enrichment, dcm4chee sync/results enrichment, identifier allocation, and transaction behavior.

### Order

- Validation/normalization already lives in `backend/domain/order.py` and `backend/domain/fhir_order.py`.
- ORM and FHIR payload construction already lives in templates.
- Move reusable row presentation from the domain module to the Order mapper.
- Preserve send-result fields, FHIR/dcm4chee enrichment, identifier finalization, and transaction behavior.

### FHIR

- Ledger validation/identifier rules are already in `backend/domain/fhir_ledger.py`.
- ServiceRequest construction is already in `backend/templates/fhir.py`.
- Move workflow-record and sync-attempt presentation to the FHIR mapper.
- Preserve dependency order, sync state, OperationOutcome, enrichment, identifiers, and all returned JSON.

### GDT

This is the largest remaining responsibility split.

- Keep parsing, encoding validation, required-field rules, and inbound `6310` interpretation in `backend/domain/gdt_protocol.py`.
- Move outbound `6302` construction to `backend/templates/gdt.py`.
- Move patient/order numbering and persistence preparation to pure domain collaborators.
- Move snapshots, attachment mapping, and order/message/attachment/event/workbench projection to `backend/mappers/gdt.py`.
- Keep the five-table SQL and atomic result/order/event writes in `GdtWorkflowRepository`.
- Preserve GDT text byte-for-byte, canonical payloads, matching precedence, event order, attachments, errors, and rollback.

### dcm4chee

- Validation, identifiers, reconciliation, and status policy already have domain owners.
- ADT/MWL construction already has a template owner.
- Move Patient-sync, MWL, attempt, Result, and refresh-snapshot row projectors from repositories to DICOM mapper modules.
- Consolidate duplicate constants/wrappers without changing retry, verification, reconciliation, generation, or enrichment semantics.

### Lab and OIE

These small helpers are intentionally included so the repository-wide rule becomes true:

- Move Lab server payload validation to the Lab domain and Lab server/operation projection to a Lab mapper.
- Move OIE settings validation to the OIE domain and settings/result presentation to OIE mappers.
- Preserve OIE password handling, duplicate behavior, listener behavior, workbench shapes, locks, and transactions.
- Do not move `validate_gdt_bridge_dirs`; filesystem readiness validation remains in its approved health/infrastructure boundary.

## Architecture Decision

Introduce `backend/mappers/` and mirrored `tests/mappers/` modules by bounded context.

Dependency intent:

```text
repositories -> mappers -> domain
repositories -> templates -> domain
```

Mappers must not execute SQL, manage transactions, depend on Flask, or import repositories, services, clients, runtime, or application composition. Repositories may invoke mappers, validators, and templates needed for an atomic persistence operation, but must not implement those pure responsibilities.

Use targeted `TypedDict`, frozen dataclass, or Protocol types only where shapes cross collaborators or `dict[str, Any]` hides required structure. Do not convert all API/persistence dictionaries into runtime model objects. Preserve existing dictionaries and JSON serialization.

## YOLO-Mode Rules and Stop Conditions

The user approved autonomous implementation with bounded safeguards.

You may proceed without asking for routine, in-scope decisions and directly caused:

- focused test failures;
- import cycles;
- typing corrections;
- fixture adjustments that preserve existing behavior;
- composition wiring mismatches;
- internal naming and module-placement decisions already resolved by the design.

Stop before performing any of the following and report evidence plus the smallest required user decision:

- schema, migration, seed, or persisted-data mutation;
- access to real `instance/*.db` data;
- live OIE, Medplum, OpenEMR, dcm4chee, GDT, Docker, or deployment actions;
- public API, validation error, payload, persistence, runtime, or compatibility-contract changes;
- architecture legacy-baseline, compatibility allowlist, or fingerprint expansion;
- dependency installation, new framework, or serialization library;
- destructive filesystem or Git operations;
- overwriting unrelated user changes or unsafe dirty-worktree overlap;
- unrelated service decomposition, frontend modularization, broad test-file cleanup, or facade removal.

Never bypass a stop condition by weakening/deleting tests, changing expected payloads without contract evidence, refreshing fingerprints, broadening allowlists, or silently accepting altered behavior. YOLO mode does not skip `/dev-test` or `/dev-review`.

## Apply Workflow Expectations

- Resolve exactly this active change from the branch and OpenSpec directory.
- Check and preserve the worktree before editing.
- Work through `tasks.md` in dependency order and by bounded context.
- Keep one logical task per commit when feasible.
- Add characterization coverage before moving implementation.
- Tick only tasks whose implementation and focused verification are complete.
- Stage only the task's code, tests, and exact `tasks.md` state; never use `git add -A`.
- Commit with focused subjects such as `refactor(ZAC-61): extract patient row mapper`.
- After each implementation commit, post the required literal-path `[progress]` Linear comment according to the `dev-apply` skill.
- Architecture baselines and compatibility caller inventories may only shrink.
- Continue until all requested tasks are complete or a protected boundary is reached, then route to `/dev-test`.

## Recommended First Implementation Slice

Start with tasks 1.1 through 1.7:

1. Record the exact current owner/export/caller inventory.
2. Add characterization tests before movement.
3. Establish `backend/mappers/` and `tests/mappers/`.
4. Extend dependency and repository-responsibility architecture checks.
5. Reconcile `docs/architecture.md` with actual ZAC-58 through ZAC-60 paths.
6. Record the YOLO stop conditions in durable project guidance.

Do not begin broad context moves until the mapper layer and its enforcement are green.

## Codex Opener Prompt

Copy the following into the new project session:

```text
/dev-apply ZAC-61

Continue the approved OpenSpec change `separate-validation-payload-presentation` on branch `feature/ZAC-61_separate-validation-payload-presentation`.

Before editing, read completely:
- `openspec/changes/separate-validation-payload-presentation/dev-apply-handoff.md`
- `openspec/changes/separate-validation-payload-presentation/proposal.md`
- `openspec/changes/separate-validation-payload-presentation/design.md`
- `openspec/changes/separate-validation-payload-presentation/specs/healthcare-lab-typed-application-architecture/spec.md`
- `openspec/changes/separate-validation-payload-presentation/tasks.md`
- `openspec/changes/separate-validation-payload-presentation/linear.yml`
- Linear issue ZAC-61

Confirm the branch, proposal commit `6768d8955422522955bff143f2ad0001a972327b`, active change, and worktree state. Then implement tasks in dependency order using focused commits and tests, ticking exact tasks only when complete and posting required `[progress]` Linear comments after commits.

Follow the mapper/domain/template/repository ownership decisions and the bounded YOLO-mode rules in the handoff and design. Proceed autonomously on routine in-scope failures, but stop before schema/data mutation, real DB or live-service access, public contract changes, baseline/allowlist expansion, dependencies, destructive operations, unsafe user-change overlap, or unrelated ZAC-62 through ZAC-65 work. Do not weaken tests or compatibility expectations to make the extraction pass.

Begin with the safety baseline and mapper placement/enforcement tasks before moving bounded-context implementations. When all apply tasks and focused checks are complete, route to `/dev-test` rather than declaring the workflow done.
```
