## Context

ZAC-56 moved database path, connection lifecycle, the application write lock, ordered migrations, and startup maintenance into `backend/repositories/database.py`. The placement contract now assigns lab control-plane persistence to `backend/repositories/lab.py`, OIE persistence to OIE repositories, and external OpenEMR transport to a client adapter. Despite those foundations, `DemoStore` still contains the lab registry and operation-history SQL, OIE result SQL and row mapping, and the `OpenEMRProcedureOrderSource` MariaDB query.

The affected HTTP and runtime paths already pass through lab and OIE services, but several structural ports are implemented by the entire `DemoStore`. Existing application assembly and tests also import the OpenEMR source from `lab_store.py`. The extraction must therefore change ownership and composition without changing URLs, payloads, status codes, database schema, lock semantics, or the supported behavior of missing OpenEMR schema.

## Goals / Non-Goals

**Goals:**

- Establish a repeatable bounded-context repository extraction using the shared SQLite infrastructure.
- Move all lab server and operation-history SQL into a lab repository.
- Move all OIE result SQL and result row mapping into an OIE repository while retaining the existing settings repository.
- Separate OpenEMR MariaDB querying from both `DemoStore` and SQLite repositories.
- Compose services and runtime components with narrow ports and keep `DemoStore` methods only as explicit compatibility delegates.
- Preserve observable application behavior and replace mixed store assertions with focused tests.
- Make unattended implementation safe by requiring disposable databases, external-service doubles, and architecture-baseline reduction rather than exception growth.

**Non-Goals:**

- Change tables, indexes, migrations, seed data, or legacy database convergence behavior.
- Extract patient, order, FHIR, GDT, or dcm4chee persistence.
- Add OIE management/channel features or OpenEMR write operations.
- Change API, frontend, listener protocol, Docker control, or deployment behavior.
- Add dependencies, contact live lab services during automated verification, or push/merge/release as part of implementation.

## Decisions

### Compose repositories from the shared SQLite owner

`DemoStore.__init__` will construct `LabRepository` and `OieRepository` with `self.database.connect`, `self.database.lock`, and the required validators, serializers, and timestamp functions. Retained `DemoStore` public methods will delegate to those instances. The repositories will not accept or import `DemoStore`.

The lab repository will own server CRUD, persisted health updates, operation history, and their row projections. The OIE repository will own inbound result insert/query behavior, duplicate detection, matching-reference persistence, error records, and OIE result row projections. `OieSettingsRepository` remains a separate focused owner; settings validation/serialization may move to OIE domain/repository helpers so it no longer depends on bound `DemoStore` implementation.

Alternative considered: create one repository that receives `DemoStore.connect`. Rejected because it preserves the general facade as the infrastructure owner and obscures the shared-lock contract established by ZAC-56.

### Keep cross-context OIE coordination in services

OIE result persistence necessarily records references to patient and order rows, but it will not absorb general patient/order inventory ownership. The OIE workflow service will receive separate narrow collaborators for OIE results and the retained patient/order operations it coordinates. Workbench assembly remains service behavior because it joins projections owned by multiple bounded contexts.

During this extraction, the patient/order collaborator may still be a narrow structural adapter implemented by `DemoStore`; that does not authorize moving unrelated patient/order SQL or exposing the entire store as the OIE result repository.

Alternative considered: move `list_oie_workbench`, ADT inventory, and order inventory wholesale into `OieRepository`. Rejected because that would make an OIE persistence adapter own cross-context patient and order queries and broaden ZAC-57 into later repository extractions.

### Treat OpenEMR MariaDB access as an external client

`backend/clients/openemr.py` will own configuration status, connection creation, the procedure-order SELECT, missing-schema classification, list/get behavior, and query verification. Pure normalization and OpenEMR-row-to-GDT-order mapping will live in `backend/domain/openemr.py`. `app_factory.py` will construct and expose the client directly; `lab_store.py` will no longer import PyMySQL or contain OpenEMR SQL.

Alternative considered: name this a SQLite-style `OpenEmrRepository`. Rejected because the architecture map classifies external OpenEMR transport under clients, and mixing it with local repositories would blur transaction, locking, and failure boundaries.

### Preserve compatibility through explicit delegation

Existing callers and tests may continue to call retained `DemoStore` lab/OIE methods. Each retained method will be a one-line or otherwise mechanically thin delegate to its owner. New services, runtime components, and composition wiring will use the repositories or OpenEMR client directly.

Architecture baseline entries corresponding to removed methods, SQL blocks, row mappers, and `OpenEMRProcedureOrderSource` will be deleted. No new or changed baseline entry is permitted solely to make the extraction pass.

Alternative considered: remove all compatibility methods immediately. Rejected because ZAC-57 explicitly requires API and caller compatibility and broader caller migration is outside this change.

### Characterize behavior before moving implementation

Focused tests will first capture current lab CRUD/health/history behavior, OIE success/error/duplicate/matching behavior, OpenEMR list/get/verify/missing-schema behavior, and compatibility-return shapes. Production implementation will then move in bounded increments, followed by port/composition cleanup and architecture-baseline reduction.

All SQLite tests will use `TemporaryDirectory` or equivalent disposable paths. OpenEMR tests will use connection/cursor doubles. No automated task may read or mutate `instance/*.db` or invoke live OIE, OpenEMR, Docker, deployment, push, merge, or release operations.

## Risks / Trade-offs

- [OIE result matching still queries patient/order tables] → Keep only the result transaction in the OIE repository, document its foreign-key/reference inputs, and leave broader inventory/workbench composition in services; stop if correct atomicity requires a broader patient/order extraction.
- [Compatibility delegates can hide continued service dependence on DemoStore] → Add architecture/service tests that require direct repository injection for extracted responsibilities.
- [Moving row projections can subtly change JSON shapes] → Move existing assertions before implementation and compare delegate and direct-repository results.
- [OpenEMR error handling depends on driver-specific exception shapes] → Preserve the current error-code/message classifier and test configured, unavailable-driver, connection-failure, missing-schema, and successful-query paths with doubles.
- [Multiple repositories could accidentally use different locks] → Assert identity with the `SQLiteDatabase.lock` used by `DemoStore` and every extracted SQLite repository.
- [Architecture cleanup could be bypassed by baseline churn] → Permit removal of extracted entries only; treat any required addition or changed exception as a stop condition for separate review.

## Migration Plan

1. Add focused characterization tests using disposable SQLite databases and OpenEMR connection doubles.
2. Introduce `LabRepository`, compose it from `SQLiteDatabase`, and replace lab SQL with `DemoStore` delegates.
3. Introduce `OieRepository`, move result persistence and projections, and update listener/service ports while retaining required cross-context coordination.
4. Move OpenEMR domain mapping and client/query ownership, then update application composition and imports.
5. Move remaining mixed assertions into responsibility-specific test packages and remove extracted architecture-baseline entries.
6. Run focused repository/client/domain/service tests, architecture tests, and the full suite.

Rollback is a normal Git revert of the focused extraction commits. No data rollback or schema downgrade is required because the database schema and persisted representations do not change.

## Open Questions

- Can OIE result matching remain transactionally equivalent when expressed through narrow patient/order lookup inputs, or should a small cross-context query port be retained temporarily? Resolve from characterization tests without broadening repository ownership.
- Does any runtime caller outside application composition import `OpenEMRProcedureOrderSource` directly from `lab_store.py`? If so, preserve only an explicit re-export long enough for compatibility and add a test that prevents new callers from using it.
