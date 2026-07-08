# Code Review: add-dcm4chee-connection-profile

## Findings

### P2 - Invalid dcm4chee config can crash startup before diagnostics

File: `app.py:2626`

`create_app()` eagerly casts `DCM4CHEE_DIMSE_PORT` with `int(...)`, and nearby TLS booleans are parsed with `parse_config_bool(...)` at startup. If an operator sets `DCM4CHEE_DIMSE_PORT=abc` or `DCM4CHEE_TLS_ENABLED=maybe`, Flask app creation raises before `/api/dcm4chee/profile/diagnostics` can return the clear invalid-field report required by the change. The same issue exists in `dcm4chee_profile_from_config()` at `app.py:304` for configs mutated at runtime or in tests. Keep raw values in config/profile construction and let `validate_dcm4chee_profile()` produce the invalid port/boolean diagnostics instead of failing early.

## Open Questions

- Should invalid booleans be reported as profile diagnostics checks, or should only numeric/URL/profile identity values be treated as recoverable configuration errors?

## Test Coverage / Residual Risk

- Existing tests cover default profile loading, missing AE title, invalid DICOMweb URL, certificate-without-TLS diagnostics, unknown profile route, full `tests.test_app`, and OpenSpec validation.
- Missing coverage: malformed raw env values for `DCM4CHEE_DIMSE_PORT`, `DCM4CHEE_TLS_ENABLED`, and `DCM4CHEE_TLS_VERIFY` should not crash app startup if diagnostics are expected to handle incomplete/invalid configuration.

## Verification Reviewed

- `python -m py_compile app.py tests\test_app.py`
- `python -m unittest tests.test_app -v` (77 tests)
- `openspec validate add-dcm4chee-connection-profile --strict`
