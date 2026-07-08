# Code Review: add-dcm4chee-connection-profile Round 2

## Findings

### P2 - Out-of-range dcm4chee DIMSE port can still crash smoke checks

File: `app.py:1368`

The fix makes non-numeric `DCM4CHEE_DIMSE_PORT` values diagnostic-friendly, but `run_tcp_smoke()` still accepts any value that can be cast with `int(...)` and then calls `socket.create_connection()` without checking the valid port range. A profile value like `DCM4CHEE_DIMSE_PORT=99999` is correctly marked invalid by `validate_dcm4chee_profile()`, but the dcm4chee smoke path still proceeds to `run_tcp_smoke(dimse["host"], dimse["port"], ...)` and can raise an uncaught `OverflowError` from the socket layer instead of returning a Down/diagnostic response. Add the same `1 <= port <= 65535` guard in `run_tcp_smoke()` before opening the socket, with a regression test for an out-of-range dcm4chee profile port.

## Open Questions

- None.

## Test Coverage / Residual Risk

- Existing malformed-env coverage now protects non-numeric DIMSE ports and malformed TLS booleans.
- Missing coverage: numeric but out-of-range dcm4chee DIMSE ports during smoke/profile diagnostics.

## Verification Reviewed

- `python -m py_compile app.py tests\test_app.py`
- `python -m unittest tests.test_app -v` (78 tests)
- `openspec validate add-dcm4chee-connection-profile --strict`
