## Context

FHIR-mode ECG order creation currently persists a local order, builds and synchronizes a `ServiceRequest`, then builds and synchronizes a generated `Task` that points back to the order. The same pairing is embedded in supported-resource mappings, local order response composition, Medplum inventory grouping, preview/retry behavior, frontend acceptance logic, tests, and workflow documentation.

Healthcare Lab does not implement an independent owner, assignment, acceptance, or execution lifecycle for that Task. The generated resource therefore duplicates order state without supplying a real Task workflow. Existing installations may already contain Task ledger rows and synchronized Medplum Task resources, so retirement must not silently destroy historical data.

## Goals / Non-Goals

**Goals:**

- Make `ServiceRequest` the only FHIR order resource created by the Order page.
- Remove Task-specific supported-resource metadata, orchestration, response fields, frontend rendering, and acceptance criteria.
- Keep ServiceRequest failure, retry, preview, inventory, and patient-reference behavior intact.
- Align active specifications, tests, user guidance, and workflow diagrams with the ServiceRequest-only model.
- Preserve unrelated FHIR result resources and the existing generic ledger schema.

**Non-Goals:**

- No deletion of existing Task rows from SQLite or Task resources from Medplum.
- No migration or mutation of historical order payloads and sync-attempt records.
- No change to Patient, DiagnosticReport, Observation, DocumentReference, Binary, or Provenance workflows except removing Task as a declared dependency.
- No replacement worklist, assignment, or execution-state model.

## Decisions

### 1. Retire Task at every active support boundary

Remove Task from FHIR supported-resource constants, mapping metadata, identifier systems, dependency ordering, Medplum inventory/read allowlists, summaries, and patient grouping. Remove the Task resource builder and order-ledger creation method. The FHIR `/api/orders` path ends after the ServiceRequest synchronization attempt and returns the refreshed order.

Leaving Task in a generic allowlist while merely stopping automatic creation was considered, but would continue advertising Task as a supported Healthcare Lab workflow and leave preview/retry/UI paths inconsistent with the requested model.

### 2. Make ServiceRequest the sole FHIR order response and status signal

The local order response retains `fhir.serviceRequest` and removes `fhir.task`. Frontend FHIR order state is `Accepted` only when the ServiceRequest ledger is synced and has a valid `ServiceRequest/<id>` Medplum reference; otherwise it is `Error`.

Keeping a nullable `fhir.task` compatibility member was considered, but rejected because it preserves a misleading contract and forces frontend callers to continue understanding a retired resource.

### 3. Preserve historical Task data without exposing it as supported workflow

No database migration deletes rows, and no Medplum DELETE request is introduced. Existing Task ledger rows remain available for database-level audit and retain their sync attempts, but active resource lists, inventory, preview, retry, and order response composition exclude or reject Task records. Archived OpenSpec changes remain untouched as historical implementation records.

Purging local and remote resources was rejected because it is destructive, requires deployment-specific authorization and retention decisions, and is not required to stop the workflow.

### 4. Keep result-resource relationships ServiceRequest-based

DiagnosticReport and other result relationships continue to use Patient and ServiceRequest references. Task is removed only from declared Provenance dependencies and Task-specific patient reference handling; result synchronization order and live DiagnosticReport reads remain unchanged.

### 5. Update active documentation and derived diagrams together

Current README sections, Markdown workflows, diagram source SVGs, and their rendered PNG counterparts must show Patient/ServiceRequest order flow without Task. Historical artifacts under `openspec/changes/archive/` are not rewritten.

## Risks / Trade-offs

- **[Risk] External AP integrations may still query Medplum Task resources.** → Document the breaking workflow change and retain remote historical resources; integrations must move to ServiceRequest-based order discovery before deployment.
- **[Risk] Existing clients may expect `item.fhir.task`.** → Treat its removal as a breaking API change and update all repository-owned frontend code and tests atomically.
- **[Risk] Historical Task rows remain in SQLite even though Task is unsupported.** → Keep them for audit, exclude them from active APIs/UI, and scope any later retention cleanup as a separate destructive migration.
- **[Risk] Removing Task from shared mapping order can affect Provenance dependency assertions.** → Update mapping tests to verify the complete supported set and confirm result-resource dependency order remains valid.

## Migration Plan

1. Remove Task metadata, builders, orchestration, and order response composition from the backend.
2. Remove Task inventory, relationship rendering, labels, and acceptance checks from the frontend.
3. Update tests to assert one ServiceRequest write and no Task creation or exposure.
4. Update the active specification, README, workflow documents, SVGs, and rendered PNGs.
5. Run JavaScript syntax checks, Python tests, Task-reference scans over active sources, and strict OpenSpec validation.

Deployment requires no schema migration. Rollback is a normal code revert; existing historical Task rows and Medplum resources remain available because this change does not delete them.

## Open Questions

None. The exploration established ServiceRequest-only ordering and non-destructive historical-data retention as the proposal boundary.
