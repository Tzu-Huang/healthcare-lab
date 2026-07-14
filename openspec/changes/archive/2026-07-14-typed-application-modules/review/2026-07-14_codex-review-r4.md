# Codex Review R4: ZAC-53 Typed Application Modules

- Date: 2026-07-14
- Branch: `feature/ZAC-53_typed-application-modules`
- Base: `main`
- Verdict: Changes requested

## Findings

### [P2] Remove the remaining API dependency on the operation adapter module

`backend/api/lab_servers.py:11` and `backend/api/dashboard.py:11` still import `LabOperationError` from `backend.lab_operations`. That module is not a service/domain boundary: it owns Docker socket and subprocess operation implementations, and imports the concrete store at `backend/lab_operations.py:12`. Consequently, importing either Blueprint still loads `backend.lab_store` transitively even though the new architecture contract only checks for a direct `backend.lab_store` import and reports the API boundary as clean.

Move `LabOperationError` to a domain- or service-owned error module (with a compatibility re-export from `backend.lab_operations` if required), then have the APIs import it through that boundary. Tighten the API dependency contract so infrastructure/operation adapter modules cannot bypass the intended API-to-service direction.

### [P2] Add focused service coverage for the new Lab and Dashboard coordinators

The fix moved roughly 225 lines of coordination into `LabServerWorkflowService` and `DashboardWorkflowService` at `backend/services/lab_workflow.py:113-335`, but no test under `tests/services` references either class. The existing integration route tests keep the HTTP behavior green, yet they do not directly lock down the injected repository/callback contracts, disabled-server smoke history, per-service bulk failure behavior, or operation-target selection at the service boundary. This conflicts with the checked task at `openspec/changes/typed-application-modules/tasks.md:26` and the focused-test scenario in the architecture spec.

Add focused unit tests in `tests/services` using fake repositories and injected callbacks for both coordinators, including success and partial-failure paths. Retain the integration tests for endpoint compatibility.

## Resolved From Previous Round

- GDT directory validation is now owned by `backend.repositories.gdt_bridge_health`; services and repositories no longer import runtime modules.
- Lab Servers and Dashboard route coordination now resides in service objects injected by the composition root.
- API modules no longer directly import or call `DemoStore`, and the repository Protocol includes the new service operations.
- Architecture contracts now reject direct API concrete-store imports and outward service/repository runtime imports.

## Verification Evidence

- Focused architecture/config/client/domain/service/runtime/repository suite: 82/82 passed.
- Full automated suite: 208/208 passed.
- Python compileall, frontend syntax, Docker Compose config, local Flask smoke, dependency scans, `git diff --check`, and strict OpenSpec validation passed.
- Live Medplum, dcm4chee, OIE, and GDT service smoke was not run.

## Residual Risk

No behavior regression was reproduced. Remaining risk is that the API boundary is only directly—not transitively—enforced, and the newly introduced service coordination surface can change without focused service tests identifying which injected contract regressed.
