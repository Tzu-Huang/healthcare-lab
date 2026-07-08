## Findings

### P1: Successful create with failed read-back is never retried

- File: `app.py:639`
- File: `app.py:790`

When the POST succeeds but the follow-up read-back fails, the mapping is still updated with `sync_status=DCM4CHEE_MWL_STATUS_CREATED` while storing the read-back error. On later syncs, `sync_order_to_dcm4chee_mwl()` returns immediately for any mapping whose status is `Created`, so the failed read-back is never retried and missing dcm4chee-generated identifiers can remain missing permanently. This breaks the ZAC-37 requirement to store dcm4chee-generated identifiers once available and makes transient read-back failures unrecoverable through the normal retry path.

Suggested direction: distinguish "created but read-back pending/failed" from "confirmed mapping", or make the early return require both `Created` and no read-back error/missing required identifiers.

### P2: Existing dcm4chee attempts are not backfilled into canonical mappings

- File: `backend/lab_store.py:986`
- File: `backend/lab_store.py:1059`

The migration creates the new canonical mapping table and adds attempt linkage columns, but it does not backfill mappings from existing `local_dcm4chee_mwl_attempts`. Any local database that already has dcm4chee MWL attempts before this change will still show the latest attempt, but the new reconciliation lookup APIs will not find those orders because `local_dcm4chee_mwl_mappings` starts empty for historical rows.

Suggested direction: during initialization, insert one canonical mapping per existing dcm4chee order from the latest attempt row, then set `mapping_id` on existing attempts where possible.

## Open Questions / Residual Risk

- The read-back endpoint shape uses keyword query parameters against `/mwlitems`; local unit tests mock this path, but the actual dcm4chee runtime behavior still needs environment validation.
- Full AP C-STORE ingestion/display remains intentionally out of scope; this review only covers the mapping foundation.

## Verification Reviewed

- `openspec validate add-dcm4chee-pacs-ledger --strict`
- `node --check frontend\static\app.js`
- `python -m unittest tests.test_app -k dcm4chee` -> 14 tests passed
- `python -m unittest discover -s tests` -> 117 tests passed
