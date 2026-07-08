# Codex Review R2: add-dcm4chee-sync-retry-api

## Findings

### P1: Failed retries are treated as transport errors in the UI

[frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:2378)

`retryDcm4cheeOrder()` calls the generic `requestJson()` helper, but `requestJson()` throws whenever a JSON response has `success === false` ([frontend/static/app.js](C:/Personal_repo/Projects/healthcare-lab/frontend/static/app.js:127)). The new retry endpoint intentionally returns HTTP 200 with `success: false` when the retry ran but dcm4chee sync still failed ([app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:3204)), including the updated order, MWL state, and latest error metadata. Because the helper throws before `retryDcm4cheeOrder()` can read that payload, the UI falls into the catch block, shows a generic retry failure, and does not refresh the order list or selected-order attempt history. This breaks the ZAC-38 recovery/inspection path for the common case where dcm4chee is still down after pressing Retry.

Suggested direction: let this call accept unsuccessful business results, for example by using a local fetch wrapper that only throws on non-2xx transport errors, then render `result.item.dcm4chee.mwl` and refresh attempts even when `result.success` is false.

## Residual Risk

- Manual browser verification is still pending. The automated checks do not currently exercise the retry button’s failed-retry rendering path, which is where the finding above appears.

## Verification Reviewed

- `openspec validate add-dcm4chee-sync-retry-api --strict` -> passed
- `node --check frontend\static\app.js` -> passed
- `python -m unittest tests.test_app -k dcm4chee` -> 20 tests passed
- `python -m unittest tests.test_lab_store.HealthcareLabStoreTests.test_dcm4chee_mapping_backfills_from_existing_attempts` -> passed
