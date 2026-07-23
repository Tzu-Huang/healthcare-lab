## Context

The current Settings view has separate API, state, component, view, CSS, and template files, but its page structure and view controller still jointly own OIE connection settings, the HLAB result listener, OIE diagnostics, and managed Channels. ZAC-71 introduced closed typed profiles and secret-safe public projections for Medplum and OIE. ZAC-72 must turn that foundation into an extensible workspace without prematurely implementing the later Medplum, GDT, dcm4chee, or AP forms.

OpenEMR is not part of the product direction for this workspace. Existing unrelated OpenEMR code is not removed by this change, but no Settings architecture or readiness behavior may depend on it or reserve a section for it.

## Goals / Non-Goals

**Goals:**

- Establish a stable Settings shell and integration-owned frontend module contract.
- Represent overall and per-section readiness without exposing secrets or PHI.
- Guide a fresh installation through required setup while allowing optional integrations to remain disabled.
- Preserve all existing OIE workflows and lifecycle safeguards.
- Make activation impact and bounded diagnostics understandable and testable.

**Non-Goals:**

- Implement final Medplum, GDT, dcm4chee, or AP configuration forms and persistence.
- Include, migrate, remove, or otherwise change OpenEMR.
- Rewrite Compose files, restart application processes, recreate containers, or run unbounded network probes.
- Infer readiness from non-empty form fields alone.

## Decisions

### Use a registry-driven Settings shell with integration-owned modules

The shell will own navigation, section activation, overview cards, first-run progression, and Run all checks orchestration. Each registered section will provide stable metadata plus its own view initializer, API adapter, state, and styles. OIE's existing behavior will move behind the OIE registration with compatibility-preserving DOM and API contracts.

Alternative considered: continue extending `views/settings.js`. Rejected because it would couple later integrations to OIE state and make independent testing and ownership progressively harder.

### Aggregate readiness behind a dedicated application service

A readiness provider contract will return a closed, secret-safe projection containing integration id, label, state, summary, required/optional classification, activation impact, and bounded action metadata. A dedicated service will combine registered providers and calculate overall completion. It will read typed public/effective settings and bounded diagnostics through injected ports rather than becoming another persistence owner.

Alternative considered: add readiness fields to typed profile responses. Rejected because operational diagnostics and setup progress have a different lifecycle from persisted configuration and not every section has a runtime profile.

### Model state as one primary readiness value plus bounded detail

Each section will expose exactly one of `ready`, `needs-setup`, `degraded`, `disabled`, or `restart-required`. `restart-required` takes presentation priority when saved valid intent is not yet effective; bounded detail can still identify diagnostic degradation without adding uncontrolled state combinations. Overall setup is complete when every required section is ready and every optional section is ready or disabled.

Alternative considered: arbitrary flags with client-side precedence. Rejected because different clients could calculate contradictory results.

### Persist no separate wizard cursor

The guided flow will derive the next actionable section from current readiness and will store only local presentation preference if needed. Leaving and returning resumes from authoritative persisted configuration, avoiding another server-side setup state that could drift.

Alternative considered: persist a wizard step number. Rejected because configuration can change outside the wizard and invalidate the stored cursor.

### Keep checks bounded and provider-owned

Run all checks will fan out only across registered diagnostic providers with existing timeout and secret-safety guarantees. Missing future diagnostics will be represented explicitly and will not trigger speculative network access. The frontend will render returned summaries and recovery guidance without receiving raw payloads.

Alternative considered: a central diagnostic service that knows every protocol. Rejected because it would duplicate integration ownership and grow into a monolith.

### Exclude OpenEMR from the registry and product surface

The registry will contain only Overview, Medplum, OIE, GDT Bridge, dcm4chee, AP / External Devices, and Deployment & Diagnostics. Tests will assert that OpenEMR is absent from navigation, readiness aggregation, first-run completion, diagnostics orchestration, and extension examples.

Alternative considered: retain a disabled placeholder. Rejected because the user has confirmed OpenEMR will not be used and a placeholder would create a false future contract.

## Risks / Trade-offs

- [Risk] Extracting OIE into a section regresses mature workflows. → Preserve public endpoints and safety controls, migrate incrementally, and retain focused OIE interaction tests.
- [Risk] Readiness becomes a duplicate configuration authority. → Providers remain read-only projections over typed settings and bounded diagnostics; no readiness mutation API is introduced.
- [Risk] Optional sections accidentally block first-run completion. → Encode required/optional metadata server-side and test optional disabled states explicitly.
- [Risk] Run all checks becomes slow or leaks diagnostic data. → Reuse bounded provider timeouts, allow partial results, and enforce secret/PHI canaries in API tests.
- [Risk] Later modules bypass the contract. → Add architecture tests for registration, ownership, and prohibited monolithic imports.

## Migration Plan

1. Introduce the readiness domain/service/API contract and provider registry with compatibility tests.
2. Add the Settings shell, navigation, overview, guided flow, and activation-impact presentation.
3. Extract existing OIE behavior behind the module contract without changing its APIs.
4. Register placeholder shells/readiness for the planned non-OIE integrations, with optional integrations disabled where appropriate.
5. Add Run all checks orchestration, accessibility/responsive coverage, and full regressions.
6. Roll back by restoring the prior Settings entry while leaving the additive readiness endpoint unused; no persisted data migration is required.

## Open Questions

- Which current integrations are mandatory besides the application/deployment foundation? The implementation should encode the smallest required set supported by ZAC-72 acceptance criteria and treat GDT, dcm4chee, and AP as optional.
- Should Medplum initially be required or optional for overall completion? Resolve this in implementation using current product topology and record it in tests.
