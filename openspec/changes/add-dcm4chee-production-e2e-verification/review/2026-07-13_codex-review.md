# Code Review - add-dcm4chee-production-e2e-verification

## Findings

### P1 - Separate simulated AP buttons hide the previous fixture result

`frontend/static/app.js:1548` and `frontend/static/app.js:1553` expose separate **Simulate AP PDF** and **Simulate AP DICOM** actions, but each backend call creates a new `refresh_generation` at `backend/lab_store.py:3823` and stores the created rows with that generation at `backend/lab_store.py:3851` and `backend/lab_store.py:3884`. Patient payload rendering then filters dcm4chee results to only the latest non-empty generation at `backend/lab_store.py:6652`.

That means the natural UI workflow "click Simulate AP PDF, then click Simulate AP DICOM" will make the PDF row disappear from the patient/order DICOM result browser as soon as the DICOM simulation is recorded, and the reverse order hides the DICOM row. This undercuts the ZAC-42 goal of validating AP-returned PDF and DICOM display from the UI. The current test only calls the API with `type: "both"`, so it misses the UI-exposed split-button path.

Suggested fix: either make the UI buttons record into the same fixture generation for an order, add a single "Simulate AP PDF + DICOM" action, or adjust simulated AP-return listing so fixture rows are not hidden by the latest-generation filter.

## Open Questions / Residual Risk

- Live AP C-STORE reconciliation remains manual/environment-specific and was not executed in this review.
- The simulated fallback path can create a mapping for an order that lacks one, but it uses the default UID root in `backend/lab_store.py:3813`; this is probably acceptable for normal UI-created DICOM orders because they already have mappings, but it is worth keeping in mind if the endpoint is used directly against manually seeded orders under a custom UID root.

## Verification Reviewed

- `openspec validate add-dcm4chee-production-e2e-verification --strict`
- `node --check frontend\static\app.js`
- `python -m py_compile app.py backend\lab_store.py tests\test_app.py`
- `python -m unittest tests.test_app tests.test_lab_store` reported 135 passing tests during `/dev-test`.
