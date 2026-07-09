# Codex Review

## Findings

1. Medium - MWL patient precondition failures are reported as retryable MWL sync failures.

   In `sync_order_to_dcm4chee_mwl`, when Patient sync preflight fails the mapping and attempt are recorded with `status = DCM4CHEE_MWL_STATUS_PATIENT_MISSING` and `error_type = "patient_sync_failed"` before returning without POSTing MWL. That is the right persistence behavior, but `_dcm4chee_mwl_retryable` only treats `patient_missing` and `profile_invalid` as non-retryable. As a result, API/UI status views mark this state as `retryable: true`, so the order row can show a MWL retry action even though retrying MWL cannot succeed until the Patient ADT sync problem is resolved.

   References:
   - `app.py:966`
   - `app.py:989`
   - `backend/lab_store.py:68`
   - `backend/lab_store.py:5035`

   Suggested fix: include `patient_sync_failed` in `DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES`, or otherwise make `_dcm4chee_mwl_retryable` return `False` for `DCM4CHEE_MWL_STATUS_PATIENT_MISSING`. Add an assertion to the MWL precondition failure test that `mwl["retryable"]` is false.

## Residual Risk

Manual live dcm4chee Docker ADT/MWL end-to-end verification was not run in this review. The automated tests mock HL7 MLLP and DICOMweb calls.

## Checked

- Inspected `main...HEAD` diff and changed implementation files directly.
- Reviewed Patient sync persistence, HL7 ADT sync flow, MWL precondition handling, and the new app/store tests.
- `git diff --check main...HEAD` passed.
