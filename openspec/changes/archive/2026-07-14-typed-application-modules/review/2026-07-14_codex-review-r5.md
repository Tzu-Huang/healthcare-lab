# Codex Review R5: ZAC-53 Typed Application Modules

- Date: 2026-07-14
- Branch: `feature/ZAC-53_typed-application-modules`
- Base: `main`
- Verdict: Changes requested

## Findings

### [P2] Remove the remaining transitive DemoStore dependency from the Lab workflow service

`backend/services/lab_workflow.py:23` imports dashboard coordination helpers from
`backend.dashboard_services`, while `backend/dashboard_services.py:15` obtains
`SimulatorValidationError` from `backend.lab_store`. Consequently, importing
`backend.services.lab_workflow` still loads `backend.lab_store`, even though the service
declares a repository Protocol and the architecture guidance says services coordinate
clients and repositories through inward-facing boundaries. An isolated import scan
reproduces `backend.lab_store` in `sys.modules`; the other typed service and runtime
modules do not load it.

The contract at `tests/test_architecture_contract.py:217` only inspects direct imports,
so it reports this service boundary as clean. Import `SimulatorValidationError` from
`backend.domain.errors` in the dashboard helper (or move the helper into an owned typed
boundary), then extend the service dependency contract to catch this transitive or
legacy-module bypass.

## Resolved From R4

- Lab Server and Dashboard APIs now import `LabOperationError` from the domain boundary;
  importing all API modules no longer loads `backend.lab_operations` or
  `backend.lab_store`.
- `backend.lab_operations` uses domain-owned errors and operation constants while
  preserving the compatibility export.
- Focused tests now cover Lab/Dashboard injected contracts, disabled-server smoke
  history, mixed success/failure handling, bulk failure isolation, and operation target
  selection.

## Verification Evidence

- Focused architecture/config/client/domain/service/runtime/repository/GDT/PDF suites:
  88/88 passed.
- Full automated suite: 214/214 passed.
- Python compileall, frontend syntax, Docker Compose config, local Flask smoke,
  `git diff --check`, and strict OpenSpec validation passed.
- Isolated API import scan passed; isolated Lab workflow import scan reproduced the
  finding above.
- Live Medplum, dcm4chee, OIE, GDT, and browser interaction smoke was not run.

## Residual Risk

No behavior regression was reproduced. Until the remaining import edge is removed and
the contract is strengthened, future changes in the legacy dashboard helper or concrete
store can reintroduce service-layer coupling without failing architecture tests.
