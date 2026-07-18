---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-62_decompose-workflow-services
base: main
reviewed_head: 98680cde4d2fe29eca2cd91d5ab620b393d8cd9b
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] Dashboard check-all returns the pre-check snapshot

`backend/api/dashboard.py:58` evaluates `snapshots.snapshot()` before invoking
`DashboardActionService.check_all`. The extracted action service then runs all
health checks at `backend/services/lab_workflow.py:314` and merges the already
captured snapshot into the response. Before this change, `DashboardWorkflowService.check_all`
ran the health checks first and called `self.snapshot()` afterward, so returned
items, summary, resources, and events reflected the newly persisted health
state. The new ordering can return stale dashboard status immediately after a
successful check-all operation, violating the explicit call-order and returned-
projection compatibility requirements. Classification: branch-introduced
correctness regression. Required resolution: capture the snapshot after health
checks complete, while retaining focused snapshot/action ownership, and add a
regression test that asserts call order and returned post-check state.

### [P2][REV-002] Focused services still accept broad or generic collaborators

The change marks task 6.2 complete, but focused services share ports containing
operations they do not consume and continue to accept generic variadic
callables. For example, every FHIR service receives the eleven-operation
`FhirRepositoryPort` declared at `backend/services/fhir_workflow.py:40`, while
the individual consumers begin at lines 75, 99, 122, and 176; Lab services
similarly share `LabRepositoryPort` from `backend/services/lab_workflow.py:64`.
New focused constructors also retain `Callable[..., ...]`, including FHIR lines
78/125/164 and Lab lines 187/212/307. This directly violates the OpenSpec
requirement that each service receive consumer-owned capabilities with concrete
signatures and no generic variadics. The architecture test only inspects
Protocol methods, so it cannot detect the generic callable annotations or a
shared port exposing unrelated operations. Classification: explicit acceptance
criterion violation. Required resolution: define or reuse capability-sized
Protocols/typed callable Protocols with concrete signatures for each focused
consumer, and strengthen the architecture test to reject generic callable
annotations and excess shared capability surfaces.

### [P2][REV-003] GDT Order extraction is a behavior-free forwarding wrapper

`GdtOrderService` at `backend/services/gdt_workflow.py:91` consists solely of
three unchanged repository forwards at lines 95-102. The OpenSpec requirement
explicitly says Patient/GDT responsibilities must not be split into behavior-
free forwarding wrappers. The new detector in
`tests/services/test_zac62_architecture_enforcement.py:40-45` only considers
classes whose names end in `Facade` or `Wrapper`, so a behavior-free class named
`*Service` is silently accepted. Classification: explicit acceptance criterion
violation introduced by the decomposition. Required resolution: keep the
cohesive GDT order responsibility with an existing owner or give the focused
service independently meaningful coordination, and make the detector identify
behavior-free service shapes without relying on `Facade`/`Wrapper` suffixes.

## Follow-up findings

None.

## Verification and residual risk

Reviewed `main...98680cde4d2fe29eca2cd91d5ab620b393d8cd9b`, the OpenSpec design/spec/tasks,
all changed production modules, and focused architecture/composition tests.
The persisted verification round reports 47 service, 2 API, 5 runtime, 175
composition/repository-wiring/architecture/integration, and 396 complete-suite
tests passing, plus compilation, frontend syntax, strict OpenSpec validation,
and diff checks. Residual risk is concentrated in missing assertions for the
three findings above; green tests do not demonstrate those explicit contracts.

## Next Action

`/dev-fix --review "openspec/changes/decompose-workflow-services/review/2026-07-18_feature-zac-62-decompose-workflow-services_codex-review-r1.md"`

Reason: blocking findings REV-001, REV-002, and REV-003 remain.
