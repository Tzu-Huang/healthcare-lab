# Codex Code Review

**Change:** `add-persistent-oie-settings-profile`  
**Branch:** `feature/ZAC-45_add-persistent-oie-settings-profile`  
**Base:** `main`  
**Verdict:** Changes requested

## Findings

### [P2] Convert malformed URL parser failures into actionable validation errors

**Location:** `backend/lab_store.py:1491-1492`, `app.py:4608-4613`

`validate_oie_settings_payload()` calls `urllib.parse.urlparse()` and reads `hostname` without handling their `ValueError` cases. A malformed bracketed host such as `http://[bad` raises `ValueError: Invalid IPv6 URL` instead of `SimulatorValidationError`. The PUT route catches only `SimulatorValidationError`, so this invalid client input escapes the intended 400 response path and becomes an internal error.

This violates the specification that every invalid Management API URL returns an actionable validation error. Wrap URL parsing and hostname extraction in `try/except ValueError`, translate the failure to the existing `SimulatorValidationError`, and add an API regression test using a malformed IPv6-style URL.

### [P2] Validate passwords as opaque strings without coercing or trimming them

**Location:** `backend/lab_store.py:1566-1577`

The password update path converts any non-null JSON value with `str(...)` and then applies `.strip()`. Consequently, a numeric password such as `123` is silently stored as `"123"`, while a legitimate secret such as `"  secret  "` is changed to `"secret"`. Passwords are case- and byte-sensitive credentials and should not be normalized or coerced.

Require the submitted value to be a string, use trimming only to determine whether it is empty, and persist the original string unchanged. Add tests covering rejection of non-string values and preservation of leading/trailing whitespace.

## Verification Reviewed

- `python -m unittest tests.test_lab_store tests.test_app`: 155 tests passed.
- Focused OIE settings API tests: 4 tests passed.
- Python compilation and `git diff --check`: passed.
- `openspec validate add-persistent-oie-settings-profile --strict`: passed.
- Review probes reproduced both findings without modifying repository state.

## Residual Risks

- The OIE password remains plaintext in the local SQLite database by explicit design; filesystem access control is the current protection boundary.
- External OIE authentication, Channel deployment, listener auto-start, and Settings UI integration remain outside this change and were not exercised.
