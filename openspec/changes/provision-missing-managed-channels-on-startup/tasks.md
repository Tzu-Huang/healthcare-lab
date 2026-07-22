## 1. Configuration and Desired Mapping Intent

- [x] 1.1 Add validated `create-missing` and `off` bootstrap mode configuration with positive bounded timeout and retry interval defaults, environment examples, and configuration tests.
- [x] 1.2 Extend repeatable OIE settings maintenance to seed complete empty-identity mappings for both canonical routes without overwriting existing profile or mapping values.
- [x] 1.3 Add repository and migration tests for fresh databases, existing profiles with no mappings, partial mappings, operator-edited mappings, and preserved workflow records.

## 2. Guarded Bootstrap Coordination

- [ ] 2.1 Make lifecycle audit actor selection explicit and bounded while preserving `local-operator` for existing API flows and the current secret-safe allowlist.
- [ ] 2.2 Implement a runtime-neutral startup bootstrap coordinator with injected clock/sleeper and Management API/lifecycle dependencies, finite readiness retry, and bounded safe outcomes.
- [ ] 2.3 Sequence fresh guarded create, identity readback/persistence, fresh guarded deploy, and started-status verification independently for each missing canonical Channel.
- [ ] 2.4 Implement terminal no-mutation handling for unchanged, stopped unchanged, drifted, conflicted, and external inventory, and stop replay after uncertain mutation or persistence failure.
- [ ] 2.5 Add focused coordinator and lifecycle tests for clean, restart no-op, partial pair, delayed readiness, timeout, unsupported/authentication failure, drift, conflict, partial failure, audit actor, and secret-safe evidence.

## 3. Runtime Integration

- [ ] 3.1 Compose and expose one bootstrap coordinator per concrete application and start one named daemon worker only when runtime activation and `create-missing` mode are enabled.
- [ ] 3.2 Adjust the production WSGI startup boundary so concrete runtime activation occurs before the first browser request while factory tests can continue using `activate_runtime=False`.
- [ ] 3.3 Add integration tests proving one bootstrap start per runtime, no start in `off` or runtime-disabled modes, non-blocking HTTP availability, and failure isolation from lab-app health.

## 4. Deployment Documentation and Verification

- [ ] 4.1 Document bootstrap mode, timeout, retry interval, one-worker constraint, startup evidence, manual recovery, and rollback-by-`off` in `.env.example`, Compose guidance, and OIE operating documentation.
- [ ] 4.2 Verify clean Compose startup creates and starts both routes, ordinary restart performs no mutation, and partial setup creates only the absent member using bounded secret-safe evidence.
- [ ] 4.3 Run focused bootstrap/settings/lifecycle tests, the complete regression suite, Python compilation, `git diff --check`, and strict OpenSpec validation.
