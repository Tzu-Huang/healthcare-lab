# Code Review: add-fhir-patient-medplum-create

## Findings

No issues found.

## Residual Risk / Test Gaps

- Live Medplum smoke was not exercised in this review; local coverage uses mocked Medplum OAuth, search, create, failure, and retry responses.
- The UI path was reviewed statically and covered through API/frontend syntax checks, but no browser-level Playwright interaction was run for the expanded Patient table.

## Reviewed Scope

- `app.py`: FHIR Patient create-and-sync route behavior and row-level retry endpoint.
- `backend/lab_store.py`: additive Patient fields, FHIR Patient resource mapping, paired FHIR ledger metadata joins.
- `frontend/templates/index.html` and `frontend/static/app.js`: FHIR-only fields, preview generation, sync status/reference/error display, retry action.
- `tests/test_app.py` and `tests/test_lab_store.py`: store and API coverage for mapping, sync success, failure preservation, and retry/idempotency.
- `openspec/changes/add-fhir-patient-medplum-create/*`: proposal/task/spec alignment.

## Verification Referenced

- `openspec validate --changes add-fhir-patient-medplum-create`
- `python -m py_compile app.py backend\lab_store.py tests\test_app.py tests\test_lab_store.py`
- `node --check frontend\static\app.js`
- `python -m unittest discover -s tests` (89 tests passed)

