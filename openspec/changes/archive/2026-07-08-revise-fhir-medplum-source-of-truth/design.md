## Context

The current FHIR foundation can persist local FHIR workflow records and sync attempts. That makes failure handling and retry possible, but the phrase "local-first" can be misread as Healthcare Lab owning a full copy of Patient, Order, and Result clinical data.

For the Medplum-backed workflow, the desired boundary is narrower:

- Medplum owns canonical FHIR resources and server-side query behavior.
- Healthcare Lab owns the lab workflow ledger, retry/audit metadata, demo presets, operation history, and UI projection state.
- Later FHIR pages should use live Medplum reads for resource inventory and worklist views, then enrich those resources with local sync/error state when a local ledger record exists.

## Goals / Non-Goals

**Goals:**

- Define Medplum as the FHIR source of truth.
- Preserve ZAC-25's local ledger for reliability, diagnostics, and idempotent retry.
- Define read/write patterns for Patient, Order, Task, Result, and Medplum inventory workflows.
- Provide a shared decision record for ZAC-26 through ZAC-32.

**Non-Goals:**

- Remove the existing FHIR ledger tables.
- Implement Patient, Order, Task, Result, or UI code in this change.
- Add a background sync worker.
- Guarantee full offline FHIR browsing when Medplum is unavailable.

## Decisions

1. Medplum is canonical for FHIR resources.

   Healthcare Lab should treat Medplum responses as authoritative after sync succeeds. Local records may retain the submitted intent and the returned Medplum id/reference, but they should not become the long-term clinical source of truth for resource inventory.

2. The local FHIR store is a ledger, not a shadow FHIR database.

   Local FHIR records should exist to answer operational questions: what did Healthcare Lab try to create or update, did it sync, what identifier was used, which Medplum resource did it resolve to, what failed, and can it be retried safely?

3. Reads default to Medplum live queries.

   Medplum/FHIR inventory and AP worklist views should read from Medplum APIs such as `Patient`, `ServiceRequest`, `Task`, and `DiagnosticReport` search. The UI can join matching local ledger rows by Medplum reference or deterministic identifier to show local sync status and retry/error details.

4. Writes keep local intent before or during Medplum submission.

   Create/update flows should preserve a local ledger record with deterministic identifiers and request payloads so failures are inspectable and retryable. Successful writes should reconcile the returned Medplum id/reference and, when useful, the canonical response payload.

5. Pending and failed local records remain visible.

   A resource that has not reached Medplum is not canonical clinical data, but it is still an important workflow intent. Patient/Order/Result pages should show these as local pending/failed items with clear sync state rather than silently hiding or treating them as canonical Medplum resources.

## Read Patterns

- Patient inventory: query Medplum `Patient`, then join local ledger rows by `Patient/<id>` or deterministic identifier.
- Order view: query Medplum `ServiceRequest` and related `Task`, then join local order intent and sync attempt metadata.
- AP worklist: query Medplum `Task?status=requested` or the agreed worklist criteria, include/resolve `Task.focus` and patient context, and record AP pull/update audit locally.
- Result view: query Medplum `DiagnosticReport`, `Observation`, `DocumentReference`, and `Binary` references; use local ledger rows for retry/error and demo provenance.

## Write Patterns

- Patient create: store local intent, create or conditionally create Medplum `Patient`, then record Medplum id/reference and canonical response details.
- Order create: store local order intent, submit `ServiceRequest` and `Task` through a transaction Bundle or equivalent idempotent strategy, then record all Medplum references.
- Task update: send status changes to Medplum and record AP/workflow audit locally.
- Result return: store result intent and artifacts, submit `Binary`, `Observation`, `DocumentReference`, `DiagnosticReport`, and `Provenance` through transaction/idempotent writes, then record Medplum references and failures.

## Follow-up Ticket Alignment

- ZAC-26 Patient creation should create a local ledger intent, write the `Patient` to Medplum, store the returned `Patient/<id>` reference, and keep failed creates retryable without treating unsynced local data as canonical.
- ZAC-27 Medplum resource inventory should query Medplum live resources first and join local ledger metadata for sync status, retry actions, and OperationOutcome details.
- ZAC-28 FHIR order creation should submit `ServiceRequest` and `Task` to Medplum through a transaction Bundle or equivalent idempotent flow, while storing only local order intent and Medplum references in Healthcare Lab.
- ZAC-29 AP worklist should pull requested `Task` resources and referenced `ServiceRequest`/`Patient` context from Medplum, while recording AP pull and Task update audit locally.
- ZAC-30 result return should preserve local result/artifact intent for retry, but synced `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance` reads should come from Medplum.
- ZAC-31 patient-centered FHIR panels should render Medplum-sourced resource relationships and enrich them with local ledger status rather than building the page from only local FHIR rows.
- ZAC-32 E2E tests should verify both live/query behavior and ledger behavior: successful Medplum-backed workflows, failure preservation, retry, idempotency, and OperationOutcome display.

## Risks / Trade-offs

- [Risk] Live Medplum reads make UI dependent on Medplum availability. -> Mitigation: show pending/failed local ledger records separately and keep clear degraded-state messaging.
- [Risk] Joining live resources with local ledger metadata can be ambiguous if identifiers are missing. -> Mitigation: continue requiring deterministic identifiers and storing Medplum references after sync.
- [Risk] Transaction Bundle behavior can differ by server configuration. -> Mitigation: keep Medplum-specific request/response details in sync attempts and allow workflow tickets to choose transaction or ordered individual requests where needed.
- [Risk] Users may expect pending local records to appear in Medplum inventory. -> Mitigation: label pending/failed local intents distinctly from Medplum-sourced resources.

## Open Questions

- Should Medplum inventory pages show cached last-seen Medplum payloads when live query fails, or only show local pending/failed intents?
- Should local ledger records store the canonical Medplum response payload after success, or only the id/reference plus request/response attempt history?
- Should ZAC-27 introduce a shared join API for Medplum live resources plus local ledger metadata, or should frontend panels perform separate calls?
