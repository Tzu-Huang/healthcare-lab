# ZAC-62 Order and dcm4chee Workflow Characterization

The decomposition baseline preserves these independently testable use cases:

| Use case | Existing evidence | Locked behavior |
|---|---|---|
| Patient prerequisite and MWL create | DICOM patient/MWL create, missing-patient, profile/station failure cases in `tests/integration/test_app.py` | patient-first ordering, stable identifiers, attempt persistence, and retained Order rows |
| MWL retry/readback | successful reuse, failed retry, readback-only retry, empty readback, and attempt-history cases | no duplicate POST, stable mapping identity, newest-first attempts, and partial-failure state |
| MWL verification | matching, empty, mismatch, ambiguity, patient-missing, and profile-failure cases | query criteria, verification status, match payload, and error classification |
| Result refresh | reconciliation, diagnostics, generation ordering, completed snapshot publication, stale/duplicate cases | refresh-generation isolation, supersession, and only-completed visibility |
| Evidence and simulated return | E2E fixture/evidence and PDF/DICOM simulated-return sequence cases | explicit evidence aggregation, result visibility, artifact ordering, and callback behavior |
| Repository boundaries | `tests/repositories/test_dcm4chee_patient_sync.py`, `test_dcm4chee_mwl.py`, and `test_dcm4chee_results.py` | transaction and ledger ownership remain outside coordinators |

Focused checks use disposable SQLite databases and patched DICOMweb/MLLP
transports. No live dcm4chee service or repository `instance/*.db` is used.
