## 1. Operational Persistence

- [x] 1.1 Add idempotent SQLite schema for bounded bootstrap run and per-logical-type outcome evidence
- [x] 1.2 Implement a focused bootstrap status repository with atomic start, progress, completion, and interrupted-run projection
- [x] 1.3 Add repository and migration tests for clean install, restart persistence, atomic completion, stale running state, and secret-safe values

## 2. Bootstrap Coordination

- [ ] 2.1 Introduce a coordinator that records startup run state around the existing guarded reconciliation workflow
- [ ] 2.2 Add process-local single-run exclusion and asynchronous Retry execution
- [ ] 2.3 Define closed Retry eligibility and recovery-guidance mappings for timeout, readiness, policy blockers, disabled mode, and unavailable evidence
- [ ] 2.4 Extend bootstrap service tests for timestamps, attempts, created/no-op/recovered/blocked outcomes, interrupted execution, concurrency, and persistence failure

## 3. API and Diagnostics

- [ ] 3.1 Add side-effect-free bootstrap status and explicit Retry API endpoints with stable success, validation, conflict, and unavailable responses
- [ ] 3.2 Add a bootstrap Runtime Diagnostics probe sourced only from bootstrap status
- [ ] 3.3 Return both canonical managed template projections with bounded inventory-unavailable evidence when live OIE inspection fails
- [ ] 3.4 Add API and diagnostic tests proving GET requests never invoke bootstrap or Channel mutation and Retry preserves lifecycle guards

## 4. Settings Workspace

- [ ] 4.1 Add frontend bootstrap status and Retry API functions plus isolated Settings state
- [ ] 4.2 Render bootstrap mode, state, timing, attempts, per-template outcomes, and allowlisted guidance separately from listener state
- [ ] 4.3 Keep both approved managed template cards visible for missing and inventory-unavailable states
- [ ] 4.4 Enable Retry only when eligible and prevent duplicate execution while a run is active
- [ ] 4.5 Add frontend tests for state distinctions, read-only refresh, inventory errors, Retry eligibility, and listener/bootstrap separation

## 5. Automated Verification and Documentation

- [ ] 5.1 Run focused repository, service, API, diagnostics, and frontend test suites and fix regressions
- [ ] 5.2 Update bootstrap configuration and operator recovery documentation without recommending container recreation for ordinary lifecycle failures
- [ ] 5.3 Extend the OIE live verification runbook with exclusive Compose ownership, resolved volume targets, non-PHI evidence fields, and safe cleanup

## 6. Live OIE 4.5.2 Convergence

- [ ] 6.1 Verify clean Compose startup creates and starts exactly two approved managed Channels
- [ ] 6.2 Verify retained-volume restart is a no-op with no duplicate identities or unnecessary revision changes
- [ ] 6.3 Verify one-Channel-missing repair preserves the unchanged Channel
- [ ] 6.4 Verify delayed readiness, timeout visibility, and explicit Retry convergence
- [ ] 6.5 Verify supported local-settings-only, OIE-appdata-only, and combined reset scenarios
- [ ] 6.6 Record the secret- and PHI-safe verification report and repeatable smoke commands
