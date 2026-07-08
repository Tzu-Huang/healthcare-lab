## Findings

### P1: Empty read-back response after create is still marked confirmed

- File: `app.py:773`
- File: `app.py:798`

The fix handles read-back transport/HTTP failures by marking the canonical mapping `Pending sync`, but the normal create path still treats a successful read-back request with no parsed identifiers as a confirmed mapping. If dcm4chee returns `[]`, `{}`, or another valid JSON body without MWL identifiers, `readback_identifiers` remains empty, `readback_error_type` remains empty, and the mapping is updated to `DCM4CHEE_MWL_STATUS_CREATED`. Future syncs then hit the early return for `Created` mappings and never retry read-back, leaving generated identifiers missing permanently.

Suggested direction: mirror the existing pre-POST read-back branch: when the read-back call succeeds but `dcm4chee_identifiers_from_response_body()` returns no identifiers, set an explicit `dcm4chee_readback_empty` error and leave the canonical mapping pending/failed rather than `Created`.

## Resolved From Prior Review

- Prior P1 transport/HTTP read-back failures after a successful create are now retryable because the mapping is left pending instead of confirmed.
- Prior P2 historical dcm4chee attempts are now backfilled into canonical mappings and linked to the generated mapping id.

## Open Questions / Residual Risk

- The read-back endpoint shape still needs validation against the local dcm4chee runtime; current coverage mocks the DICOM JSON response path.

## Verification Reviewed

- `openspec validate add-dcm4chee-pacs-ledger --strict`
- `node --check frontend\static\app.js`
- `python -m unittest tests.test_app -k dcm4chee` -> 15 tests passed on rerun
- `python -m unittest tests.test_lab_store.HealthcareLabStoreTests.test_dcm4chee_mapping_backfills_from_existing_attempts` -> passed
- `python -m unittest discover -s tests` -> 119 tests passed
