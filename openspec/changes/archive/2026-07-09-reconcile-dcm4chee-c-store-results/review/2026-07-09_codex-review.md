# Codex Review - ZAC-40 dcm4chee Result Reconciliation

## Findings

### P2 - Stale refresh diagnostics remain visible after later successful refresh

File: `app.py:1118`, `app.py:1187`, `backend/lab_store.py:3249`

`refresh_patient_dcm4chee_results()` records `no_result`, `query_failed`, and `duplicate` diagnostics as normal patient result rows, and returns all patient `dicomResults` after each refresh. There is no cleanup, superseded flag, or current-refresh filter for diagnostic rows. If an operator refreshes too early and gets `no_result`, then AP later C-STOREs a valid study and the operator refreshes again, the old `no_result` row remains under the patient beside the matched result. The same applies to transient `query_failed` diagnostics after a later successful query.

This makes the patient-level DICOM Results section report stale unresolved states even after the current refresh has succeeded, which undermines the debugging signal this feature is meant to provide. Consider expiring prior diagnostic-only rows for the same patient/profile at the start of a successful refresh, marking them superseded, or filtering current-state patient results to the latest refresh generation.

### P2 - Archive QIDO/WADO/STOW defaults ignore configured dcm4chee host

File: `app.py:329`

`dcm4chee_profile_from_config()` now defaults QIDO/WADO/STOW to a hard-coded `http://127.0.0.1:8082/.../{called_ae_title}/rs` URL whenever the specific `DCM4CHEE_QIDO_RS_URL`, `DCM4CHEE_WADO_RS_URL`, or `DCM4CHEE_STOW_RS_URL` variables are unset. That breaks non-local deployments that override `DCM4CHEE_DICOMWEB_BASE_URL` or `DCM4CHEE_WEB_UI_URL` but do not also provide all three archive URLs; result refresh silently points back to local dcm4chee.

The local default should still target archive AE `DCM4CHEE`, but the host/scheme should be derived from configured DICOMweb/Web UI values where possible, rather than hard-coding loopback. Otherwise AP result refresh fails outside the default Docker-local setup even though the profile appears valid.

## Residual Risk / Missing Manual Coverage

- Live dcm4chee/AP C-STORE behavior was not exercised in this review. Automated tests mock QIDO responses, so real dcm4chee query parameter behavior and viewer URL behavior still need environment validation.
- The current study query combines Study Instance UID, Accession Number, Patient ID, and Issuer in one QIDO request. This is acceptable only if AP truly preserves all of those identifiers; if AP changes Study UID while preserving Accession, the query may be too restrictive.

## Verification Reviewed

- `python -m unittest tests.test_app tests.test_lab_store` passed: 129 tests.
- `node --check frontend\static\app.js` passed.
- `openspec validate reconcile-dcm4chee-c-store-results --strict` passed.
