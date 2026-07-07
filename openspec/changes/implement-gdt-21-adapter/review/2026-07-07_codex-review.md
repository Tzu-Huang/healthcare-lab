# Codex Review: implement-gdt-21-adapter

## Findings

### P2 - `6310` required content fields are not rejected

`backend/gdt_adapter.py:207`

`parse_gdt_6310_result()` only checks that `8000` is `6310`, then builds canonical patient/result data by reading fields such as `3000` and `8402` if present. The shared validation helper currently enforces only `8000`, `8100`, and `9218` (`backend/gdt_adapter.py:310`), so a `6310` payload missing required result content such as `3000` or `8402` is accepted with empty canonical patient/test values. This conflicts with the ZAC-23 validation policy and the checked task for rejecting required-field failures. It also means `/api/gdt/results` can persist an invalid clinical result instead of returning a structured `200-299` validation error. Add message-type-specific required-field validation for `6310` and tests that omit `3000` and `8402`.

## Open Questions

- Should `6310` require at least one recognized measurement group, or is a text/artifact-only result acceptable for this adapter profile?
- Should malformed or incomplete `6302-6305` artifact groups be rejected now, or deferred until artifact validation is explicitly in scope?

## Residual Risk

- The review focused on the branch diff against `main`; no external device/vendor fixture was available, so vendor-specific `8410` mapping behavior is covered only by synthetic tests.

## Verification Reviewed

- `python -m unittest discover -s tests -v`
- `python -m py_compile app.py backend\gdt_adapter.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_gdt_adapter.py tests\test_lab_store.py tests\test_app.py tests\test_b64_pdf.py`
- `openspec validate implement-gdt-21-adapter --strict`
- `git diff --check`
