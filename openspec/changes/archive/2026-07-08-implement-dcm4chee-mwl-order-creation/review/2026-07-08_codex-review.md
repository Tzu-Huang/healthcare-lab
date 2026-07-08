# Code Review: implement-dcm4chee-mwl-order-creation

## Findings

### P1 - Invalid profile can still bypass dcm4chee attempt recording

- File: `app.py:585`
- File: `backend/lab_store.py:1535`

`sync_order_to_dcm4chee_mwl()` validates the profile, but immediately builds the MWL payload before checking `diagnostics["valid"]`. Several invalid profile states therefore never reach the intended `profile_invalid` attempt path. For example, if `DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE` is empty, `validate_dcm4chee_profile()` marks the profile invalid, but `build_dcm4chee_mwl_payload()` raises `SimulatorValidationError("dcm4chee default Scheduled Station AE Title is required.")` first. In the `/api/orders mode=dicom` path, the local order has already been created, then the route returns `400` without a `local_dcm4chee_mwl_attempts` row. That violates the ZAC-36 contract that profile validation failures should be recorded as dcm4chee sync metadata and that failures should be visible separately from local order creation.

Fix by checking `diagnostics["valid"]` before calling payload builders that depend on profile fields, or by making the invalid-profile branch create an attempt with safe placeholder/generated identifiers without relying on invalid MWL fields. Add a regression test with a missing Scheduled Station AE Title or MWL AE title, not only an invalid DICOMweb URL.

## Open Questions

- The Docker runtime endpoint check was skipped because dcm4chee was not running locally. This remains a runtime verification gap, not a code-review finding.

## Verification Reviewed

- `python -m py_compile app.py backend\lab_store.py tests\test_app.py`: passed during `/dev-test`.
- `node --check frontend\static\app.js`: passed during `/dev-test`.
- `openspec validate implement-dcm4chee-mwl-order-creation --strict`: passed during `/dev-test`.
- `python -m unittest tests.test_app -v`: 83 tests passed during `/dev-test`.

## Verdict

Changes requested.
