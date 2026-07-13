# Codex Review - Round 3

Date: 2026-07-13  
Branch: `feature/redesign-dcm4chee-patient-console`  
Base: `main`  
Range: `main...HEAD`  
Verdict: **Changes requested**

## Findings

### [P2] Do not publish an in-progress generation before its rows are protected

`refresh_patient_dcm4chee_results()` registers the new run before making any PACS request (`app.py:1136`), and both result read paths immediately treat the highest run ID as authoritative (`backend/lab_store.py:4123-4126` and `backend/lab_store.py:6781-6787`). At that point the generation has no result rows, so any concurrent patient read returns an empty result list for the duration of the upstream query. An unexpected exception after `begin_dcm4chee_result_refresh()` can leave that empty generation authoritative indefinitely.

The same lifecycle also remains unsafe for overlapping refreshes. Result and diagnostic records are still updated in place without checking refresh-run order (`backend/lab_store.py:3653` and `backend/lab_store.py:4019`). If G1 starts, G2 starts and writes, then the older G1 finishes last and upserts the same result key, G1 replaces the row's generation. The readers continue selecting G2, which now has no rows, and both direct listing and Patient aggregation return an empty array. This is reachable from the current UI because a Patient has multiple Refresh controls (`frontend/static/app.js:1475`, `frontend/static/app.js:1536`, and `frontend/static/app.js:1768`) while only the clicked button is disabled (`frontend/static/app.js:1927`).

A minimal store-level reproduction confirmed both failures: existing results disappeared immediately after beginning a new run, and `begin G1 -> begin G2 -> write G2 -> write G1` left both read paths empty. Keep the last completed generation visible while a run is in progress, and prevent an older run from overwriting rows owned by a newer run (for example, model run lifecycle/completion plus run ownership/versioning on result rows, or serialize refreshes per Patient with a durable rule). Add regressions for in-progress visibility, aborted runs, and the interleaved order above.

## Previous findings

- Round 1 artifact metadata preservation remains resolved.
- Round 2's sequential same-second ordering case is resolved by the refresh-run sequence and its direct/aggregated regression test.

## Verification and residual risk

- Reviewed `main...HEAD`, with focused inspection of commit `352e777`.
- Confirmed the new finding with store-level in-progress and interleaved-run reproductions.
- The committed suite passes 151 tests, but it does not exercise refresh lifecycle or overlapping requests.
- No additional blocking findings were identified in the patient layout, structured DICOM tables, artifact rendering, or responsive containment changes.
