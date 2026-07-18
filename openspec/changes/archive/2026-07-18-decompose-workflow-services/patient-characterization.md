# ZAC-62 Patient Workflow Characterization

The Patient decomposition must preserve these use-case contracts:

| Use case | Existing evidence | Locked behavior |
|---|---|---|
| Record creation and identifiers | Patient MRN allocation/duplicate cases plus `tests/repositories/test_patient_order_characterization.py` | normalization, blank-MRN allocation, rollback, sequence safety, protocol filtering, and projections |
| FHIR creation and retry | missing-base, successful Medplum sync, failed sync, and retry cases in `tests/integration/test_app.py` | local Patient survives external failure, ledger linkage, failure detail, retry status, and returned Patient view |
| DICOM patient sync | successful and failed patient-sync API cases plus `tests/repositories/test_dcm4chee_patient_sync.py` | Patient persists before transport, attempt/mapping status, error classification, and retryability |
| Result refresh | reconciliation, diagnostics, supersession, completed snapshots, and duplicate candidate cases | refresh generations, callback ordering, stale-row handling, and returned result projections |
| E2E fixture | dcm4chee fixture/evidence integration case | configured profile and UID root are passed to the explicit fixture capability |

`DcmResultRefreshService` already owns refresh invocation. Remaining extraction
will separate record creation/listing, Patient FHIR sync, and fixture coordination
without moving repository SQL, payload construction, or transport into services.
