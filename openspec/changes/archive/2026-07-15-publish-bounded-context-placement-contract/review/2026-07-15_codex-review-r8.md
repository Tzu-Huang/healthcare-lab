# Codex Review Round 8: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`23cfe90`)

Verdict: **Changes requested**

## Findings

### [P1] Enforce the complete documented layer dependency matrix

`tests/test_architecture_contract.py:711`

The import parser now resolves absolute, parent-package, relative, and nested-module imports, but the assertions consume that information through a few narrow prohibitions rather than the published inward dependency matrix. Several outward edges therefore remain accepted:

```python
# backend/api/example.py
import backend.clients.medplum

# backend/clients/example.py
import backend.services.fhir_workflow

# backend/repositories/example.py
import backend.clients.dcm4chee

# backend/domain/example.py
import backend.services.patient_workflow
```

The API tests ban only `lab_store` and `lab_operations`; the lower-layer test bans Flask and `backend.api` (plus configuration from domain); and the remaining tests cover runtime and concrete-repository special cases. None rejects the examples above. This conflicts with the OpenSpec requirement that APIs invoke services, services coordinate clients/repository ports, and clients/repositories/templates depend only on allowed configuration/domain types.

Define an explicit allowed-layer import matrix (with the two reviewed repository exceptions represented by the existing baseline), apply it to every recursively discovered module, and add one negative fixture for each forbidden outward edge. This also makes the architecture test directly auditable against the published table instead of relying on overlapping special-case tests.

## Missing tests and residual risks

- Existing dependency fixtures focus on Flask, API, runtime, `DemoStore`, operation adapters, and concrete repositories; they do not exercise API-to-client or lower-layer-to-service/client edges.
- Cross-context ownership is still represented mainly through named destinations and concrete-repository restrictions; the layer matrix should remain independent of context naming.
- Current automated verification remains green at 30 architecture tests and 229 full-suite tests; this is an uncovered policy-enforcement gap.

## Resolution

- Added an explicit allowed-layer dependency matrix matching the published inward direction, including configuration and domain allowances by layer.
- Applied the matrix to every recursively discovered responsibility module while preserving only the reviewed concrete-repository exceptions.
- Added API-to-client, client-to-service, repository-to-client, and domain-to-service negative fixtures plus a live-tree matrix check. Focused architecture verification: 32 tests passed.
