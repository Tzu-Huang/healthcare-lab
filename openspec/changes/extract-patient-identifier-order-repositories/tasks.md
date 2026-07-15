## 1. Characterize Existing Contracts

- [x] 1.1 Add disposable-database characterization coverage for automatic and explicit MRNs, collision skipping, restart/deletion monotonicity, duplicate rejection, and rollback behavior without touching `instance/*.db`.
- [x] 1.2 Add characterization coverage for patient and order protocol filters, row projections, not-found errors, deterministic payload content, and API-compatible response shapes.
- [x] 1.3 Add characterization coverage for row-ID-derived order identifiers, atomic create/finalize rollback, and send-result ACK, transport-error, and timestamp updates.
- [x] 1.4 Run the focused characterization suite and record any conflict with the proposal's protected behavior as a hard stop; treat ordinary fixture or test failures as implementation work.

## 2. Extract Pure Patient and Order Logic

- [ ] 2.1 Create `backend/domain/patient.py` and move patient validation, normalization, identifier formatting, and framework-independent projection rules with focused domain tests.
- [ ] 2.2 Create `backend/domain/order.py` and move generic order validation, normalization, identifier formatting, and framework-independent projection rules with focused domain tests.
- [ ] 2.3 Move Patient HL7, FHIR, GDT, and DICOM payload generation to named `backend/templates/` modules with representative payload tests.
- [ ] 2.4 Move generic Order HL7 and any in-scope payload generation to named `backend/templates/` modules while leaving complete FHIR, GDT, and dcm4chee ledger extraction out of scope.
- [ ] 2.5 Update internal imports and callable injection seams so domain/templates remain independent of Flask and SQLite, resolving routine typing or import-cycle issues autonomously.

## 3. Extract Transaction-Safe Identifier Allocation

- [ ] 3.1 Add a dedicated identifier persistence collaborator that uses a caller-supplied active SQLite connection and owns `local_identifier_sequences` SQL without importing or opening `DemoStore`.
- [ ] 3.2 Preserve blank-MRN allocation, explicit-MRN behavior, monotonic advancement, occupied-candidate skipping, formatting, and application-level duplicate rejection without adding a uniqueness constraint.
- [ ] 3.3 Prove allocation, collision checking, Patient insertion, and failure rollback share the Patient repository lock and transaction using disposable database tests.

## 4. Extract Patient Repository

- [ ] 4.1 Add `backend/repositories/patients.py` using the shared connection factory and lock, owning patient create/list/get SQL and protocol filtering.
- [ ] 4.2 Integrate the transaction-bound identifier collaborator and injected validation/payload collaborators so Patient insertion and payload finalization remain atomic.
- [ ] 4.3 Preserve patient row projections and required FHIR/dcm4chee enrichment through explicit narrow collaborators without moving those complete bounded-context ledgers into the repository.
- [ ] 4.4 Add focused repository tests for writes, reads, filters, errors, transaction rollback, shared-lock use, and existing database compatibility.
- [ ] 4.5 Convert retained Patient `DemoStore` methods to mechanical delegates with no patient SQL, validation, payload, or workflow implementation.

## 5. Extract Order Repository

- [ ] 5.1 Add `backend/repositories/orders.py` using the shared connection factory and lock, owning generic order create/finalize, list/get, protocol-filter, and send-result SQL.
- [ ] 5.2 Preserve row-ID-derived local/placer order numbers, Patient snapshot fields, fallback visit/account identifiers, and atomic payload finalization without introducing a new sequence or schema change.
- [ ] 5.3 Preserve order row projections and required FHIR/dcm4chee enrichment through explicit narrow collaborators without moving those complete bounded-context ledgers into the repository.
- [ ] 5.4 Add focused repository tests for generic writes, reads, filters, errors, injected payload failure rollback, shared-lock use, and send-result updates.
- [ ] 5.5 Convert retained Order `DemoStore` methods to mechanical delegates with no generic order SQL, validation, payload, or workflow implementation.

## 6. Narrow Service Ports and Composition

- [ ] 6.1 Split Patient workflow dependencies into a narrow patient ledger port and explicit FHIR/dcm4chee coordination ports, preserving service behavior and tests.
- [ ] 6.2 Split Order workflow dependencies into a narrow order ledger port and explicit FHIR/dcm4chee coordination ports, preserving service behavior and tests.
- [ ] 6.3 Update `backend/app_factory.py` to compose the repositories and explicit coordinators directly instead of passing `DemoStore` to Patient or Order workflow services.
- [ ] 6.4 Update OIE inventory and other retained cross-context callers to use narrow Patient/Order collaborators or documented compatibility delegates without broadening OIE repository ownership.
- [ ] 6.5 Add composition and port tests proving Patient/Order services do not receive or rely on the general facade.

## 7. Architecture Cleanup and Verification

- [ ] 7.1 Remove architecture legacy-baseline entries corresponding to extracted patient, identifier, generic order, validation, and payload implementation; do not add or refresh replacement exceptions.
- [ ] 7.2 Run focused domain, template, repository, service, database, API, and integration tests using only disposable databases and external-service doubles.
- [ ] 7.3 Run the full automated regression suite, Python compilation checks, frontend syntax checks if affected, architecture contract tests, and strict OpenSpec validation.
- [ ] 7.4 Confirm the final diff contains no schema/data migration, new runtime dependency, API or deterministic payload change, real `instance/*.db` access, or complete FHIR/GDT/dcm4chee extraction.
- [ ] 7.5 If and only if a documented hard-stop condition is proven, stop with evidence; otherwise autonomously resolve ordinary failures and complete all verification.
