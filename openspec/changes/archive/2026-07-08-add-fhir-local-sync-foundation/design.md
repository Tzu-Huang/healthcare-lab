## Context

Healthcare Lab currently stores local Patient, HL7 Order, OIE Result, and GDT workflow data in SQLite through `backend/lab_store.py`. `app.py` already contains Medplum OAuth and FHIR request helpers, but Medplum writes are not backed by a durable local FHIR sync ledger. If a Medplum request fails or times out, the app cannot consistently show resource-level sync state or retry without risking duplicate resources.

The existing project boundary says Healthcare Lab owns the local interoperability lab control plane and dashboard-originated local workflows, while full AP result packaging belongs outside this project. This change therefore adds shared persistence and sync infrastructure only. Later workflow-specific tickets can use it for Patient, Order, AP, and Result flows.

## Goals / Non-Goals

**Goals:**

- Persist intended FHIR resources locally before any Medplum request is attempted.
- Track resource-level sync status, Medplum reference, request/response data, sync errors, and OperationOutcome details.
- Provide a common idempotent sync helper/API for supported FHIR resource types.
- Define mapping conventions for resources needed by later Patient, Order, AP, and Result workflows.

**Non-Goals:**

- Build the complete Patient, Order, AP, or Result UI workflow.
- Move ECG AP Simulator result packaging back into Healthcare Lab.
- Add production-grade background queue infrastructure beyond SQLite-backed local retry helpers.
- Guarantee full FHIR profile conformance for every future workflow payload.

## Decisions

1. Use a generic FHIR sync ledger instead of adding Medplum columns to each local workflow table.

   The ledger should store `local_source_type`, `local_source_id`, `resource_type`, deterministic identifier fields, resource JSON, Medplum id/reference, sync status, error text, OperationOutcome JSON, and timestamps. This avoids coupling Patient, Order, Result, and artifact workflows to separate one-off schemas.

2. Store sync attempts separately from the current resource record.

   A current-state table is useful for UI/API status, while an attempt table preserves HTTP status, request payload, response body, and failure detail for debugging. Keeping attempts separate prevents the latest status from losing prior failure context.

3. Use deterministic FHIR identifiers for idempotency.

   Each resource produced from local workflow data should include a stable `identifier` derived from local source type and id, for example `healthcare-lab.local/fhir/identifier/patient` + `local-patient-000001`. The sync helper should search by identifier before create, then update or record the found Medplum reference.

4. Sync resources in dependency order.

   Patient resources must sync before dependent `ServiceRequest`, `Task`, `Observation`, `DocumentReference`, `DiagnosticReport`, or `Provenance` resources that reference them. Binary artifacts may sync before `DocumentReference` resources that point to them. The helper should support single-resource sync and workflow-level ordered sync.

## Risks / Trade-offs

- [Risk] SQLite locking can leave a record stuck in `Syncing` after process interruption. -> Mitigation: store `sync_started_at` and allow retry to reclaim stale `Syncing` records.
- [Risk] FHIR search-by-identifier semantics differ across servers. -> Mitigation: keep Medplum-specific helper behavior isolated and record the actual request URL and response body for diagnosis.
- [Risk] Mapping definitions can grow into full workflow implementation. -> Mitigation: keep this ticket to mapping policy, ledger persistence, helper functions, and minimal status API.
- [Risk] OperationOutcome bodies can be large. -> Mitigation: store JSON as text in SQLite with tests around preservation, accepting demo-scale storage limits.

## Migration Plan

1. Add new SQLite tables with `CREATE TABLE IF NOT EXISTS` and additive migration helpers.
2. Add store methods for creating, listing, updating, and recording attempts for local FHIR workflow records.
3. Add sync helper functions around existing Medplum OAuth/request utilities.
4. Add focused tests for local persistence, idempotency search/create behavior, retry behavior, and OperationOutcome preservation.

Rollback is additive: existing Patient, Order, OIE, and GDT tables remain unchanged. If disabled, existing workflows continue without reading the new FHIR sync tables.

## Open Questions

- Should the first implementation expose sync status only through APIs, or also add a small UI status surface?
- Should `Task` be generated from the same local order source as `ServiceRequest`, or reserved for a later AP/device workflow ticket?
- Should failed sync records use `Sync failed` only, or distinguish validation failures from transient transport failures?
