## 1. Safety Baseline and Characterization

- [x] 1.1 Record the starting branch, clean/known worktree state, exact in-scope files, existing architecture-baseline entries, and disposable test-resource strategy before product-code edits.
- [x] 1.2 Add or strengthen focused FHIR characterization for ledger upsert/idempotency, changed-payload requeueing, dependency ordering, state transitions, sync attempts, OperationOutcome details, Medplum references, and projection ordering.
- [x] 1.3 Add or strengthen FHIR-mode order characterization for synced-Patient requirements, deterministic ServiceRequest content, local-order ownership, ledger creation sequence, and sync-failure preservation.
- [x] 1.4 Add or strengthen focused GDT characterization for patient-number snapshots, order/message/event creation, exact result matching precedence, unmatched results, attachments, event isolation, and workbench projections.
- [x] 1.5 Add rollback characterization proving injected FHIR/GDT collaborator failures and GDT multi-table result failures expose no partial ledger state.
- [x] 1.6 Verify all characterization uses temporary SQLite databases and external-service doubles, and add a failing guard where needed to prevent resolution to `instance/*.db`, Docker, or live healthcare endpoints.

## 2. Pure FHIR and GDT Collaborators

- [x] 2.1 Move or reuse FHIR validation, identifier/resource mapping, JSON normalization, and row-independent projection rules in framework-independent domain modules with representative tests.
- [x] 2.2 Move deterministic FHIR Patient/ServiceRequest ledger payload construction to template collaborators without changing serialized resource content or identifiers.
- [x] 2.3 Consolidate GDT validation, 6302 construction, 6310 parsing, attachment interpretation, rendering, and encoding behavior in adapters/templates with deterministic regression tests.
- [x] 2.4 Confirm pure FHIR/GDT collaborators import neither Flask nor SQLite and perform no Medplum transport, bridge filesystem mutation, or repository access.
- [x] 2.5 Run the nearest domain, template, and adapter tests and commit only the explicit collaborator/test paths after they pass.

## 3. FHIR Ledger Repository

- [x] 3.1 Introduce `FhirLedgerRepository` using the shared connection factory and application write lock, with no `DemoStore` dependency.
- [x] 3.2 Move workflow-record create/update/read/list, identifier lookup, dependency ordering, sync state transitions, and row projection into the FHIR ledger owner.
- [x] 3.3 Move sync-attempt create/list/projection and request/response/OperationOutcome audit persistence into the FHIR ledger owner.
- [x] 3.4 Move patient/order FHIR batch enrichment reads behind narrow FHIR ledger loaders and remove independent FHIR-table SQL from generic enrichment modules.
- [x] 3.5 Add direct repository tests for FHIR transactions, state transitions, attempts, enrichment batching, ordering, missing records, and compatibility projections.
- [x] 3.6 Run focused FHIR repository and characterization tests, inspect the diff for schema or behavior drift, and commit only the explicit FHIR repository/test paths after they pass.

## 4. FHIR Order Coordination and Service Ports

- [x] 4.1 Keep `local_order_records` SQL in `OrderRepository` while adding the narrow atomic primitive needed for compatible FHIR-mode order creation.
- [x] 4.2 Introduce a named FHIR order coordinator that combines synced-Patient lookup, order creation, pure ServiceRequest construction, and FHIR ledger creation without importing concrete unrelated repositories.
- [x] 4.3 Route Patient and Order workflow FHIR capabilities through explicit ports while preserving validation errors, local-first persistence, and failed-sync behavior.
- [x] 4.4 Compose `FhirWorkflowService` from `FhirLedgerRepository` and existing Medplum-facing collaborators instead of `DemoStore`.
- [x] 4.5 Add service/port/composition tests proving Medplum transport remains outside persistence and FHIR/order services cannot reach unrelated store capabilities.
- [x] 4.6 Run focused FHIR service, API, order, and integration tests with service doubles, inspect for public-contract drift, and commit only the explicit coordination/composition/test paths after they pass.

## 5. GDT Workflow Repository

- [x] 5.1 Introduce `GdtWorkflowRepository` using the shared connection factory and application write lock, with no `DemoStore` dependency.
- [x] 5.2 Move GDT patient-context, order, message, attachment, and workflow-event SQL plus row projections into the cohesive repository owner.
- [x] 5.3 Move normalized-result matching, unmatched-result persistence, attachment/event recording, order updates, and stored-data workbench aggregation into repository-controlled transactions.
- [x] 5.4 Keep raw GDT parsing/rendering and 6302/6310 interpretation in adapter/template collaborators and pass only validated normalized data across the repository boundary.
- [x] 5.5 Keep bridge discovery, file claim/disposition, filesystem paths, and watcher lifecycle in service/runtime collaborators while narrowing the persistence port.
- [x] 5.6 Add direct repository tests for exact matching precedence, ambiguous/unmatched results, attachments, event scoping, workbench projection, missing records, and multi-table rollback.
- [x] 5.7 Run focused GDT repository, adapter, service, runtime, and integration tests using temporary paths, inspect for matching/filesystem behavior drift, and commit only the explicit GDT paths after they pass.

## 6. Compatibility Facade and Architecture Enforcement

- [x] 6.1 Convert retained FHIR/GDT `DemoStore` methods to enumerated mechanical delegates to repositories, pure collaborators, or named coordinators with no SQL, payload, parsing, transport, filesystem, or orchestration bodies.
- [x] 6.2 Update application composition so new FHIR/GDT callers use owning capabilities directly and no workflow service receives `DemoStore` or an arbitrary forwarding wrapper.
- [x] 6.3 Add architecture checks for FHIR/GDT table ownership, dependency direction, pure adapter/template boundaries, narrow service composition, and compatibility-only delegates.
- [x] 6.4 Remove only the legacy-baseline entries proven extracted; do not add or refresh fingerprints, allowlists, classifier exclusions, skipped checks, or replacement compatibility exceptions.
- [x] 6.5 Run architecture, service-port, compatibility-delegate, and compilation checks, inspect the baseline diff explicitly, and commit only the intended architecture/composition paths after they pass.

## 7. YOLO Hard Stops and Closure Verification

- [x] 7.1 Before each remaining fix, classify it as an in-scope routine repair or a hard stop; stop and report evidence if it requires schema/data mutation, real DB/live service access, public behavior change, baseline expansion, a new dependency, unrelated extraction, or unsafe dirty-worktree overlap.
- [x] 7.2 Run focused FHIR/GDT repository, domain/template/adapter, service, runtime, API/integration, database characterization, architecture, and compilation verification using disposable resources only.
- [x] 7.3 Run the full automated regression suite without skips or weakened assertions and record command, result, duration, and any directly caused remediation in the devlog.
- [x] 7.4 Run strict OpenSpec validation and verify every requirement scenario is covered by implementation or automated evidence.
- [x] 7.5 Audit the final diff and commit history for explicit-path staging, reviewable increments, preserved unrelated changes, and absence of schema/migration/index, dependency, secret, real-database, live-service, deployment, or unrelated-scope changes.
- [x] 7.6 Confirm FHIR state/order semantics, GDT matching/events/attachments, public APIs, deterministic payloads, stored rows, transaction/lock behavior, and runtime configuration remain compatible before routing to `/dev-test`.
