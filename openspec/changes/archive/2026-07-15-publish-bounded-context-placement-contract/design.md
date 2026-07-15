## Context

ZAC-53 established responsibility-oriented backend packages and reduced `app.py` to a thin entrypoint, but substantial retained implementation remains in compatibility-era catch-all files. `backend/lab_store.py` still combines persistence with validation, protocol payload construction, and reconciliation; `backend/dashboard_services.py` combines dashboard projection with Docker access; the frontend and integration suite remain concentrated in `frontend/static/app.js`, `frontend/static/styles.css`, and `tests/integration/test_app.py`.

The current architecture guide explains generic layers and future OIE placement, while the architecture contract protects dependency direction and selected misplaced constructs. It does not name the destination of every current responsibility or inspect retained catch-all modules. This change must close that gap without forcing a broad extraction or changing behavior.

## Goals / Non-Goals

**Goals:**

- Publish an implementation-ready placement contract for patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane responsibilities.
- Describe target backend, frontend, and test trees and a deterministic placement decision process.
- Define inward dependency direction and the narrow conditions under which compatibility facades may remain.
- Detect new SQL, payload, workflow, and transport implementation in catch-all modules with category, path, and current line diagnostics.
- Permit existing legacy implementation to remain and be removed incrementally.

**Non-Goals:**

- Extract all retained responsibilities from `DemoStore`, frontend globals, or the integration suite.
- Change API contracts, database schemas, runtime lifecycle, protocol payloads, or UI behavior.
- Introduce an ORM, frontend framework, build system, or new static-analysis dependency.
- Implement the later OIE management or Settings workspace features.

## Decisions

### Publish one responsibility inventory as the placement authority

`docs/architecture.md` will contain target backend, frontend, and test trees plus a bounded-context matrix. Each current responsibility family will identify its current source, category, target owner, matching test destination, and whether a temporary compatibility facade is allowed. The matrix will cover patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane behavior, including mixed modules such as `lab_store.py` and `dashboard_services.py`.

The same guide will provide a placement sequence: identify the bounded context, classify the behavior as HTTP/workflow/transport/runtime/persistence/domain/template/composition, choose the named destination, then place tests in the mirrored package. Engineers and Codex therefore use the same contract.

Alternative considered: maintain separate documents per context. Rejected because duplicated dependency and facade rules would drift and make placement decisions harder to audit.

### Keep dependency direction layer-based inside each bounded context

HTTP APIs and runtime composition invoke services; services coordinate ports implemented by clients and repositories; clients, repositories, and templates use domain types; domain code remains framework-independent. Cross-context orchestration belongs in an explicitly named service rather than one context importing another context's API or concrete repository. `backend/app_factory.py` remains the composition root.

Alternative considered: allow arbitrary imports between modules sharing a context name. Rejected because context naming alone does not prevent Flask, SQLite, or transport concerns from leaking inward.

### Treat compatibility facades as enumerated migration seams

Allowed facades will be listed with their owning destination and retained caller. A facade may re-export or delegate to the owning implementation, but it must not receive new SQL, payload, workflow, or transport behavior. New callers import the owning module directly. Removing a facade or shrinking its baseline is always allowed.

`app.py` remains the process compatibility boundary. Retained catch-all modules such as `DemoStore`, `gdt_adapter.py`, `dashboard_services.py`, `lab_operations.py`, `app.js`, and `styles.css` are migration sources, not destinations for new responsibility.

Alternative considered: allow any old module to act as a facade by convention. Rejected because an implicit exception would recreate the catch-all pattern.

### Enforce a frozen legacy baseline instead of demanding immediate extraction

The architecture test will scan named catch-all files and classify candidate implementation as SQL, payload, workflow, or transport. Existing candidates are represented by an explicit baseline keyed by category, path, qualified symbol or stable source fingerprint. A live violation is accepted only when it matches the reviewed baseline; newly introduced or materially changed candidates fail with category, path, and the line reported from the current source.

The baseline is monotonic in normal development: extraction removes entries, while adding or refreshing an entry requires an intentional architecture-contract change visible in review. Python inspection will use the standard-library AST. Frontend enforcement will use explicit inventories of existing top-level functions and selectors plus categorized forbidden additions, avoiding a new JavaScript parser or build dependency.

Alternative considered: enforce only file-size ceilings or baseline counts. Rejected because replacement logic could keep the same size or count while adding a new responsibility. Alternative considered: forbid every existing violation immediately. Rejected because it would turn this contract ticket into a risky broad migration.

### Keep behavioral regression tests separate from placement tests

The architecture contract verifies ownership and dependency rules; existing focused and integration tests continue to prove behavior. Moving implementation or tests is performed by later changes, which first add or relocate focused coverage and then shrink the compatibility baseline.

Alternative considered: move the 4,000-line integration suite during this change. Rejected because test reorganization would obscure whether the placement contract itself changed behavior.

## Risks / Trade-offs

- [A baseline can be updated to legitimize new catch-all logic] -> Require baseline changes to name the category and target destination, keep them explicit in review, and document that additions are exceptional migration decisions.
- [Static heuristics miss dynamically constructed payload or transport logic] -> Combine AST constructs, qualified-symbol inventories, imports/calls, and representative negative fixtures for every required category.
- [Frontend parsing without a JavaScript AST is less precise] -> Enforce stable top-level inventories and narrow forbidden patterns now; keep the contract dependency-free and strengthen it when a build/parser tool is adopted.
- [Strict fingerprints flag harmless edits in retained legacy code] -> Prefer qualified-symbol fingerprints scoped to classified constructs and move changed behavior to its target owner instead of casually refreshing the baseline.
- [The placement matrix becomes stale] -> Make architecture tests and the contributor decision process point to the matrix, and require new contexts or exceptions to update it in the same change.

## Migration Plan

1. Inventory current responsibilities in the named large modules and publish the target trees, context matrix, dependency rules, facade list, and placement decision process.
2. Add baseline-aware scanners and negative fixtures for SQL, payload, workflow, and transport violations.
3. Cover Python and frontend catch-all entrypoints without changing their runtime contents.
4. Run focused architecture tests, the full regression suite, compilation, frontend syntax checks, and strict OpenSpec validation.
5. In later extraction changes, move responsibility and focused tests together, then delete the corresponding baseline entry.

Rollback consists of reverting the documentation and architecture-test commit; no data or runtime migration is involved.

## Open Questions

None. ZAC-55 is treated as a documentation-and-enforcement change; broad responsibility extraction remains follow-up work.
