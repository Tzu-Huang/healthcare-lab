# Code Review: remove-medplum-task-workflow

## Findings

No findings. I found no correctness, data-retention, frontend-state, or test-coverage issue that should block the change.

## Review Scope

- Compared `main...HEAD` on `feature/remove-medplum-task-workflow`.
- Reviewed the backend FHIR supported-resource contract, ServiceRequest order orchestration, historical Task materialization and API guards, and local order response shape.
- Reviewed the Medplum Patient console grouping, related-resource rendering, raw preview copy, and ServiceRequest-only acceptance state.
- Reviewed store, API, and frontend contract tests plus active documentation and diagram changes.
- Reviewed the OpenSpec proposal, design decisions, delta requirements, and completed task checklist.

## Evidence

- New FHIR orders create and synchronize only ServiceRequest, and the refreshed order response no longer contains `fhir.task`.
- Historical Task ledger rows remain readable internally for audit materialization but are excluded from active resource lists and rejected by record preview/sync paths.
- Task creation through the generic FHIR record API is rejected because Task is no longer a supported mapping.
- Frontend FHIR order acceptance requires only a synced `ServiceRequest/<id>` reference.
- Patient FHIR Order rollups and related-resource navigation no longer group or display Task.
- The historical-data guard test covers list, inventory, record read, preview, sync, and new Task creation behavior.

## Verification

- `python -m unittest discover -s tests`: 155 tests passed.
- `node --check frontend/static/app.js`: passed.
- `python -m py_compile app.py backend/lab_store.py`: passed.
- `git diff --check`: passed.
- `openspec validate remove-medplum-task-workflow --strict`: passed.
- Active frontend, README, Markdown documentation, and SVG scan found no Task workflow references.

## Residual Risks

- A live Medplum integration smoke was not run. Automated tests mock the identifier search, ServiceRequest create, OperationOutcome failure, and historical Task rejection paths.
- Removing `fhir.task` and Task from supported resource lists is intentionally breaking for external consumers. The proposal documents this contract change.
- Existing Task rows and remote Medplum Task resources remain historical data by design; destructive cleanup is outside this change.

## Verdict

Ready for `/dev-done` from a code-review perspective.
