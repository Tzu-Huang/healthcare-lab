# Codex Review R3: ZAC-53 Typed Application Modules

- Date: 2026-07-14
- Branch: `feature/ZAC-53_typed-application-modules`
- Base: `main`
- Verdict: Changes requested

## Findings

### [P2] Do not make services and persistence depend on the runtime layer

The duplicate GDT directory validator is now consolidated, but its new owner creates the opposite dependency problem. `backend/services/lab_workflow.py:42` and the persistence compatibility module `backend/lab_store.py:86` both import `backend.runtime.gdt_bridge_health`. This conflicts with the declared inward direction in `docs/architecture.md:19` and the change design: runtime wiring points toward services, while services point toward clients, repositories, domain, and templates. A service importing runtime makes the lifecycle layer a lower-level utility dependency, and the new architecture test at `tests/test_architecture_contract.py:248-258` now hard-codes that reversed ownership instead of detecting it.

Keep one implementation, but place filesystem validation behind a health/repository boundary that does not require services or persistence to import runtime. If the watcher must invoke it directly, inject the validator at composition time or depend on a lower-level port. Extend the dependency contract to reject `backend.runtime` imports from services and repositories.

### [P2] Route the remaining Lab and Dashboard APIs through service boundaries

The OpenSpec requirement says API modules SHALL map HTTP input and output through services, but `backend/api/lab_servers.py:11-27` and `backend/api/dashboard.py:21-32` still import and type directly against `DemoStore`. These handlers also perform persistence/workflow coordination themselves: Lab Servers loops over and mutates the store at `backend/api/lab_servers.py:94-96,143-158`, while Dashboard resolves groups and backing servers directly at `backend/api/dashboard.py:78-92,114-132`. Other extracted APIs already accept workflow services from the composition root, so these two modules remain exceptions to the architecture being established.

Introduce Lab/Dashboard service ports (or service objects) that own CRUD, bulk check/smoke, group selection, and operation coordination, then inject those into the Blueprints. Move the remaining constants/errors to domain-owned imports where applicable, and add an architecture contract rejecting `backend.lab_store` imports from `backend/api`.

## Resolved From Previous Round

- Runtime watcher/listener modules no longer import the concrete `DemoStore` and now declare structural store/callback Protocols.
- `LabRepositoryPort` declares its consumed repository operations and has an AST contract preventing an empty surface.
- `validate_gdt_bridge_dirs` has one implementation, and watcher/smoke behavior now shares its validation semantics.

## Verification Evidence

- Focused architecture/config/client/domain/service/runtime/repository suite: 80/80 passed.
- Full automated suite: 206/206 passed.
- Python compileall, frontend syntax, Docker Compose config, local Flask smoke, `git diff --check`, and strict OpenSpec validation passed.
- Live Medplum, dcm4chee, OIE, and GDT service smoke was not run.

## Residual Risk

No behavior regression was reproduced. The remaining risk is architectural enforcement: the current code and tests allow API-to-concrete-persistence coupling and service/persistence-to-runtime coupling despite the dependency direction promised by the change specification.
