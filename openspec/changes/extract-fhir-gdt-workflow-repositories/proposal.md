## Why

FHIR ledger persistence and the complete GDT workflow ledger remain concentrated in `DemoStore`, so services still receive a broad compatibility facade and ownership of protocol-specific SQL is difficult to discover or enforce. The shared SQLite, patient/order, and dcm4chee boundaries are now stable enough to extract these last large persistence contexts without changing supported workflow behavior.

## What Changes

- Add a dedicated FHIR ledger repository for workflow records, sync attempts, state transitions, projections, and patient/order enrichment reads.
- Add a cohesive GDT workflow repository for patient contexts, orders, messages, attachments, events, result matching, and workbench projections.
- Keep FHIR validation and resource construction in domain/template collaborators, Medplum transport in clients/services, and GDT parsing/rendering in adapters/templates.
- Coordinate FHIR-mode local order creation through the existing order owner and explicit FHIR capabilities instead of duplicating `local_order_records` ownership.
- Compose FHIR and GDT services from narrow repository and coordination capabilities; retain only mechanical `DemoStore` compatibility delegates.
- Remove extracted architecture-baseline entries without adding or refreshing replacement exceptions.
- Add YOLO-mode safety boundaries: autonomous work is limited to reversible internal refactoring on disposable databases and service doubles, with mandatory hard stops before schema/data mutation, real database access, live external-service access, public behavior changes, new dependencies, baseline expansion, or unrelated scope growth.
- Characterize protected behavior before movement and require focused verification after each bounded extraction increment, followed by architecture and full regression gates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Require dedicated FHIR ledger and GDT workflow persistence owners, narrow service capabilities, compatibility-only `DemoStore` delegation, and enforceable autonomous-refactor safety boundaries.

## Impact

- Affected code: `backend/lab_store.py`, `backend/repositories/`, FHIR/GDT domain and template collaborators, enrichment composition, workflow services, and `backend/app_factory.py`.
- Affected tests: FHIR/GDT characterization and repository tests, service-port and architecture-contract tests, disposable-database integration coverage, and the reviewed legacy baseline.
- Public HTTP APIs, frontend behavior, SQLite schema and stored rows, FHIR identifiers/state transitions/order behavior, GDT matching/events/attachments, and deployment configuration remain compatible.
- No ORM, runtime dependency, live healthcare-service interaction, or real `instance/*.db` access is introduced by this change.
