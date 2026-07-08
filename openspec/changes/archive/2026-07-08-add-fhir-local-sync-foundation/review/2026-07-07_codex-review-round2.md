## Findings

### P2 - Failed Medplum HTTP attempts lose the actual method and response payload

[app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:495) catches every `UpstreamFhirError` in one fallback path and records the sync attempt as method `SYNC` with no `response_payload` at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:498). For a real Medplum HTTP rejection from the identifier GET or create POST, `request_fhir_json()` has already read the upstream body at [app.py](C:/Personal_repo/Projects/healthcare-lab/app.py:322), but that parsed/raw response is not carried into the attempt row.

That means `/api/fhir/records/<id>/attempts` reports a failed search/create as a synthetic `SYNC` attempt with `{}` response payload, even though the spec requires preserving the HTTP method, request URL, HTTP status, and response payload when available. It also makes operators unable to distinguish a failed identifier search from a failed create. Consider using an upstream exception type that carries `status_code` and parsed/raw `response_payload`, or recording the GET/POST attempt around each request site before re-raising into the status failure path.

## Open Questions

- Should `/api/fhir/records/<id>/sync` continue returning `200` with `success: false` for upstream sync failures? The current tests encode that contract, so I did not mark it as a defect.

## Test Coverage Reviewed

- Latest `/dev-test` result: `python -m unittest discover -s tests` passed 85 tests.
- Latest `/dev-test` result: `python -m py_compile app.py backend\lab_store.py backend\dashboard_services.py backend\lab_operations.py tests\test_app.py tests\test_lab_store.py tests\test_b64_pdf.py` passed.
- Latest `/dev-test` result: `node --check frontend\static\app.js` passed.
- Latest `/dev-test` result: `openspec validate --changes add-fhir-local-sync-foundation` passed.

Residual gap: the mocked HTTP failure test asserts final `Sync failed` and `OperationOutcome`, but does not assert the sync attempt method or `responsePayload` for HTTPError failures.
