## Why

Patient records, MRN allocation, generic order records, and send-result persistence still share `DemoStore` with protocol validation and payload generation. The shared SQLite infrastructure and the first bounded-context repositories now provide a stable foundation for extracting these core ledgers without changing public behavior.

## What Changes

- Add dedicated patient and order repositories that own their SQLite queries, row projections, and write coordination through the shared database owner.
- Extract transaction-safe patient MRN allocation behind a narrow identifier boundary while preserving monotonic, collision-skipping behavior.
- Separate patient/order validation and normalization from persistence, and keep protocol payload generation outside repository SQL.
- Compose patient and order workflows with narrow ports instead of the general `DemoStore` facade.
- Retain only explicit compatibility delegates on `DemoStore` for existing callers and reduce the reviewed architecture baseline as implementation moves out.
- Add focused characterization and repository/domain tests while preserving API shapes, protocol filters, payloads, identifier semantics, and existing database compatibility.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Require dedicated patient, identifier, and order persistence boundaries; narrow patient/order service ports; and compatibility-only `DemoStore` delegation.

## Impact

- Affected code: `backend/lab_store.py`, `backend/repositories/`, `backend/domain/`, patient/order services, and `backend/app_factory.py` composition.
- Affected tests: focused domain and repository tests, service port/composition tests, integration regression coverage, and the architecture legacy baseline.
- Public HTTP APIs, SQLite schema, stored data, protocol payloads, filters, and deployment configuration remain compatible.
- No new runtime dependency, ORM, connection pool, or live-service requirement is introduced.
