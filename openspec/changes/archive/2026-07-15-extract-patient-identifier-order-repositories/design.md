## Context

`DemoStore` still owns patient validation, protocol payload builders, patient and order row projections, MRN sequence SQL, patient/order CRUD, protocol-specific order creation, and order send-result updates. Patient and order workflow services declare structural ports, but application composition satisfies those ports with the entire `DemoStore`, so the services can reach unrelated persistence and protocol behavior.

ZAC-55 established the bounded-context placement contract. ZAC-56 moved the SQLite path, connection lifecycle, shared reentrant write lock, migrations, and startup maintenance into `backend/repositories/database.py`. ZAC-57 established the extraction pattern used by lab and OIE repositories: repositories receive the shared connection factory and lock, new composition uses the owning repository directly, and retained `DemoStore` methods become compatibility delegates.

The current patient MRN allocator is deliberately application-transactional rather than schema-constrained. It advances `local_identifier_sequences`, skips candidates already present in `local_patient_records`, and inserts the patient while holding the shared lock and connection transaction. Existing databases may contain duplicate historical MRNs, so adding a uniqueness constraint is unsafe. Generic local order identifiers are derived from the inserted SQLite row ID and then finalized in the same transaction.

This change must allow unattended implementation while protecting stored data and observable protocol behavior. The implementation therefore distinguishes autonomous decisions from a small set of hard stop conditions.

## Goals / Non-Goals

**Goals:**

- Move all patient-record, MRN-sequence, generic order-record, and order send-result SQL to dedicated repository owners.
- Preserve the shared lock, transaction, SQLite row factory, connection, and error semantics established by the database owner.
- Preserve monotonic collision-skipping MRN allocation and row-ID-derived order identifier behavior.
- Separate patient/order validation and normalization into domain modules and protocol payload construction into template modules.
- Replace broad patient/order service dependencies on `DemoStore` with narrow, explicit ports.
- Preserve API shapes, status codes, protocol filters, projections, payload bytes/JSON meaning, and existing database compatibility.
- Retain thin `DemoStore` delegates only where existing callers still require them and shrink the reviewed architecture baseline.
- Give autonomous implementation freedom for internal structure, naming, helper extraction, fixtures, and directly caused fixes inside these boundaries.

**Non-Goals:**

- Change the SQLite schema, add uniqueness constraints, renumber records, or repair/delete historical data.
- Redesign MRN, visit, placer/filler, FHIR, GDT, or DICOM identifier semantics.
- Extract the complete FHIR, GDT, or dcm4chee bounded contexts and their ledgers.
- Change HTTP routes, request/response fields, frontend behavior, protocol filters, or external-service behavior.
- Introduce an ORM, connection pool, asynchronous database driver, new runtime dependency, or distributed lock.
- Read, copy, migrate, or modify a real `instance/*.db` during implementation or verification.

## Decisions

### Compose repositories from the shared SQLite owner

`DemoStore.__init__` will construct dedicated patient, identifier, and order persistence collaborators from `self.database.connect` and `self.database.lock`, following the existing lab/OIE repository pattern. New application composition and services use the owning collaborators directly. A repository must not accept or import `DemoStore`.

The patient repository owns SQL for `local_patient_records`; the identifier repository/allocator owns SQL for `local_identifier_sequences`; and the order repository owns common SQL for `local_order_records`, including list/get, creation/finalization primitives, protocol filtering, and send-result updates. Row-to-core-projection mapping remains beside the repository SQL, while cross-context enrichment is coordinated through explicit collaborators rather than hidden `DemoStore` access.

Alternative considered: give each repository its own SQLite owner or lock. Rejected because independent locks would weaken the current application concurrency boundary.

### Keep identifier allocation inside the patient write transaction

The identifier allocator will operate on the connection supplied by the patient repository's active write transaction. It will not open its own connection, commit independently, or acquire a separate lock. Automatic allocation, collision checks, and patient insertion therefore remain one atomic application operation.

Explicit MRNs remain trimmed and do not consume the automatic sequence. Automatic candidates retain `MRN-` plus a minimum of six decimal digits, skip manually occupied candidates, and never decrement or reuse values after restart or deletion. No database unique constraint will be added because legacy databases may already contain duplicates.

Alternative considered: expose `allocate_mrn()` as a standalone transaction that returns a reserved string. Rejected because a later patient insert could fail or race after consuming an identifier outside the current atomic boundary.

### Preserve order identifiers instead of introducing a new sequence

Generic order creation will continue inserting the row, deriving local/placer order identifiers and fallback visit/account identifiers from the new row ID, generating the required payload through an injected template collaborator, and finalizing the row within one repository-controlled transaction. This keeps allocation collision-safe without adding schema or changing externally visible identifiers.

Alternative considered: move orders onto `local_identifier_sequences`. Rejected because it changes established identifier behavior and is unnecessary for this extraction.

### Separate validation and templates without splitting atomic writes

Pure patient and order validation, normalization, and identifier-format helpers will move to `backend/domain/patient.py` and `backend/domain/order.py`. Protocol payload construction will move to the named modules under `backend/templates/`. Repositories may invoke injected pure validators, projectors, or payload factories while controlling a transaction, but repository modules will not implement protocol payload rules.

This permits payload generation that needs an assigned record ID while keeping insert and finalization atomic. Internal callable signatures and helper grouping are autonomous implementation choices as long as domain/templates remain independent of Flask and SQLite and repositories remain independent of HTTP construction.

Alternative considered: have the service perform insert, build, and final update as three public operations. Rejected because it exposes partial rows and weakens failure rollback semantics.

### Define narrow core and protocol coordination ports

Patient and order workflow services will no longer receive `DemoStore`. Their ports will be split or composed so each service receives only the patient/order ledger operations and explicitly required FHIR or dcm4chee coordination operations. Cross-context coordination remains in services or named adapters assembled in `backend/app_factory.py`; a patient/order repository must not absorb FHIR workflow, GDT workflow, or dcm4chee ledger ownership.

It is acceptable to introduce small composition adapters or additional constructor ports when that avoids broad facade access. It is not acceptable to wrap `DemoStore` in a nominally narrow object that simply forwards arbitrary attributes.

Alternative considered: retain the existing broad protocol and keep passing `DemoStore` because Python structural typing hides the extra methods. Rejected because it does not satisfy the issue's dependency boundary.

### Preserve compatibility through mechanical delegation

Existing callers may continue using enumerated patient/order methods on `DemoStore`. Each retained compatibility method will delegate mechanically to the new owner or an explicitly composed coordinator and contain no SQL, validation, payload, or workflow implementation. New callers import or receive the owning collaborator directly.

Extracted patient/order SQL, validation, and payload baseline entries will be removed from `tests/architecture_legacy_baseline.py`. No entry may be added or refreshed merely to make the extraction pass.

Alternative considered: remove every compatibility method in the same change. Rejected because callers outside the newly composed services may still rely on the facade and public compatibility is an acceptance criterion.

### Characterize first and verify only against disposable resources

Before moving implementation, focused characterization tests will pin current MRN allocation, explicit/duplicate behavior, restart/deletion behavior, order identifier derivation, rollback behavior, protocol filtering, row projections, send-result timestamps/errors, and representative payload output. Tests will use temporary SQLite databases and external-service doubles only.

Implementation verification includes focused domain/repository/service tests, database/repository regression tests, integration/API tests, architecture contract checks, compilation, and strict OpenSpec validation. A changed payload must be explained by a pre-existing nondeterministic field and normalized in the characterization test; otherwise it is a regression.

### YOLO autonomy and hard-stop policy

Within this design, autonomous implementation may choose internal names, helper boundaries, callable injection style, fixture organization, commit granularity within the ordered task gates, and directly necessary import/type/composition fixes. It may repair tests, circular imports, typing problems, and architecture diagnostics caused by the extraction without requesting approval, provided observable behavior and scope remain unchanged.

Implementation must stop and report instead of improvising only when one of these conditions is proven:

- preserving MRN/order collision safety conflicts with the repository boundary;
- completion requires destructive SQL, application-row deletion, table rebuilding, a new uniqueness constraint, or modification of a real `instance/*.db`;
- characterization demonstrates that an acceptance criterion conflicts with current supported behavior;
- completion requires changing a public API shape, status code, protocol filter, identifier semantic, or deterministic payload content;
- architecture checks can pass only by adding or refreshing a legacy baseline exception;
- completion requires absorbing the complete FHIR, GDT, or dcm4chee bounded context, adding a runtime dependency, or contacting a live external service.

Ordinary failed tests, import cycles, typing issues, internal design choices, fixture changes, or composition rewiring are not stop conditions and must be resolved autonomously.

## Risks / Trade-offs

- [The allocator accidentally commits separately from patient creation] -> Require connection-bound allocation and rollback characterization tests that inspect both the patient row and sequence behavior.
- [Payload extraction changes exact protocol output] -> Capture representative payloads before movement and compare deterministic content after extraction.
- [Core repositories absorb cross-context FHIR/dcm4chee behavior] -> Keep explicit service ports and repository ownership tests; allow only injected pure projection/payload collaborators.
- [A compatibility delegate grows into a second implementation] -> Enforce mechanical delegation and remove, rather than refresh, corresponding architecture baseline entries.
- [Legacy duplicate MRNs make database uniqueness attractive] -> Preserve application-level locking/checks and explicitly prohibit a new uniqueness constraint in this change.
- [Order creation becomes partially committed] -> Keep insert, row-ID allocation, payload generation, and finalization inside one repository-controlled transaction and test injected builder failure.
- [Narrow ports multiply composition parameters] -> Prefer cohesive context-specific ports or small named adapters, accepting modest wiring verbosity over general facade coupling.
- [YOLO stops for routine implementation friction] -> Limit stop conditions to proven data, compatibility, architecture-exception, dependency, or scope conflicts.

## Migration Plan

1. Add characterization tests for patient/MRN/order behavior, transaction rollback, projections, filters, payloads, and send-result updates using temporary databases.
2. Extract pure patient/order validation, normalization, identifier formatting, row projection helpers, and protocol payload builders with behavior held by characterization tests.
3. Introduce the connection-bound identifier allocator and focused collision/restart/rollback tests.
4. Introduce the patient repository, wire it to the shared database owner, and convert retained patient methods to delegates.
5. Introduce the order repository, preserve row-ID-derived identifiers and atomic payload finalization, and convert retained order/send-result methods to delegates.
6. Split patient/order service ports and update `app_factory.py` to compose owning collaborators directly, using explicit protocol coordinators where required.
7. Remove only the extracted architecture baseline entries and run focused, full, compile, architecture, and strict OpenSpec verification.

Deployment requires no schema command or data migration. Existing databases retain their rows, sequences, and identifiers.

Rollback is a code rollback. Because this change adds no schema or data migration, the prior code can continue using the same database. Generated records created while the new code ran retain the same existing formats.

## Open Questions

None. Internal structure is intentionally delegated to autonomous implementation; encountering a hard-stop condition requires a reviewed follow-up decision rather than expanding scope.
