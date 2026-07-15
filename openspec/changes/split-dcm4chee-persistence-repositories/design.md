## Context

ZAC-56 established `SQLiteDatabase` as the shared owner of the connection factory, transaction lifecycle, application write lock, migrations, and startup maintenance. ZAC-58 extracted generic patient and order ledgers, but their enrichment loaders and protocol coordinators still reach dcm4chee persistence implemented across `DemoStore`, `backend/repositories/enrichment.py`, and the MWL maintenance backfill.

The remaining dcm4chee implementation mixes five concerns: patient-sync mappings and attempts; MWL mappings, attempts, readback, verification, and historical repair; result reconciliation and refresh snapshots; DICOM payload/identifier rules; and cross-context demo/evidence workflows. The extraction must preserve observable behavior while preventing the three repositories from becoming new catch-all modules.

This change is intended to be safe for unattended or YOLO-mode implementation. Autonomous work is permitted within explicit boundaries, while data-destructive, live-service, compatibility-changing, and scope-expanding actions are hard stops.

## Goals / Non-Goals

**Goals:**

- Give patient-sync, MWL, and result persistence separate repository owners using the shared connection factory and lock.
- Group all dcm4chee ledger SQL, enrichment reads, row projection, and MWL backfill with the matching owner.
- Preserve retries, stable identifiers, readback-before-repost behavior, verification, reconciliation precedence, duplicate diagnostics, refresh publication, and legacy convergence.
- Keep DICOM parsing, payload creation, UID/identifier rules, status policy, and cross-context orchestration outside repositories.
- Replace broad patient/order protocol facades with explicit capability ports and direct composition.
- Retain mechanical compatibility delegates and reduce the architecture baseline without replacement exceptions.
- Permit autonomous internal refactoring while enforcing test, resource, scope, and stop-condition guardrails.

**Non-Goals:**

- Change tables, columns, indexes, migrations, stored rows, or identifier formats.
- Change HTTP routes, request/response shapes, status codes, frontend behavior, or live dcm4chee behavior.
- Redesign reconciliation precedence, retry classification, refresh-generation ordering, or backfill selection rules.
- Add an ORM, new runtime dependency, background worker, distributed lock, or remote migration mechanism.
- Read, copy, repair, migrate, or modify a real `instance/*.db`.
- Contact or mutate live dcm4chee, OpenEMR, Medplum, OIE, Docker, or other healthcare services during automated implementation or verification.

## Decisions

### Split persistence by ledger ownership

Create three repository modules: `dcm4chee_patient_sync.py`, `dcm4chee_mwl.py`, and `dcm4chee_results.py`. Each receives `database.connect` and `database.lock` directly and owns its table SQL and row projections. None accepts, imports, or dynamically forwards to `DemoStore`.

The patient-sync repository owns `local_dcm4chee_patient_syncs` and `local_dcm4chee_patient_sync_attempts`. The MWL repository owns `local_dcm4chee_mwl_mappings` and `local_dcm4chee_mwl_attempts`. The result repository owns `local_dcm4chee_result_records` and `local_dcm4chee_result_refresh_runs`.

Alternative considered: one `dcm4chee.py` repository. Rejected because the issue explicitly calls for three narrower persistence capabilities and a single owner would retain the largest bounded-context surface.

### Keep cross-ledger reads explicit

Result reconciliation may consume MWL mapping candidates through an injected narrow lookup callable or port. Patient/order enrichment loaders receive explicit dcm4chee loaders/projectors during composition rather than issuing dcm4chee SQL themselves or importing a concrete repository across contexts. Cross-context aggregation remains in a service or composition adapter.

Alternative considered: allow each repository to query any dcm4chee table. Rejected because it obscures ownership and makes future changes to mapping, result, or enrichment behavior inseparable.

### Move MWL backfill ownership without changing startup orchestration

`SQLiteDatabase` continues to sequence migrations and maintenance under the initialization lock. The deterministic historical mapping repair implementation moves beside the MWL repository and remains callable with the active startup connection. It must not open a second connection, commit independently, overwrite an existing mapping, or alter its latest-attempt selection.

Alternative considered: run backfill lazily from the MWL repository constructor. Rejected because initialization ordering and transaction behavior are already established infrastructure contracts.

### Keep DICOM rules and payloads pure

DICOM JSON parsing, UID and identifier normalization, reconciliation policy, retry/status projection, and payload builders move to or are reused from framework-independent domain/template modules. Repositories may receive pure callables for projection or normalized inputs, but repository modules do not construct ADT/MWL payloads or parse transport response bodies.

Alternative considered: copy the current helpers into each repository. Rejected because it duplicates protocol policy and violates the issue boundary.

### Use capability-specific service ports

Patient and order workflows receive only the patient-sync, MWL, result, FHIR, and core-ledger capabilities they call. The composition root may assemble small named coordinators for workflows spanning multiple ledgers, including E2E fixtures, evidence aggregation, simulated AP returns, and patient result refresh. A nominally narrow wrapper with arbitrary `__getattr__` forwarding is prohibited.

Alternative considered: retain `PatientProtocolCoordinator` and `OrderProtocolCoordinator` unchanged with the new repositories hidden behind `DemoStore`. Rejected because it moves SQL without satisfying narrow service-port acceptance.

### Preserve compatibility through mechanical delegation

Existing callers may continue using enumerated dcm4chee methods on `DemoStore`; retained methods delegate directly to the owning repository, domain/template helper, or explicit workflow coordinator. They contain no SQL, payload, parsing, or orchestration implementation. New composition uses owning collaborators directly.

Extracted architecture-baseline entries are removed. No baseline hash may be added or refreshed solely to permit replacement implementation.

### Characterize before movement and verify with disposable resources

Before moving implementation, focused characterization tests pin patient-sync success/failure/retry state, MWL create/readback/retry/verification behavior, reconciliation precedence and wrong-patient handling, duplicate diagnostics, refresh snapshot publication and generation ordering, and historical backfill. All database tests create isolated temporary files; transport tests use doubles.

### YOLO autonomy, invariants, and hard stops

Autonomous implementation may choose internal helper names, protocol partitioning, injected callable shapes, fixture organization, and focused commit granularity. It may fix directly caused imports, typing, circular dependencies, test fixtures, and composition wiring without asking for approval.

Every implementation increment must remain reviewable and reversible: stage only intended files, use focused commits, run the nearest focused tests before continuing, and run architecture plus regression gates before closure. Unrelated dirty-worktree content must be preserved. Destructive Git operations, broad staging, baseline regeneration, and bypassing failing tests are prohibited.

Implementation must stop and report evidence instead of improvising when any of these conditions is proven:

- completion requires destructive SQL, schema/index changes, application-row deletion, table rebuilding, or access to a real `instance/*.db`;
- completion requires contacting or mutating a live external service, Docker environment, or non-disposable database;
- characterization conflicts with an acceptance criterion or requires changing a public API, status code, deterministic payload, identifier, retry, reconciliation, refresh, duplicate, or backfill behavior;
- architecture checks can pass only by adding or refreshing a legacy-baseline exception;
- completion requires a new dependency, secret, elevated permission, unrelated bounded-context extraction, or material expansion beyond ZAC-59;
- an unexpected dirty-worktree overlap prevents safely isolating the requested change.

Ordinary test failures, import cycles, type errors, internal naming decisions, fixture maintenance, and directly caused composition changes are not hard stops and must be resolved autonomously within scope.

## Risks / Trade-offs

- [Result reconciliation becomes coupled to the MWL implementation] -> Inject a narrow mapping lookup contract and test precedence independently.
- [Enrichment keeps hidden dcm4chee SQL outside the new owners] -> Add ownership tests and route enrichment through explicit loaders.
- [Backfill timing or transaction behavior changes] -> Retain startup orchestration and characterize legacy repair using disposable databases.
- [Payload or identifier behavior changes during helper extraction] -> Pin representative deterministic outputs before movement.
- [Compatibility delegates become a second implementation] -> Require mechanical forwarding and architecture inspection.
- [Narrow ports create verbose composition] -> Prefer explicit cohesive capability adapters over general facade access.
- [YOLO mode silently broadens scope after a failure] -> Enforce the hard-stop list, focused commits, resource isolation, and full closure verification.

## Migration Plan

1. Characterize all protected patient-sync, MWL, result, refresh, reconciliation, duplicate, and backfill behavior on disposable resources.
2. Extract or inject pure DICOM parsing, identifier, status, and payload collaborators.
3. Introduce the three repositories and move table SQL plus projections in bounded increments.
4. Route enrichment and startup backfill through the owning repositories without changing ordering or output.
5. Split service ports, add explicit cross-ledger coordinators, and update `app_factory.py` composition.
6. Convert retained `DemoStore` seams to mechanical delegates and remove extracted architecture-baseline entries.
7. Run focused, database, service, API/integration, architecture, compilation, full regression, and strict OpenSpec verification.

Deployment requires no schema or data migration. Rollback is a code rollback because both implementations use the same existing schema and observable data formats.

## Open Questions

None. The repository boundaries and YOLO-mode stop conditions are explicit; a proven hard-stop condition requires a reviewed follow-up rather than autonomous scope expansion.
