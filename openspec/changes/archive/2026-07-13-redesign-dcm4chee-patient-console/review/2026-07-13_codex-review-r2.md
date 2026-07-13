# Codex Review - Round 2

Date: 2026-07-13  
Branch: `feature/redesign-dcm4chee-patient-console`  
Base: `main`  
Range: `main...HEAD`  
Verdict: **Changes requested**

## Findings

### [P2] A unique generation is not enough to identify the latest refresh

`dcm4chee_result_refresh_generation()` now makes each generation unique, but the read path does not order by that generation. `DemoStore.list_dcm4chee_results_for_patient()` and the patient-list aggregation still select the latest generation with `ORDER BY last_refreshed_at DESC, id DESC` (`backend/lab_store.py:4065-4068` and `backend/lab_store.py:6705-6724`), while `now_iso()` stores `last_refreshed_at` only to whole-second precision (`backend/lab_store.py:329-330`). Existing result/diagnostic rows are updated in place, so their IDs do not reflect refresh order.

Consequently, a newer refresh can still be hidden by a higher-ID row from an older generation when both writes occur in the same second. A minimal store-level reproduction using a frozen `now_iso()` wrote `G1 no_result`, `G2 query_failed`, then updated the existing `no_result` row to `G3`; `list_dcm4chee_results_for_patient()` returned only stale `G2 query_failed`. The same ordering feeds the patient console, so a successful latest refresh can continue showing a superseded status/result.

The changed helper at `app.py:1120-1122` therefore fixes generation collisions but not refresh ordering. Persist an authoritative refresh-run order (for example, an autoincrement refresh-run record/sequence) and select by it, or otherwise ensure the read path has a stable total order that represents refresh creation rather than result-row ID. Add a regression covering an update of a lower-ID existing row after a higher-ID stale row within the same timestamp, including both the direct result listing and patient-list aggregation.

## Previous finding

The round-1 artifact-metadata finding is resolved. The Study table now searches all records in the study for artifact metadata, renders artifact label/type/location columns, and passes the discovered artifact to result actions.

## Verification and residual risk

- Reviewed `main...HEAD` and the follow-up fixes `de0ab2f` and `53cc612`.
- Confirmed the refresh-order finding with a store-level frozen-clock reproduction.
- Existing tests cover generation uniqueness and `no_result -> matched`, but not the reverse/update-in-place ordering that exposes this defect.
- No additional blocking findings were identified in the patient-list layout, preview placement, sync-card containment, or structured DICOM result tables.
