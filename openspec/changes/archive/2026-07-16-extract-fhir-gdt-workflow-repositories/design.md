## Context

ZAC-55 established the bounded-context placement contract, ZAC-56 extracted the shared SQLite owner, ZAC-58 separated core patient/order persistence, and ZAC-59 split dcm4chee persistence. FHIR and GDT are now the largest remaining persistence implementations in `DemoStore`.

FHIR workflow records and sync attempts are written and projected in `lab_store.py`, while patient/order enrichment performs additional FHIR-table queries in a generic enrichment module. FHIR-mode local order creation also writes `local_order_records`, whose stable owner is the existing order repository. The FHIR service still receives the entire `DemoStore`, even though Medplum HTTP behavior already belongs to the client/service side.

GDT patient contexts, orders, messages, attachments, workflow events, matching, and projections are implemented as one transactionally coupled area in `lab_store.py`. Raw GDT parsing, rendering, and 6302/6310 interpretation already have an adapter boundary, while bridge filesystem coordination belongs to the GDT service/runtime layer. The GDT service nevertheless receives the whole compatibility store.

The change is intended to be safe for unattended YOLO-mode implementation. Autonomous progress is useful for mechanical extraction, composition rewiring, and test repair, but it must not silently turn a structural refactor into a schema migration, behavior redesign, live integration exercise, or architecture-baseline bypass.

## Goals / Non-Goals

**Goals:**

- Give all FHIR ledger SQL and projections one discoverable owner using the shared connection factory and write lock.
- Give all GDT-owned SQL and projections one cohesive repository owner while preserving transactional matching and lifecycle recording.
- Preserve FHIR identifiers, dependency ordering, sync transitions, retry/audit evidence, Medplum references, and FHIR-mode order behavior.
- Preserve GDT patient snapshots, order identifiers, 6302/6310 persistence, matching precedence, unmatched results, attachments, events, and workbench projections.
- Keep protocol validation, payload creation, raw parsing/rendering, transport, filesystem, and cross-context orchestration in their proper layers.
- Replace broad `DemoStore` service dependencies with explicit capabilities and retain only mechanical compatibility delegates.
- Shrink the reviewed architecture baseline without replacement exceptions.
- Make YOLO-mode permissions, verification gates, resource isolation, failure handling, and hard stops explicit enough to be enforced from `tasks.md`.

**Non-Goals:**

- Change tables, columns, indexes, migrations, foreign keys, seed data, or existing stored rows.
- Change HTTP routes, request/response shapes, status codes, frontend behavior, configuration, or runtime startup behavior.
- Redesign FHIR identifier systems, resource mapping, state transitions, retry/idempotency, dependency ordering, or Medplum source-of-truth semantics.
- Redesign GDT field support, encoding, matching precedence, event vocabulary, attachment interpretation, bridge filenames, watcher behavior, or filesystem disposition.
- Move Medplum HTTP transport into a repository or move GDT raw parsing/rendering into persistence.
- Give the FHIR ledger repository ownership of generic `local_order_records` or the GDT repository ownership of generic patient records.
- Add an ORM, database driver, runtime dependency, background worker, distributed lock, or remote migration mechanism.
- Read, copy, repair, migrate, or modify a real `instance/*.db`, or contact a live Medplum, OpenEMR, dcm4chee, OIE, Docker, or other healthcare service during implementation or verification.

## Decisions

### Use one FHIR ledger repository as the table owner

Create `backend/repositories/fhir_ledger.py` with ownership of `local_fhir_workflow_records` and `local_fhir_sync_attempts`. It receives `database.connect` and `database.lock` and owns create/update/read operations, state transitions, identifier lookup, dependency ordering, sync-attempt history, row projection, and batch enrichment reads for patient/order projections.

Patient and order enrichment consume narrow batch loaders from the FHIR ledger owner rather than issuing FHIR SQL themselves. The repository does not import or accept `DemoStore`.

Alternative considered: leave enrichment SQL in `repositories/enrichment.py`. Rejected because multiple modules would continue to own reads and projections for the same FHIR ledger.

Alternative considered: split workflow records and attempts into separate repositories. Rejected because attempts are subordinate audit records whose lifecycle is inseparable from the workflow state transitions in this scope.

### Keep FHIR resource rules and local order ownership outside the ledger

Move or reuse FHIR validation, identifier mapping, resource normalization, and deterministic `ServiceRequest` construction in framework-independent domain/template modules. The FHIR ledger may receive normalized resources or injected pure projectors, but it does not construct protocol payloads or perform Medplum HTTP operations.

The existing order repository remains the sole owner of `local_order_records`. A named FHIR order coordinator combines a narrow synced-Patient-reference lookup, an order creation capability, pure FHIR validation/template collaborators, and FHIR ledger creation. It preserves the current sequence and failure semantics rather than introducing a new cross-table transaction.

Alternative considered: let the FHIR ledger repository insert FHIR-mode rows into `local_order_records`. Rejected because it creates overlapping table ownership and reverses the stable patient/order boundary from ZAC-58.

Alternative considered: make the order repository query FHIR ledger tables directly. Rejected because a core repository would absorb cross-context knowledge; the coordinator keeps that dependency explicit.

### Use one cohesive GDT workflow repository

Create `backend/repositories/gdt_workflow.py` with ownership of `local_gdt_patient_contexts`, `local_gdt_order_records`, `local_gdt_message_records`, `local_gdt_attachment_records`, and `local_gdt_workflow_events`. It owns their SQL, projections, transactional context/order/message/event creation, normalized-result matching, attachment persistence, unmatched-result persistence, and workbench aggregation from stored GDT data.

The repository receives a narrow patient snapshot or loader capability and normalized GDT data. Raw message parsing, rendering, encoding checks, 6302 request construction, and 6310 interpretation remain in `gdt_adapter.py` or a template/domain module. Bridge path discovery, file claiming, archive/delete/error disposition, and watcher lifecycle remain in services/runtime.

Alternative considered: split contexts, orders, messages, attachments, and events into five repositories. Rejected because supported order/result workflows write these records together and require one transaction and matching policy; five owners would add coordination without isolating independent lifecycles.

Alternative considered: put parsing and rendering inside the repository to keep the workflow in one file. Rejected because persistence would then own protocol payload policy and violate the established dependency direction.

### Compose narrow capabilities directly

`FhirWorkflowService` receives the FHIR ledger port plus its existing Medplum-facing collaborators. `GdtWorkflowService` receives the GDT repository port plus bridge/runtime collaborators. Patient and order services receive explicit FHIR coordination capabilities; they do not receive `DemoStore` or a wrapper with arbitrary forwarding.

Cross-ledger work is implemented by named coordinators assembled in `backend/app_factory.py`. Concrete repositories do not import unrelated concrete repositories or API modules.

Alternative considered: hide the new repositories behind unchanged broad coordinator facades. Rejected because moving SQL alone would not satisfy the narrow runtime-port acceptance criterion.

### Preserve compatibility through mechanical delegation and baseline reduction

Existing tests or callers may continue to invoke enumerated FHIR/GDT methods on `DemoStore`. Each retained method delegates directly to a repository, pure collaborator, or named coordinator and contains no SQL, protocol rules, raw parsing/rendering, transport, filesystem, or workflow implementation.

Architecture-baseline entries corresponding to extracted implementation are removed. A replacement fingerprint, refreshed hash, new allowlist, weakened classifier, skipped test, or broad compatibility exception is prohibited.

### Characterize behavior before movement and preserve transaction boundaries

Before extraction, focused tests pin FHIR upsert/idempotency, changed-payload requeueing, state transitions, attempts, ordering, synced-Patient order requirements, and local-order failure behavior. GDT tests pin patient-number snapshots, order/message/event creation, exact result matching precedence, unmatched results, attachment status/details, event isolation, and transaction rollback.

Implementation moves one bounded owner at a time. Each increment runs its nearest disposable-database tests before composition changes continue. Repository write methods retain the shared reentrant lock and connection transaction; injected pure collaborators that fail inside a write must not expose partial ledger state.

### Define an enforceable YOLO-mode safety contract

Autonomous implementation may choose internal class/helper names, injected callable shapes, test fixture organization, and focused commit boundaries. It may resolve directly caused import cycles, typing errors, composition mismatches, and failing focused tests when the resolution stays inside this change and preserves the contracts below.

Before every implementation increment, the agent must inspect the current diff and worktree, identify the exact files in scope, and preserve unrelated user changes. It must stage explicit paths only and create reviewable commits after the relevant focused tests pass. It must not use destructive Git operations, broad staging, baseline regeneration, test skipping, or assertions weakened solely to obtain a pass.

Automated tests must use temporary SQLite paths and external-service doubles. Commands that could resolve to `instance/*.db`, a configured non-temporary database, Docker, or a live healthcare endpoint are prohibited. No implementation task authorizes deployment, service restart, data repair, remote mutation, or secret use.

YOLO mode must stop and report evidence instead of improvising when any of these conditions is proven:

- completion requires a schema/index/migration change, destructive SQL, table rebuild, row deletion, historical-data rewrite, or access to a real database;
- completion requires live Medplum/OpenEMR/dcm4chee/OIE/Docker/network interaction or a secret not already used by isolated tests;
- characterization conflicts with an acceptance criterion or requires changing a public API, status code, deterministic payload, identifier, state transition, retry, ordering, matching, event, attachment, or filesystem behavior;
- architecture checks can pass only by adding/refreshing a baseline entry, allowlist, classifier exclusion, or compatibility exception;
- completion requires a new runtime dependency, broader bounded-context extraction, unrelated cleanup, or material expansion beyond ZAC-60;
- an unexpected dirty-worktree overlap makes the intended files unsafe to isolate;
- verification exposes data loss, partial commits, lock regression, non-idempotent behavior, or nondeterminism that cannot be corrected without one of the prohibited changes.

Ordinary test failures, import cycles, typing issues, internal naming choices, and directly caused fixture or composition maintenance are not hard stops. They must be fixed within scope and routed back through focused verification. A hard stop must identify the failing invariant, command/test evidence, affected files, and the smallest decision needed from the user; it must not be bypassed by changing the proposal contract.

## Risks / Trade-offs

- [FHIR enrichment remains a hidden second ledger owner] -> Move all FHIR-table batch reads and projection responsibility behind the FHIR ledger repository and enforce ownership in architecture tests.
- [FHIR-mode order creation crosses repository boundaries] -> Use a named coordinator while keeping `local_order_records` SQL in the order repository and FHIR-table SQL in the FHIR ledger.
- [GDT extraction accidentally mixes raw protocol parsing with SQL] -> Feed normalized adapter output into the repository and add import/placement checks plus representative deterministic payload tests.
- [GDT matching or event ordering changes during movement] -> Characterize precedence, unmatched behavior, event scope, attachment details, and rollback before extraction.
- [Compatibility delegates become a second implementation] -> Enumerate mechanical delegates and reject SQL, parsing, payload, transport, filesystem, or orchestration in their bodies.
- [YOLO mode broadens scope after a failing test] -> Use the explicit hard-stop list, file-scoped commits, disposable resources, and mandatory re-verification instead of opportunistic redesign.
- [Many narrow capabilities make composition verbose] -> Prefer small named coordinators and cohesive ports over general facade access; accept explicit wiring as the boundary cost.

## Migration Plan

1. Add characterization and rollback tests for protected FHIR and GDT behavior using disposable SQLite databases and service doubles.
2. Extract or reuse pure FHIR/GDT domain, adapter, and template collaborators without changing deterministic outputs.
3. Introduce the FHIR ledger repository and route workflow state, attempts, projections, and enrichment through it.
4. Coordinate FHIR-mode order creation through the order owner and explicit FHIR capabilities.
5. Introduce the cohesive GDT workflow repository and move normalized workflow persistence in transactional increments.
6. Compose FHIR/GDT services and patient/order coordination from narrow capabilities; convert retained `DemoStore` methods to mechanical delegates.
7. Remove extracted legacy-baseline entries and run focused repository/domain/template/service, architecture, integration, compilation, and full regression gates.
8. Perform a final diff/scope audit confirming no schema, migration, dependency, real-database, live-service, public-contract, or unrelated changes.

Deployment requires no data or schema migration. Rollback is a code rollback because the extracted owners use the existing schema and stored formats. If any hard-stop condition appears, implementation pauses before the prohibited change and records the evidence for reviewed follow-up.

## Open Questions

None. Repository ownership, coordination boundaries, protected behavior, autonomous permissions, and hard stops are explicit; a proven hard-stop condition requires user review rather than autonomous scope expansion.
