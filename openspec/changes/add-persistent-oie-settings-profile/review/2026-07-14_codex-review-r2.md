# Codex Code Review — Round 2

**Change:** `add-persistent-oie-settings-profile`  
**Branch:** `feature/ZAC-45_add-persistent-oie-settings-profile`  
**Base:** `main`  
**Verdict:** Approved

## Findings

No findings.

## Prior Finding Resolution

- **Malformed Management API URLs:** Resolved by `f6ceddc`. URL parsing, hostname extraction, and port validation now translate parser `ValueError` failures into the existing actionable `SimulatorValidationError` response path. The API regression suite covers malformed bracketed-host input and verifies atomic rejection.
- **Password coercion and trimming:** Resolved by `0258ccb`. Password updates now require a non-empty JSON string, reject non-string values, and persist the original string without removing leading or trailing whitespace. Regression coverage verifies secret masking, log exclusion, verbatim persistence, omission preservation, and invalid-value rejection.

## Verification Reviewed

- `python -m unittest tests.test_lab_store tests.test_app`: 155 tests passed after both fixes.
- Python compilation for `app.py`, `backend/lab_store.py`, `tests/test_app.py`, and `tests/test_lab_store.py`: passed.
- `git diff --check`: passed.
- `openspec validate add-persistent-oie-settings-profile --strict`: passed.

## Residual Risks

- The OIE password remains plaintext in the local SQLite database by explicit local-lab design; filesystem access control remains the protection boundary.
- External OIE authentication, Channel deployment, listener auto-start, and Settings UI integration remain outside this change and were not exercised.
