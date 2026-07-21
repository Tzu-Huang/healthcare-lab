# Validation Evidence

## Apply verification — 2026-07-20

- `python -m unittest discover -s tests -q`: 518 tests passed; 5 environment-dependent tests skipped.
- Focused lifecycle/client suite: 25 tests passed.
- Focused architecture, repository, lifecycle, and shared-component suite: 77 tests passed.
- `node --check` passed for Settings API, state, view, and application composition modules.
- `python -m compileall -q backend tests` passed.
- `openspec validate implement-safe-managed-channel-lifecycle --strict` passed.
- `git diff --check` passed.

Mocked verification covers classification, preview binding, stale/target substitution, XML update preservation, `override=false`, create retry containment, exact deploy/undeploy/delete targeting, partial delete failure, mapping CAS rollback, audit allowlisting, API rejection of force/override/wildcard inputs, and absence of bulk/adopt/redeploy-all routes and controls.

Live OIE 4.5.2 validation is intentionally deferred to `/dev-test` in a disposable managed-Channel environment. No live mutation was performed during apply, and mocked acceptance criteria were not weakened.
