## Why

Patient sync, MWL, and result persistence still form the largest remaining bounded context inside `DemoStore`, mixing SQLite ownership with DICOM payload, identifier, reconciliation, fixture, and workflow behavior. The shared database infrastructure and extracted patient/order repositories now provide the stable composition seams needed to split this context without changing supported dcm4chee behavior.

## What Changes

- Add dedicated dcm4chee patient-sync, MWL, and result repositories that share the application connection factory and write lock.
- Move all dcm4chee ledger SQL, including enrichment reads and deterministic MWL startup backfill, behind the matching repository owner.
- Keep DICOM payload construction, UID/identifier rules, response parsing, status projection, and cross-context fixture/evidence workflows outside repositories.
- Replace broad patient/order coordination dependencies with explicit patient-sync, MWL, and result capabilities assembled in the composition root.
- Retain only mechanical `DemoStore` compatibility delegates and shrink the reviewed architecture baseline as implementation moves out.
- Add focused characterization and repository/service tests for retries, verification, reconciliation, duplicates, refresh snapshots, and historical backfill.
- Add bounded YOLO-mode guardrails so unattended implementation may resolve routine internal issues but must stop before data-destructive, externally mutating, behavior-changing, or scope-expanding actions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Require separate dcm4chee patient-sync, MWL, and result persistence owners, narrow service ports, and compatibility-only `DemoStore` delegation.
- `healthcare-lab-sqlite-infrastructure`: Assign deterministic dcm4chee MWL backfill to the MWL persistence owner while retaining shared startup orchestration and legacy convergence behavior.

## Impact

- Affected code: `backend/lab_store.py`, `backend/repositories/`, `backend/domain/dicom.py`, DICOM templates, patient/order/dcm4chee services, enrichment collaborators, and `backend/app_factory.py`.
- Affected tests: focused dcm4chee repository/domain/template/service coverage, disposable-database migration/backfill tests, integration regressions, and the architecture legacy baseline.
- Public HTTP APIs, SQLite schema, stored rows, retry semantics, DICOM payload meaning, reconciliation precedence, refresh visibility, and deployment configuration remain compatible.
- Verification uses disposable databases and external-service doubles only; no real `instance/*.db`, live dcm4chee, or other live healthcare service is accessed or mutated.
