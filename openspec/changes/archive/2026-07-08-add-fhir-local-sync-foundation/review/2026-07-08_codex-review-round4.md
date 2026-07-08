## Findings

### P2 - Changed synced resources can be marked `Synced` without updating Medplum

[backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:2929) correctly moves an already-synced local FHIR record back to `Pending sync` when the stored resource JSON changes, while preserving the existing Medplum id/reference. However, the sync path now treats any stored Medplum id as success after an identifier-search miss at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:532), returning through `mark_fhir_sync_success()` at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:535) without issuing a `PUT`, `PATCH`, or any other request that sends the changed payload to Medplum.

That means a workflow can update a synced local resource, see it become `Pending sync`, call `/api/fhir/records/<id>/sync`, and get `Synced` even though Medplum still has the old representation. This regresses the sync-status contract and makes the local ledger report false success. The duplicate-create guard should distinguish unchanged retries from changed pending records, or implement an update/upsert path when `medplum.id` is present.

Add a regression test that starts with a synced record, changes its payload, then syncs with identifier search returning empty and asserts the changed payload is not marked `Synced` unless an update request is made.

## Open Questions

- Is update/upsert in scope for this foundation ticket, or should changed records with an existing Medplum id remain `Pending sync`/`Sync failed` until a later update feature is implemented?

## Test Coverage Reviewed

- Latest `/dev-test` result: `python -m unittest discover -s tests` passed 85 tests.
- Latest `/dev-test` result: `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py` passed.
- Latest `/dev-test` result: `node --check frontend\static\app.js` passed.
- Latest `/dev-test` result: `openspec validate --changes add-fhir-local-sync-foundation` passed.

Residual gap: tests cover first create, retry without duplicate create, and store-level changed-payload status reset, but not the API sync behavior for changed records that already have a Medplum id.
