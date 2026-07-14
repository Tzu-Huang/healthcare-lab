## 1. Backend Resource Support

- [x] 1.1 Remove Task constants, supported-resource mapping, identifier, dependency-order, Provenance dependency, Medplum inventory/read allowlist, and Task-specific summary behavior.
- [x] 1.2 Remove the generated ECG Task builder and order-to-Task workflow ledger creation function.
- [x] 1.3 Change FHIR Order creation to create and sync only ServiceRequest while preserving ServiceRequest failure and idempotent retry behavior.
- [x] 1.4 Remove Task lookup and `fhir.task` composition from local order API responses and exclude historical Task rows from active list, preview, retry, and sync contracts without deleting stored data.

## 2. Frontend ServiceRequest-Only Workflow

- [ ] 2.1 Group Patient FHIR Orders using ServiceRequest only and remove Task related-resource navigation, labels, prompts, and preview text.
- [ ] 2.2 Change Local Orders FHIR acceptance and error display to depend only on the ServiceRequest sync status and valid Medplum reference.
- [ ] 2.3 Remove remaining Task-facing DOM copy while preserving Patient, ServiceRequest, DiagnosticReport, Observation, DocumentReference, and Binary workflows.

## 3. Tests And Contracts

- [x] 3.1 Update store tests for the supported mapping set, ServiceRequest-only order ledger, response shape, and preserved result-resource dependency order.
- [x] 3.2 Update API tests to assert one ServiceRequest Medplum write, no generated Task request, ServiceRequest failure preservation, and rejection or exclusion of historical Task workflow operations.
- [ ] 3.3 Update frontend contract tests for ServiceRequest-only patient rollups, related resources, preview copy, and order acceptance logic.

## 4. Documentation And Diagrams

- [ ] 4.1 Update README and active workflow documentation to describe Patient/ServiceRequest order flow without Task.
- [ ] 4.2 Update affected SVG diagram sources and regenerate matching PNG assets without modifying archived OpenSpec history.

## 5. Verification

- [ ] 5.1 Run JavaScript syntax checks and the relevant Python unit-test suites.
- [ ] 5.2 Scan active backend, frontend, tests, README, docs, and current specs to confirm no Task workflow references remain outside explicitly documented historical-retention context.
- [ ] 5.3 Run `git diff --check` and strict OpenSpec validation for `remove-medplum-task-workflow`.
