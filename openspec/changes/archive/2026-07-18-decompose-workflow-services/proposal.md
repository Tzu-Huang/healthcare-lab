## Why

Repository, domain, template, and mapper boundaries are now explicit after ZAC-56 through ZAC-61, but several workflow services still coordinate multiple independent use cases through broad ports. ZAC-62 decomposes those services before facade removal so application behavior remains maintainable, testable, and aligned with the published architecture.

## What Changes

- Split Lab coordination into focused dashboard, health, operations, smoke, and resource/status use cases.
- Split FHIR coordination into focused sync, inventory/query, preview, DiagnosticReport, and retry/status use cases.
- Split Order/dcm4chee coordination into focused patient, MWL, verification, result-refresh, and evidence/simulated-return use cases.
- Review Patient and GDT workflows and extract only cohesive use cases with independent responsibilities; avoid empty pass-through wrappers.
- Replace broad workflow collaborators with narrow typed ports while keeping Flask, concrete stores, repositories, runtime lifecycle, SQL, protocol construction, and reusable presentation outside service implementations.
- Keep `backend/app_factory.py` as a compact composition root and preserve routes, public JSON, errors, persistence, startup, background runtime, and external-integration behavior.
- Add focused service characterization tests and architecture enforcement without broad test-file decomposition or allowlist expansion.
- Stage the work safely alongside OIE development: exploration and proposal may proceed now, but implementation begins only after ZAC-46 is merged and this branch is updated from `main`; ZAC-47 is not an apply dependency.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-typed-application-architecture`: Require workflow services to represent focused use cases with narrow typed ports, preserve framework and infrastructure independence, keep composition compact, and define the behavior-preserving migration and parallel-work boundaries.

## Impact

- Affected production areas: workflow modules under `backend/services/`, their composition in `backend/app_factory.py`, and only the API/runtime call sites necessary to preserve existing wiring.
- Affected verification: focused service tests, API and startup characterization, architecture dependency and legacy-baseline contracts, full regression tests, compilation, and strict OpenSpec validation.
- Known integration hotspot: ZAC-46 also changes `backend/app_factory.py` to compose the OIE management client. ZAC-62 must update from the ZAC-46 merge before implementation and retain that wiring.
- Explicitly unaffected parallel scope: ZAC-46 OIE management client/settings responsibilities and ZAC-47 managed-channel domain/templates.
- No database migration, dependency addition, live external-service operation, public API change, frontend modularization, broad test-file cleanup, or `DemoStore`/compatibility-export removal is introduced.
