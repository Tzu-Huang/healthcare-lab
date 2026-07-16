## Why

Repository extraction in ZAC-56 through ZAC-60 established dedicated persistence owners, but several repositories still implement validation, protocol construction, and API-facing row presentation, while `DemoStore` retains compatibility helpers and constants whose final owners are not consistently documented. ZAC-61 completes those responsibility boundaries now so later service decomposition and facade removal do not preserve or recreate the same coupling.

## What Changes

- Add a framework- and persistence-independent mapper layer for reusable row and boundary presentation, and enforce its dependency direction in the architecture contract.
- Keep validation, normalization, identifiers, and status policy in domain modules; keep outbound HL7, FHIR, GDT, and DICOM payload construction in template modules; keep repositories focused on SQL, transactions, and invocation of injected pure collaborators.
- Finish the responsibility split context by context for Patient, Order, FHIR, GDT, and dcm4chee, including moving GDT `6302` construction out of the domain parser/validator module and moving reusable repository row projections to mappers.
- Include the small remaining Lab and OIE validation/presentation helpers so the repository-wide persistence boundary is internally consistent; retain GDT bridge directory health validation as an infrastructure boundary.
- Introduce only targeted typed boundary models where a shape crosses collaborators or currently relies on ambiguous `dict[str, Any]`; do not replace public JSON objects with a new runtime serialization model.
- Reconcile the placement guide with the modules that ZAC-58 through ZAC-60 actually created, and document every temporary compatibility export with its owner and retained callers.
- Preserve schema, stored data, payload bytes/content, API JSON contracts, errors, transaction behavior, and runtime behavior.
- Add bounded YOLO-mode safeguards: autonomous work may resolve directly caused internal failures within scope, but must stop before schema/data mutation, real database or live-service access, public contract change, architecture-baseline expansion, dependency installation, destructive operations, unsafe dirty-worktree overlap, or unrelated refactoring. Tests, allowlists, and compatibility behavior may not be weakened to bypass a stop condition.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Add mapper ownership and dependency rules; require validation, payload construction, and reusable row presentation to have one non-repository owner; reconcile repository requirements that previously allowed row-projection implementation; and generalize autonomous/YOLO safety boundaries for this behavior-preserving refactor.

## Impact

- Affected production areas: `backend/domain/`, `backend/templates/`, a new `backend/mappers/` package, bounded-context repositories, compatibility exports in `backend/lab_store.py` and `backend/gdt_adapter.py`, and composition wiring where pure collaborators are injected.
- Affected verification: focused domain/template/mapper/repository characterization tests, architecture dependency and legacy-baseline contracts, full regression tests, compilation, and strict OpenSpec validation.
- Documentation: `docs/architecture.md` will describe actual owners, mapper placement, temporary export ownership, and the autonomous stop conditions.
- No database migration, dependency addition, external service operation, public API change, or frontend/service decomposition is introduced by this change.
