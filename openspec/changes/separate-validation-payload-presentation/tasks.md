## 1. Safety Baseline and Placement Contract

- [x] 1.1 Record the ZAC-61 owner inventory for Patient, Order, FHIR, GDT, dcm4chee, Lab, OIE, and retained compatibility exports, including current callers and final module destinations.
- [ ] 1.2 Add focused characterization tests for existing validation errors, normalized values, deterministic payloads, row projections, and relevant rollback behavior before moving each implementation.
- [x] 1.3 Create the `backend/mappers/` package and mirrored `tests/mappers/` package with context-specific modules and persistence-neutral row protocols.
- [x] 1.4 Extend architecture dependency tests to recognize mappers, allow repositories to invoke them, and reject mapper dependencies on Flask, SQLite connection APIs, repositories, services, clients, runtime, or composition.
- [ ] 1.5 Add architecture checks that reject new validation, protocol-builder, or reusable row-presentation implementations in repositories while permitting SQL, transactions, infrastructure validation, and injected pure collaborator calls.
- [x] 1.6 Update `docs/architecture.md` to match the modules created by ZAC-58 through ZAC-60 and document mapper ownership, retained compatibility callers, and the approved GDT bridge health exception.
- [x] 1.7 Document the bounded YOLO-mode rules: routine directly caused fixes may proceed, quality gates remain mandatory, and protected boundaries require an immediate stop without weakening tests, allowlists, fingerprints, or compatibility expectations.

## 2. Patient, Order, and FHIR Pure Boundaries

- [x] 2.1 Move Patient row presentation from the domain module to the Patient mapper, inject or import the single owner from the repository and enrichment paths, and preserve exact projections and protocol filtering.
- [x] 2.2 Move Order row presentation from the domain module to the Order mapper, inject or import the single owner from the repository and enrichment paths, and preserve send-result and dcm4chee/FHIR enrichment shapes.
- [x] 2.3 Move FHIR workflow-record and sync-attempt presentation from the domain module to the FHIR mapper and preserve ledger, enrichment, and compatibility-call projections.
- [x] 2.4 Consolidate shared Patient/Order HL7 template primitives and constants under a single template owner without changing generated ADT, ORM, or DICOM ADT text.
- [x] 2.5 Add only targeted Patient, Order, and FHIR typed boundary models or protocols where reused collaborator shapes remain ambiguous, with tests proving runtime dictionaries and JSON contracts are unchanged.

## 3. GDT Domain, Template, Mapper, and Ledger Boundaries

- [x] 3.1 Characterize GDT `6302` text byte-for-byte, parsed/canonical results, validation notices, persistence candidates, patient snapshots, attachment metadata, workbench projections, and atomic result rollback.
- [x] 3.2 Move outbound GDT `6302` construction to `backend/templates/gdt.py` while keeping parsing, encoding validation, required-field rules, and inbound `6310` interpretation in the GDT domain owner.
- [ ] 3.3 Move GDT patient/order number rules and persistence preparation out of `GdtWorkflowRepository` into pure domain collaborators without changing collision, matching, or transaction behavior.
- [ ] 3.4 Move GDT patient snapshot, attachment filename/shape mapping, and order/message/attachment/event/workbench presentation into the GDT mapper.
- [ ] 3.5 Wire `GdtWorkflowRepository` to the pure template/domain/mapper collaborators while retaining cohesive five-table SQL ownership and atomic writes.
- [ ] 3.6 Convert retained `backend/gdt_adapter.py` and `DemoStore` GDT helpers to documented re-exports or mechanical delegates with no duplicate implementation.
- [ ] 3.7 Add targeted GDT typed boundary models only for reused normalized or persistence shapes not already covered by `GdtAdapterResult`.

## 4. dcm4chee Presentation and Protocol Ownership

- [ ] 4.1 Move dcm4chee patient-sync and attempt row projectors from the patient-sync repository to the DICOM mapper with exact JSON characterization.
- [ ] 4.2 Move dcm4chee MWL mapping and attempt row projectors from the MWL repository to the DICOM mapper with exact retry, verification, and enrichment characterization.
- [ ] 4.3 Move dcm4chee result and refresh-snapshot row projectors from the result repository to the DICOM mapper with exact reconciliation and generation characterization.
- [ ] 4.4 Consolidate duplicated DICOM constants, identifier mapping wrappers, and presentation helpers under their existing domain, template, or mapper owners without changing payloads or response interpretation.
- [ ] 4.5 Convert retained `DemoStore` dcm4chee projector and builder helpers to documented re-exports or mechanical delegates and shrink the legacy baseline without adding replacement exceptions.

## 5. Lab and OIE Consistency Cleanup

- [ ] 5.1 Move Lab server payload validation into the Lab domain owner and Lab server/operation row presentation into the Lab mapper while preserving validation errors and API projections.
- [ ] 5.2 Move OIE settings validation into the OIE domain owner and settings/result presentation into OIE mappers while preserving password handling, duplicate behavior, and public JSON.
- [ ] 5.3 Keep GDT bridge directory readiness validation in its approved health/infrastructure owner and add a focused architecture assertion preventing accidental reclassification.
- [ ] 5.4 Update Lab/OIE repository construction and compatibility delegates to invoke the new pure owners without changing locks, transactions, listener behavior, or workbench coordination.

## 6. Verification and Safety Audit

- [ ] 6.1 Run focused domain, template, mapper, repository, service wiring, compatibility, and architecture tests after each bounded-context migration using disposable SQLite databases and external-service doubles only.
- [ ] 6.2 Audit generated HL7, FHIR, GDT, and DICOM payloads and persisted JSON for byte-for-byte or deep-structure compatibility, explaining only pre-existing controlled nondeterminism.
- [ ] 6.3 Audit API projections, validation errors, ordering, defaults, transaction rollback, schema hashes, and the real `instance/*.db` metadata to prove no public, persistence, or data mutation occurred.
- [ ] 6.4 Confirm architecture legacy baselines and compatibility caller inventories only shrink, no allowlist/fingerprint is broadened, and every temporary export has an owner and retained-caller record.
- [ ] 6.5 Run the complete unittest suite, mapper and architecture contracts, Python compilation, frontend syntax checks if touched, `git diff --check`, and strict OpenSpec validation.
- [ ] 6.6 Record YOLO-mode safety evidence: no live services, deployment actions, destructive operations, dependencies, schema/data changes, unsafe dirty-worktree overlap, or unrelated ZAC-62 through ZAC-65 work occurred.
