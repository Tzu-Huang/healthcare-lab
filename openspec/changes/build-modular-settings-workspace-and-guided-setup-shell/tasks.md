## 1. Readiness Contract and Composition

- [x] 1.1 Add closed readiness states, section metadata, activation-impact values, provider ports, and secret-safe aggregate projections.
- [x] 1.2 Implement the readiness aggregation service and provider registry with explicit required/optional completion rules and no OpenEMR registration.
- [x] 1.3 Add bounded readiness providers for the currently supported Settings sections using persisted typed configuration and existing diagnostics.
- [x] 1.4 Expose a stable readiness API and compose it into the application with value-free error handling.
- [x] 1.5 Add domain, service, API, and composition tests covering every readiness state, partial provider failure, completion rules, and secret/PHI canaries.

## 2. Modular Settings Shell

- [x] 2.1 Add the responsive, keyboard-accessible Settings shell and registry-driven navigation for Overview, Medplum, OIE, GDT Bridge, dcm4chee, AP / External Devices, and Deployment & Diagnostics.
- [x] 2.2 Define integration-owned frontend module boundaries for view initialization, API adapters, state, and styling, with architecture tests preventing a new monolithic controller.
- [x] 2.3 Implement Overview readiness cards, bounded next actions, activation-impact labels, safe-local-default explanations, and accessible Advanced disclosures.
- [x] 2.4 Add explicit tests proving OpenEMR is absent from navigation, registrations, readiness, setup progression, diagnostics, and extension fixtures.

## 3. OIE Compatibility Extraction

- [x] 3.1 Move existing OIE connection, result-listener, managed-Channel, preview, and diagnostic presentation behind the OIE Settings module registration.
- [x] 3.2 Preserve existing OIE endpoints, write-only secret behavior, persistence-only listener saves, preview confirmation, and lifecycle concurrency safeguards.
- [x] 3.3 Update focused frontend and integration tests to prove existing OIE Settings workflows remain functional within the new shell.

## 4. Guided Setup and Diagnostics

- [x] 4.1 Implement fresh-instance guided setup and readiness-derived resume behavior without a persisted wizard cursor.
- [x] 4.2 Allow GDT Bridge, dcm4chee, and AP / External Devices to remain disabled without blocking overall completion.
- [x] 4.3 Implement top-level Run all checks orchestration over registered bounded diagnostic providers with partial and unavailable results.
- [x] 4.4 Add frontend tests for first-run, resume, optional disabling, restart-required presentation, Advanced fields, mixed diagnostic outcomes, keyboard navigation, and responsive ownership.

## 5. Documentation and Verification

- [ ] 5.1 Document the Settings registration, readiness-provider, activation-impact, and bounded-diagnostics extension contracts for later integration tickets.
- [ ] 5.2 Run focused readiness, Settings, OIE lifecycle, and architecture tests plus the complete regression suite.
- [ ] 5.3 Run Python compilation, JavaScript syntax checks, `git diff --check`, and strict OpenSpec validation.
