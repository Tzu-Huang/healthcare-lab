## Findings

No blocking issues found in this review round.

## Resolved From Prior Reviews

- Read-back transport/HTTP failures after a successful create are retryable because the mapping remains pending rather than confirmed.
- Empty successful read-back responses now set `dcm4chee_readback_empty`, keep the mapping retryable, and are covered by regression tests.
- Historical `local_dcm4chee_mwl_attempts` rows are backfilled into canonical mappings and linked to the generated mapping id.

## Open Questions / Residual Risk

- The dcm4chee read-back endpoint and query parameter shape are still mocked in local tests; this should be validated against the local dcm4chee Docker runtime before relying on generated-identifier read-back in a demo.
- Full AP C-STORE result ingestion/display remains out of scope for this change.

## Verification Reviewed

- `openspec validate add-dcm4chee-pacs-ledger --strict`
- `node --check frontend\static\app.js`
- `python -m unittest tests.test_app -k dcm4chee` -> 16 tests passed
- `python -m unittest tests.test_lab_store.HealthcareLabStoreTests.test_dcm4chee_mapping_backfills_from_existing_attempts` -> passed
- `python -m unittest discover -s tests` -> 120 tests passed
