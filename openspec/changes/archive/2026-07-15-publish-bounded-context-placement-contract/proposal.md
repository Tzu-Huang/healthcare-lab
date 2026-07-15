## Why

Healthcare Lab has responsibility-oriented packages, but its published guidance does not yet assign every patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane responsibility to a named destination. Large compatibility modules can therefore continue to accumulate SQL, payload construction, workflow coordination, or transport logic without violating the current architecture checks.

## What Changes

- Publish the target backend, frontend, and test trees together with a bounded-context placement matrix covering every current responsibility in the large compatibility modules.
- Define dependency direction, allowed compatibility facades, and a repeatable placement decision process for engineers and Codex.
- Extend the architecture contract to report category, path, and line for new SQL, payload, workflow, and transport logic placed in catch-all modules.
- Freeze an explicit baseline for retained legacy implementation so incremental migration remains possible while new monolithic responsibility is rejected.
- Preserve all runtime behavior, API contracts, persistence semantics, frontend behavior, and integration behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Strengthen the placement guidance and mechanical architecture contract with bounded-context ownership, compatibility-facade rules, and baseline-aware rejection of new catch-all implementation.

## Impact

- Architecture guidance under `docs/`, including backend, frontend, and test placement rules.
- `tests/test_architecture_contract.py` and any focused fixtures or baseline data used by the architecture contract.
- Existing large modules such as `backend/lab_store.py`, `backend/dashboard_services.py`, `backend/lab_operations.py`, `backend/gdt_adapter.py`, `frontend/static/app.js`, `frontend/static/styles.css`, and `tests/integration/test_app.py` are documented and constrained but not broadly extracted by this change.
- No new runtime dependency, schema migration, endpoint change, or frontend framework is introduced.
