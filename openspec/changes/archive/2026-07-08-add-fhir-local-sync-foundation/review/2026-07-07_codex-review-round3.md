## Findings

### P2 - Retrying an already-created FHIR record can create a duplicate Medplum resource

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:511) always starts sync by searching Medplum by identifier, and [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:532) falls through to `POST` create whenever that search returns no Bundle entry. It does not check the local record's existing `medplum.id`/`medplum.reference` before creating.

That violates the OpenSpec idempotency scenario that after a missing resource is created, a later retry with the same deterministic identifier does not create another copy. A record marked `Synced` by [backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:3084) already retains the Medplum resource id, but a later `/api/fhir/records/<id>/sync` can still duplicate the resource if identifier search is empty because of indexing lag, server search behavior, or a mocked retry path. The same risk applies after `create_fhir_workflow_record()` marks a changed synced payload back to `Pending sync` while preserving the old Medplum reference at [backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:2929).

Use the stored Medplum reference/id as an idempotency guard before issuing a create, or implement update/upsert behavior when a local record already has a Medplum id. Add a regression test that syncs once via POST, then retries with identifier search returning empty again and asserts no second POST occurs.

## Open Questions

- For changed local payloads that already have a Medplum id, should the foundation issue a `PUT`/update, keep the record `Pending sync` until a later update feature, or fail explicitly as unsupported? The current code silently creates a new resource if search misses.

## Test Coverage Reviewed

- Latest `/dev-test` result: `python -m unittest discover -s tests` passed 85 tests.
- Latest `/dev-test` result: `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py` passed.
- Latest `/dev-test` result: `node --check frontend\static\app.js` passed.
- Latest `/dev-test` result: `openspec validate --changes add-fhir-local-sync-foundation` passed.

Residual gap: `test_fhir_sync_creates_once_when_identifier_is_missing` covers only the first create path. It does not retry the same local record after a successful create.
