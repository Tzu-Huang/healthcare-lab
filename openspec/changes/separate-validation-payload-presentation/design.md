## Context

ZAC-56 through ZAC-60 moved SQLite ownership from `DemoStore` into bounded-context repositories. To preserve behavior and atomic writes, those extractions deliberately left some pure collaborators close to persistence: Patient, Order, and FHIR row projection lives in domain modules; dcm4chee and GDT row projection still lives in repository modules; GDT order preparation and presentation rules remain mixed with its ledger; and Lab/OIE validation or serialization still resides beside SQL. The placement guide also names several target paths that differ from the modules ultimately created.

The change is cross-cutting but behavior-preserving. Existing schemas, stored JSON, generated payloads, public API JSON, errors, ordering, timestamps, transaction boundaries, and compatibility calls are constraints. ZAC-62 owns service decomposition, ZAC-63 owns frontend modularization, ZAC-64 owns broad test-file decomposition, and ZAC-65 owns removal of `DemoStore` and obsolete exports.

## Goals / Non-Goals

**Goals:**

- Give validation, payload construction, and reusable presentation exactly one discoverable owner.
- Keep repository implementation centered on SQL, transactions, persistence ordering, and calls to injected pure collaborators.
- Add a mapper layer with enforceable inward dependencies.
- Finish the GDT protocol/domain/template/presentation split and extract dcm4chee row presentation.
- Apply the same boundary consistently to the small remaining Lab and OIE helpers.
- Add targeted static types at ambiguous collaborator seams without changing runtime JSON.
- Preserve safe autonomous progress while defining simple, mandatory stop conditions for YOLO-mode execution.

**Non-Goals:**

- Removing `DemoStore`, `backend/gdt_adapter.py`, or compatibility exports.
- Decomposing workflow services, frontend assets, or the large integration test module.
- Changing schema, migrations, persisted values, public JSON, protocol payload content, runtime behavior, or external integrations.
- Introducing an ORM, serialization framework, dependency, or generalized enterprise data-model layer.
- Moving GDT bridge directory health validation from its approved infrastructure boundary.

## Decisions

### Add a persistence-neutral mapper layer

Create `backend/mappers/` with context modules for reusable row and boundary presentation. Mappers may depend on other mappers and domain modules, but not on Flask, SQLite connection APIs, repositories, services, clients, runtime modules, or application composition. Repositories may import or receive mapper callables and invoke them after reads or within an existing transaction.

The architecture contract will recognize `mappers` as a responsibility package, allow repositories to depend on mappers, and reject inward dependency violations. Architecture documentation will distinguish mapper ownership from templates: templates construct outbound protocol payloads; mappers transform persistence or upstream shapes into established internal/public projections.

Alternative considered: leave projections in domain modules. Rejected because these functions know persistence column names and public JSON presentation details that are not domain policy. Alternative considered: leave projections beside SQL. Rejected because they are pure, reusable behavior and are a stated ZAC-61 extraction target.

### Migrate by bounded context while preserving injected seams

Patient, Order, and FHIR projectors move from domain modules to mappers. dcm4chee patient-sync, MWL, and result projectors move from repositories to DICOM mapper modules. GDT number/snapshot/attachment/presentation helpers move to domain or mapper owners according to whether they express protocol policy or shape conversion. Repositories retain their existing transaction sequence and invoke the new pure collaborators.

Default collaborator arguments are permitted where they preserve current construction ergonomics, but the implementation must have one owner. A wrapper may remain only when it is a documented compatibility export with retained callers; it must not duplicate the implementation.

Alternative considered: migrate every context in one mechanical rewrite. Rejected because context-sized commits and focused characterization reduce contract and transaction regression risk.

### Separate GDT parsing from outbound construction

GDT parsing, required-field validation, encoding rules, and inbound canonical interpretation remain in `backend/domain/gdt_protocol.py`. Outbound `6302` construction moves to `backend/templates/gdt.py`. Persistence candidate preparation and presentation move to explicit domain/mapper functions, while `GdtWorkflowRepository` retains the five-table atomic write sequence and matching-related SQL.

`backend/gdt_adapter.py` and `DemoStore` may temporarily re-export or delegate existing symbols, with the owner and retained callers documented for ZAC-65 cleanup.

### Include small Lab and OIE pure helpers, retain infrastructure validation

Lab server input validation and Lab/OIE row serialization move to domain or mapper modules so the repository-wide rule is consistent. OIE settings validation moves to an OIE domain owner; its profile and result presentation moves to mappers. `validate_gdt_bridge_dirs` remains in the approved health/infrastructure boundary because it validates filesystem readiness rather than a pure protocol or API payload.

Alternative considered: limit the change to the five contexts named in the Linear scope. Rejected because the global acceptance statement that repositories focus on persistence would otherwise remain knowingly false, and no later ticket owns these small repository-local pure helpers.

### Add targeted types without runtime model conversion

Use `TypedDict`, frozen dataclasses, or Protocols only where a shape crosses collaborators, is reused, or currently hides required keys behind `dict[str, Any]`. Existing public dictionaries remain dictionaries, and mapper/template results remain compatible with current JSON serialization. `GdtAdapterResult` remains the protocol result model. Types that merely rename a one-use local dictionary are not added.

Alternative considered: convert all API and persistence shapes to dataclasses. Rejected because it broadens the change, introduces serialization churn, and creates little value for a behavior-preserving extraction.

### Preserve contracts with characterization before movement

Before changing an owner, focused tests capture validation errors, normalized values, generated protocol payloads, row projections, and relevant transaction rollback behavior. Payload checks compare deterministic bytes or deep structures; presentation checks compare exact keys, nesting, defaults, and values. Existing nondeterministic timestamps remain controlled by injected factories. Architecture baselines may only shrink.

### Bound YOLO-mode autonomy with explicit stop conditions

Autonomous implementation may make routine in-scope decisions and resolve directly caused test, import, typing, fixture, or composition failures. It must stop before:

- schema, migration, seed, or stored-data mutation;
- access to `instance/*.db`, live OIE/Medplum/OpenEMR/dcm4chee/GDT resources, or deployment environments;
- public API, error, payload, persistence, or compatibility-contract changes;
- architecture legacy-baseline or allowlist expansion;
- dependency installation or framework introduction;
- destructive filesystem or Git operations;
- overwriting unrelated user changes or unsafe dirty-worktree overlap;
- unrelated service, frontend, test-suite, or facade cleanup.

The implementation may not bypass a stop condition by weakening or deleting tests, changing expected payloads without contract evidence, refreshing fingerprints, broadening allowlists, or silently accepting a different behavior. Verification and closure review remain mandatory; YOLO mode changes decision latency, not quality gates.

## Risks / Trade-offs

- [Moving pure functions changes import and patch seams] → Preserve documented compatibility exports, test retained callers, and defer removal to ZAC-65.
- [Mapper extraction accidentally changes JSON defaults or nested shapes] → Add exact characterization tests before movement and inject the same projector through repositories and enrichment loaders.
- [GDT split changes byte-sensitive payloads] → Freeze timestamp factories and compare outbound text byte-for-byte plus parsed/canonical structures.
- [New mapper layer becomes a miscellaneous dumping ground] → Require context ownership, pure dependencies, mirrored tests, and architecture enforcement.
- [Typed models cause broad annotation churn] → Add only seam-level types with demonstrated reuse or ambiguity; keep runtime dictionaries.
- [Repository calls to pure collaborators are mistaken for forbidden responsibility] → Architecture rules reject implementation ownership, not injected invocation needed for atomic operations.
- [YOLO safeguards become documentation only] → Represent boundaries in tasks, architecture tests where enforceable, verification commands, and closure review evidence.

## Migration Plan

1. Characterize current pure rules, payloads, and projections and record the exact compatibility export inventory.
2. Add mapper placement documentation and architecture dependency enforcement.
3. Move Patient, Order, and FHIR projection owners and update injected repository/enrichment collaborators.
4. Split GDT validation/parsing, outbound construction, persistence preparation, and presentation while preserving ledger transactions.
5. Move dcm4chee row projectors and consolidate protocol constants/helpers with their existing owners.
6. Move the small Lab/OIE validation and presentation helpers; retain the GDT bridge health boundary.
7. Shrink applicable legacy baselines, update owner/caller documentation, and run focused plus full verification using only disposable databases and external doubles.

Each context-sized product change is independently reversible through its focused commit. No schema or data rollback is needed because the change does not alter storage.

## Open Questions

None. Exploration resolved mapper ownership, Lab/OIE inclusion, targeted typing, and autonomous safety boundaries before proposal creation.
