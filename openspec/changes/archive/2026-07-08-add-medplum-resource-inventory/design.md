## Context

Healthcare Lab's current FHIR foundation persists local workflow records, tracks sync state, retries idempotently, and records Medplum resource references. The Patient page can now create FHIR-mode Patients through that ledger and show row-level sync status.

The missing workflow is an inventory surface where users can inspect resources across the FHIR workflow, select a Patient, see directly related resources, inspect raw JSON, and retry local records that have not synced.

The current FHIR source-of-truth specification says synced clinical resources should be read from Medplum live APIs when available. Local ledger records remain the authority for workflow intent, retry status, audit, and diagnostics.

## Goals / Non-Goals

**Goals:**

- Enable a Medplum navigation view in Healthcare Lab.
- Show a read-only inventory for `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, and `DocumentReference`.
- Prefer Medplum live JSON for synced resources.
- Fall back to local submitted JSON when a synced resource cannot be fetched live, with clear UI labeling that the preview is not live data.
- Show local submitted JSON for `Pending sync` and `Sync failed` records because those resources may not exist in Medplum yet.
- Let users select a Patient and see resources with direct Patient references.
- Allow retry from the Medplum page for `Pending sync` and `Sync failed` local ledger records.

**Non-Goals:**

- Delete FHIR resources.
- Edit FHIR resources from the inventory page.
- Build a complex Medplum/local diff viewer.
- Implement indirect graph traversal beyond direct Patient references.
- Add full FHIR search/query builder support.
- Move AP simulator result packaging into Healthcare Lab.

## Decisions

1. The Medplum page uses a hybrid read model.

   For records with sync status `Synced` and a Medplum reference, the page should fetch and display Medplum live JSON. For records that are `Pending sync` or `Sync failed`, the page should display the local submitted JSON and present the resource as local workflow intent, not canonical Medplum clinical data.

2. Live fetch failures fall back to local JSON with explicit labeling.

   A synced local ledger row can have a stale or temporarily unreachable Medplum reference. The UI should show the Medplum fetch error and label the preview as local submitted JSON instead of hiding the row or pretending the fallback is live data.

3. Patient-centered filtering starts with direct references only.

   The first version should include resources whose relevant field directly references the selected `Patient/<id>`. Supported direct fields include `subject`, `patient`, and `for`, plus array/object variants where those fields contain a FHIR reference.

4. Retry is available for pending and failed local records.

   Although ZAC-27 calls out `Sync failed`, `Pending sync` records also represent unsynced workflow intent and can safely use the existing idempotent sync path. `Synced` rows do not show retry, and `Syncing` rows should not allow concurrent retry.

5. The page is read-only except retry.

   Retry is an operational action on the local workflow ledger. It should not expose delete, arbitrary update, or destructive Medplum actions.

## Risks / Trade-offs

- [Risk] Live Medplum reads can fail due to service, network, or auth state. -> Mitigation: surface the failure and fall back to local submitted JSON only when available.
- [Risk] Local fallback JSON may differ from Medplum's current state. -> Mitigation: label fallback data clearly and keep Medplum live JSON as the preferred preview for synced resources.
- [Risk] Direct Patient reference filtering may miss indirectly related resources. -> Mitigation: keep the first version understandable and expand relation traversal in a later ticket if needed.
- [Risk] Inventory reads could become chatty if every row fetches live JSON eagerly. -> Mitigation: fetch list metadata from the ledger first, then fetch live JSON for selected rows or bounded visible resources.

## Open Questions

- Should sync attempt history appear on the Medplum page in this first version, or remain available only through the existing API?
- Should the first implementation add one aggregate Medplum inventory endpoint, or keep the API thin and let the frontend compose existing ledger, sync, and live-fetch calls?
