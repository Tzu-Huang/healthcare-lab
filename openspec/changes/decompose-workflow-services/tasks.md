## 1. Integration Gate and Responsibility Baseline

- [x] 1.1 Before product implementation, confirm ZAC-46 is merged, update this branch from `main`, and record the merged commit plus retained OIE management client/settings composition keys and callers.
- [x] 1.2 Inventory Lab, FHIR, Order/dcm4chee, Patient, and GDT service responsibilities, callers, collaborators, runtime callbacks, compatibility seams, and current focused-test coverage.
- [x] 1.3 Define the final focused service and coordinator ownership map, including concrete narrow port signatures and explicit reasons for any Patient or GDT responsibility that remains cohesive.
- [x] 1.4 Add characterization for application extension keys, Blueprint inputs, runtime startup order, callbacks, and ZAC-46 OIE wiring before changing composition.
- [ ] 1.5 Add architecture checks rejecting broad service ports, generic variadic or dynamic delegation, Flask/SQL/runtime implementation in services, and behavior-free forwarding wrappers without expanding baselines or allowlists.

## 2. Lab Control-Plane Use Cases

- [x] 2.1 Characterize existing Lab dashboard aggregation, health checks, service operations, smoke checks, resource/status snapshots, call ordering, partial failures, and persisted operation effects.
- [x] 2.2 Extract focused Lab dashboard and resource/status coordination with narrow repository, client, and callback ports.
- [x] 2.3 Extract focused Lab health and smoke-check coordination while keeping filesystem/runtime readiness and external transports in their approved owners.
- [x] 2.4 Extract focused Lab service-operation coordination and preserve operation targeting, bulk-failure behavior, history persistence, and returned projections.
- [x] 2.5 Rewire Lab APIs and application composition to the focused services, preserve compatibility callers, and add mirrored focused tests.

## 3. FHIR Use Cases

- [x] 3.1 Characterize FHIR sync, inventory/query, preview, DiagnosticReport, retry/status, patient/order enrichment, error mapping, and ledger transition behavior.
- [x] 3.2 Extract focused FHIR sync and retry/status coordination using explicit ledger, template, transport, and core-record capabilities.
- [x] 3.3 Extract focused FHIR inventory/query and preview coordination without moving transport, resource construction, or row presentation into services.
- [x] 3.4 Extract focused DiagnosticReport coordination and preserve order/result linking, refresh behavior, errors, and public projections.
- [x] 3.5 Rewire FHIR APIs, Patient/Order callers, and application composition to the focused services and add mirrored focused tests.

## 4. Order and dcm4chee Use Cases

- [x] 4.1 Characterize dcm4chee patient, MWL, verification, result-refresh, evidence, simulated-return, callback, retry, and partial-failure coordination used by Order workflows.
- [x] 4.2 Extract focused dcm4chee patient and MWL coordinators with explicit patient, order, ledger, template, and client capability ports.
- [x] 4.3 Extract focused order-verification and result-refresh coordinators while preserving status transitions, reconciliation, returned projections, and callback behavior.
- [x] 4.4 Extract focused evidence and simulated-return coordination without moving repository SQL, DICOM payload rules, or external transport ownership.
- [x] 4.5 Rewire Order APIs, cross-context callers, and application composition to the focused coordinators and add mirrored focused tests.

## 5. Patient and GDT Cohesion Review

- [x] 5.1 Characterize Patient creation, identifier, FHIR sync, dcm4chee sync, failure, and returned-projection coordination and extract only independently meaningful use cases from the approved owner map.
- [ ] 5.2 Rewire Patient APIs and composition to any focused Patient services with narrow ports, or record test-backed evidence for responsibilities retained as one cohesive service.
- [ ] 5.3 Characterize GDT outbound export, inbox import, demo result, workbench, bridge callback, file-disposition, ordering, and error behavior.
- [ ] 5.4 Extract only independently meaningful GDT application use cases while keeping bridge filesystem/watcher lifecycle in runtime and atomic GDT-table work in the repository.
- [ ] 5.5 Rewire GDT APIs/runtime callbacks and composition to any focused GDT services, or record test-backed evidence for responsibilities retained as cohesive.

## 6. Composition, Compatibility, and Architecture Closure

- [ ] 6.1 Compact `backend/app_factory.py` around explicit construction and registration while retaining ZAC-46 OIE management wiring, all extension keys, Blueprint inputs, patch seams, and startup order.
- [ ] 6.2 Replace remaining broad service collaborators with concrete consumer-owned Protocols or typed callables and verify signatures contain no generic variadics, dynamic delegation, or bare `Any` returns.
- [ ] 6.3 Update `docs/architecture.md` with final service/use-case owners, cross-context coordinators, composition destinations, and deferred ZAC-63 through ZAC-65 responsibilities.
- [ ] 6.4 Shrink applicable workflow legacy baselines and document retained compatibility callers without adding replacement exceptions or removing facades owned by ZAC-65.

## 7. Verification and Safety Audit

- [ ] 7.1 Run focused service, API, runtime, composition, repository-wiring, mapper/template boundary, and architecture tests after each context migration using disposable databases and external-service doubles only.
- [ ] 7.2 Audit routes, HTTP methods, request/response shapes, errors, persistence ordering and transactions, callbacks, extension keys, runtime startup/shutdown, and external-integration behavior for compatibility.
- [ ] 7.3 Run the complete unittest suite, Python compilation, frontend syntax checks if touched, `git diff --check`, and strict OpenSpec validation.
- [ ] 7.4 Confirm ZAC-46 client/settings and ZAC-47 channel domain/template ownership were not changed, and no frontend modularization, broad test-file cleanup, `DemoStore` removal, schema/data mutation, live-service operation, dependency installation, destructive action, baseline expansion, or test weakening occurred.
