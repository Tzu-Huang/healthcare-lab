## Context

ZAC-56 through ZAC-61 established bounded-context repositories and separated domain policy, outbound templates, and reusable presentation. The remaining service layer is uneven: `lab_workflow.py` coordinates dashboard, health, operations, and smoke behavior; FHIR and Order workflows mix several independently testable external-system use cases; and Patient/GDT services require review for similar cohesion problems. Existing APIs, startup paths, background runtime, persistence semantics, compatibility seams, and external protocol behavior are constraints.

ZAC-46 and ZAC-47 are being developed concurrently in separate worktrees. ZAC-46 changes `backend/app_factory.py` to compose a persisted OIE management client, making that file a known integration hotspot. Exploration and proposal for ZAC-62 may proceed from the ZAC-61 mainline, but implementation is intentionally gated until ZAC-46 is merged and the ZAC-62 branch is updated. ZAC-47 owns isolated OIE channel domain/template modules and is not an implementation gate.

## Goals / Non-Goals

**Goals:**

- Give each workflow service one cohesive use-case responsibility.
- Replace broad collaborators with narrow, typed capability ports.
- Keep services independent of Flask, concrete stores/repositories, runtime modules, SQL, and protocol/presentation implementation.
- Keep application assembly compact while preserving all route, startup, runtime, persistence, and integration behavior.
- Migrate by bounded context with focused characterization and architecture enforcement.
- Integrate ZAC-46 composition changes before any product implementation begins.

**Non-Goals:**

- Implementing or reorganizing ZAC-46 OIE management behavior or ZAC-47 channel templates.
- Adding OIE channel lifecycle capabilities.
- Removing `DemoStore`, compatibility exports, or legacy facades; ZAC-65 owns that work.
- Frontend modularization or broad integration-test file decomposition; ZAC-63 and ZAC-64 own those changes.
- Changing database schemas, stored data, public APIs, payloads, error policy, runtime lifecycle, or external integrations.
- Creating a generic service framework, dependency-injection container, or one-class-per-method structure.

## Decisions

### Gate product implementation on the ZAC-46 merge

The proposal artifacts are created from the ZAC-61 mainline, but `/dev-apply` MUST start only after ZAC-46 is merged and this branch is updated from `main`. The update must retain ZAC-46's OIE management client extension and settings wiring before service composition changes are made.

Alternative considered: implement immediately and resolve `app_factory.py` at the end. Rejected because both changes affect composition and late reconciliation can silently omit a dependency even when the textual conflict is small.

### Decompose around use cases, not file size alone

Lab will separate dashboard aggregation, health checks, service operations, smoke checks, and resource/status coordination. FHIR will separate sync, inventory/query, preview, DiagnosticReport, and retry/status coordination. Order/dcm4chee will separate patient, MWL, verification, result-refresh, and evidence/simulated-return coordination. Patient and GDT will be decomposed only where caller and collaborator inventories demonstrate independently meaningful responsibilities.

Each extracted unit must own decisions or orchestration for a cohesive use case and have focused tests. A class or function that only forwards the same broad arguments to another object is not a valid extraction.

Alternative considered: split by line-count thresholds. Rejected because it encourages arbitrary wrappers and fragments workflows that need atomic or ordered coordination.

### Define narrow ports at the consumer boundary

Each service declares Protocols or typed callables for only the operations it consumes. Ports use concrete parameter and return types and reject generic `*args`, `**kwargs`, bare `Any` returns, dynamic delegation, or a general store facade. Cross-context work uses an explicitly named coordinator composed at the application boundary.

Alternative considered: reuse repository classes as service types. Rejected because it couples use cases to concrete persistence and exposes unrelated methods.

### Preserve layer ownership established by ZAC-61

Services coordinate use cases. APIs own HTTP mapping; clients own transport; repositories own SQL and transactions; runtime owns listeners, watchers, retries, and lifecycle state; domain owns validation and policy; templates own outbound protocol construction; mappers own reusable row/boundary presentation. Extraction may move orchestration among service modules but must not pull these lower-layer implementations into services.

### Compose explicit services without growing the composition root

`backend/app_factory.py` may construct and register services, but it must not implement workflow decisions. Repeated wiring may move to a typed composition helper when that makes assembly smaller and remains explicit. Existing `app.extensions`, Blueprint inputs, callback seams, and runtime startup order remain compatible.

Alternative considered: introduce a dependency-injection framework. Rejected because it adds a dependency and obscures the explicit wiring relied on by tests and compatibility patches.

### Characterize before moving and migrate in bounded increments

Before each context is decomposed, record the owner/caller/collaborator inventory and lock down ordering, errors, projections, callback behavior, and partial-failure policy with focused tests. Implement context-sized commits, update composition immediately, and shrink applicable legacy baselines only when implementation has actually moved. Architecture allowlists and baselines may not grow.

## Risks / Trade-offs

- [ZAC-46 composition wiring is lost during refactoring] → Update from the merged ZAC-46 mainline before apply, inventory `app.extensions`, and add composition characterization before editing `app_factory.py`.
- [Decomposition creates pass-through classes] → Require a cohesive responsibility, narrow collaborator set, and focused behavior tests for every extracted service.
- [Workflow ordering or partial-failure behavior changes] → Characterize call order, persisted transitions, callbacks, and error mapping before moving code.
- [Ports become numerous or duplicate shapes] → Define ports at consumer boundaries, reuse an existing cohesive capability where the consumed operation set is identical, and avoid generic abstractions.
- [Import cycles appear across cross-context coordinators] → Keep shared types in domain modules and assemble explicit coordinators at the composition root without importing APIs or concrete repositories.
- [Broad refactoring collides with ZAC-63 through ZAC-65] → Limit production changes to service decomposition and necessary call-site wiring; defer frontend, broad test organization, and facade removal.

## Migration Plan

1. Before `/dev-apply`, confirm ZAC-46 is merged, update the feature branch from `main`, and record the retained OIE composition baseline.
2. Inventory current service responsibilities, callers, ports, composition keys, runtime callbacks, and compatibility seams.
3. Add focused characterization for Lab, FHIR, Order/dcm4chee, Patient, and GDT behavior.
4. Decompose Lab, then FHIR and Order/dcm4chee in context-sized commits, updating composition and tests with each move.
5. Review Patient and GDT against the cohesion criteria and extract only justified use cases.
6. Enforce narrow port signatures, inward dependencies, composition thinness, and a shrinking legacy baseline.
7. Run focused and full verification with disposable databases and external doubles, then audit public and startup compatibility.

Each context-sized extraction is independently revertible. No schema or data rollback is required.

## Open Questions

None for proposal creation. Exact class/module names and whether individual Patient/GDT responsibilities warrant extraction will be resolved from the apply-time owner/caller inventory after updating from ZAC-46.
