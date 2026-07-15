## Why

`DemoStore` still owns lab control-plane SQL, OIE result persistence, and the OpenEMR procedure-order query even though the shared SQLite infrastructure and bounded-context placement contract are now established. Extracting these smaller boundaries provides the first repeatable repository-extraction pattern while keeping current APIs and legacy callers stable.

## What Changes

- Add a lab control-plane repository that owns lab server registry, health-state, and operation-history persistence through the shared SQLite connection factory and write lock.
- Add an OIE repository that owns result, error-result, duplicate-detection, and result-query persistence while retaining the existing OIE settings repository.
- Move OpenEMR MariaDB connection and procedure-order query ownership to a dedicated external adapter, with OpenEMR-to-GDT normalization kept framework-independent.
- Inject narrow repository and external-query ports into services and runtime components instead of passing the general-purpose `DemoStore` where the extracted boundary is sufficient.
- Retain explicit `DemoStore` compatibility delegates for existing callers without retaining the extracted SQL, mapping, or workflow implementation.
- Replace mixed `DemoStore` assertions with focused repository, client, domain, and service tests; shrink the reviewed architecture baseline for the extracted implementation.
- Preserve all existing URLs, payloads, status codes, persistence semantics, startup behavior, and supported legacy database data.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Require dedicated lab control-plane and OIE persistence owners, separate OpenEMR external-query ownership, narrow service ports, and compatibility-only `DemoStore` delegation for the extracted boundaries.

## Impact

- Primary code: `backend/lab_store.py`, new or expanded modules under `backend/repositories/`, `backend/clients/openemr.py`, `backend/domain/openemr.py`, `backend/app_factory.py`, and the affected lab/OIE services and runtime wiring.
- Tests: focused modules under `tests/repositories/`, `tests/clients/`, `tests/domain/`, and `tests/services/`, plus architecture-baseline updates that remove extracted entries.
- Data and APIs: no schema migration, destructive SQL, external API change, or new dependency is expected.
- Operations: automated verification must use disposable SQLite databases and test doubles for OpenEMR/OIE; repository `instance/*.db` files and live lab services remain out of scope.
