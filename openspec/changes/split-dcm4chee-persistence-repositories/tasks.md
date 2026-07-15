## 1. Characterize Protected Behavior and Safety Boundaries

- [x] 1.1 Add disposable-database characterization tests for patient-sync mappings, attempts, ACK/error projection, retry increments, and success/failure transitions.
- [ ] 1.2 Add characterization tests for MWL mapping creation, stable identifiers, attempts, readback-before-repost, verification outcomes, and retry classification.
- [ ] 1.3 Add characterization tests for reconciliation precedence, wrong-patient rejection, duplicate candidates, simulated results, and evidence projection.
- [ ] 1.4 Add characterization tests for result refresh generations, completed-snapshot publication, stale-result supersession, diagnostics, and run ordering.
- [ ] 1.5 Add disposable legacy-database characterization for deterministic MWL mapping backfill and attempt linking.
- [ ] 1.6 Prove the verification fixtures cannot resolve to or mutate a repository `instance/*.db` and use transport doubles instead of live external services.
- [ ] 1.7 Run the focused characterization suite; stop only if evidence proves a documented hard-stop conflict, otherwise resolve ordinary failures within scope.

## 2. Extract Pure DICOM Rules and Payload Collaborators

- [ ] 2.1 Move or consolidate Patient ADT and MWL payload construction in named template modules with representative deterministic payload tests.
- [ ] 2.2 Move or consolidate DICOM response parsing, dataset extraction, UID/identifier normalization, and verification-query rules in framework-independent modules.
- [ ] 2.3 Move or consolidate retry classification, status projection, reconciliation matching policy, and result-link/key rules outside repository modules.
- [ ] 2.4 Update callable injection and imports so pure modules remain independent of Flask and SQLite and repositories do not parse transport bodies or construct protocol payloads.

## 3. Extract Patient-Sync Repository

- [x] 3.1 Add `backend/repositories/dcm4chee_patient_sync.py` using the shared connection factory and lock.
- [x] 3.2 Move patient-sync mapping upsert/get/list SQL and row projection into the patient-sync repository.
- [x] 3.3 Move patient-sync attempt create/update/get/list SQL and mapping transition behavior into the patient-sync repository.
- [x] 3.4 Add focused repository tests for shared-lock use, transaction rollback, retry behavior, ACK/errors, not-found behavior, projections, and existing database compatibility.
- [x] 3.5 Convert retained patient-sync `DemoStore` methods to mechanical delegates with no SQL, payload, parsing, or workflow logic.

## 4. Extract MWL Repository and Backfill

- [ ] 4.1 Add `backend/repositories/dcm4chee_mwl.py` using the shared connection factory and lock.
- [ ] 4.2 Move MWL mapping upsert/update/get/reconciliation-lookup SQL and row projection into the MWL repository.
- [ ] 4.3 Move create, readback, profile-failure, and verification attempt SQL plus verification updates into the MWL repository.
- [ ] 4.4 Move deterministic historical MWL mapping backfill beside the MWL owner while retaining the supplied startup connection, initialization lock, ordering, and transaction.
- [ ] 4.5 Add focused repository and disposable legacy-database tests for stable identifiers, retries, readback, verification, lookups, backfill idempotence, and rollback.
- [ ] 4.6 Convert retained MWL `DemoStore` methods to mechanical delegates with no SQL, payload, parsing, or workflow logic.

## 5. Extract Result Repository and Enrichment Reads

- [ ] 5.1 Add `backend/repositories/dcm4chee_results.py` using the shared connection factory and lock and an explicit narrow MWL lookup collaborator.
- [ ] 5.2 Move result record upsert/get/list, result-key, reconciliation persistence, duplicate diagnostic, and row-projection behavior into the result repository or injected pure policy.
- [ ] 5.3 Move result refresh-run, generation comparison, begin/complete publication, diagnostic, and stale-result SQL into the result repository.
- [ ] 5.4 Remove direct dcm4chee SQL from patient/order enrichment loaders and route projections through explicitly injected patient-sync, MWL, and result loaders.
- [ ] 5.5 Add focused tests for reconciliation precedence, patient mismatch, duplicates, refresh atomicity, completed snapshots, generation ordering, diagnostics, enrichment, and rollback.
- [ ] 5.6 Convert retained result `DemoStore` methods to mechanical delegates with no SQL, parsing, or cross-context orchestration.

## 6. Narrow Ports and Cross-Context Coordination

- [ ] 6.1 Split patient workflow dependencies into explicit FHIR, dcm4chee patient-sync, result-refresh, and core patient capabilities.
- [ ] 6.2 Split order workflow dependencies into explicit FHIR, dcm4chee patient-sync precondition, MWL, result/evidence, and core order capabilities.
- [ ] 6.3 Move E2E fixture, evidence aggregation, simulated AP return, and other multi-ledger behavior into an explicit service or named coordinator.
- [ ] 6.4 Update `backend/app_factory.py` to compose repositories and coordinators directly without passing the general facade or using arbitrary attribute forwarding.
- [ ] 6.5 Update service and composition tests to prove declared ports are explicit, typed, capability-limited, and behavior-compatible.
- [ ] 6.6 Update the bounded-context placement map to name the three repositories and their mirrored test destinations.

## 7. Architecture Cleanup and YOLO-Safe Verification

- [ ] 7.1 Remove only architecture legacy-baseline entries corresponding to extracted dcm4chee SQL, projections, payloads, parsing, and workflow implementation; do not add or refresh exceptions.
- [ ] 7.2 Run focused domain, template, repository, service, database, migration/backfill, API, and integration tests using disposable resources and external-service doubles only.
- [ ] 7.3 Run Python compilation, architecture contract tests, the full automated regression suite, `git diff --check`, and strict OpenSpec validation.
- [ ] 7.4 Confirm the final diff contains no schema/index/data migration, real `instance/*.db` access, live-service call, new dependency, secret, public API change, deterministic payload change, or unrelated bounded-context extraction.
- [ ] 7.5 Keep implementation commits focused and reversible, stage only intended files, preserve unrelated worktree changes, and never bypass a failing verification gate.
- [ ] 7.6 If and only if a documented hard-stop condition is proven, stop with evidence; otherwise autonomously resolve ordinary test, typing, import, fixture, and composition failures and complete verification.
