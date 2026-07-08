## Findings

### P2 - Validation failures leave FHIR records stuck in `Syncing`

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:443) marks the record `Syncing` before entering the `try` block, but [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:495) only converts `UpstreamFhirError` into a recorded sync failure. Local validation failures raised after that point, especially missing Medplum credentials from `MedplumAuthManager.get_access_token()` at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:136), bubble to the route handler at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:2053), which returns `400` without calling `mark_fhir_sync_failure()`.

That leaves the local FHIR workflow record indefinitely in `Syncing`, with no sync attempt or error captured. This violates the ticket requirement that Medplum-unavailable or not-configured flows preserve local records with `Pending sync`/`Sync failed` status and diagnostic detail. Wrap the sync body so `ValidationError`/`SimulatorValidationError` after `mark_fhir_syncing()` also record an attempt and mark the record `Sync failed`, or move `mark_fhir_syncing()` inside a broader exception-handled block.

### P2 - Updating a synced local FHIR record can keep stale `Synced` status

When `create_fhir_workflow_record()` receives an existing deterministic identifier, it updates `resource_json` and `dependency_json` but deliberately preserves `Synced` status via the CASE expression at [backend/lab_store.py](C:/Personal_repo/Projects/healthcare-lab/backend/lab_store.py:2930). If a later workflow regenerates the same resource with changed content after it was already synced, the local ledger now contains unsynced resource JSON while still showing `Synced` and retaining the old Medplum reference.

That makes the status display unreliable and can prevent the retry path from sending the updated resource. Either treat duplicate creates as idempotent no-ops when already synced, or mark the record `Pending sync` and clear/retain metadata intentionally when the payload changes. Add a regression test covering "synced record updated with changed resource becomes pending" or the chosen no-op behavior.

## Open Questions

- Should the sync API return non-2xx status when the record transitions to `Sync failed`, or is the current `200` with `success: false` the intended operator contract?

## Test Coverage Reviewed

- `python -m unittest discover -s tests -v`
- `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py`
- `node --check frontend\static\app.js`
- `openspec validate --changes add-fhir-local-sync-foundation`

The automated tests cover Medplum HTTP failure and mocked search/create behavior, but they do not cover local validation failures after `Syncing` or resource mutation after a successful sync.
