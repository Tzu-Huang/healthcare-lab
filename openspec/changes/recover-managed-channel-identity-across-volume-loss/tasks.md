## 1. Recovery Classification

- [x] 1.1 Extend managed Channel reconciliation with an explicit recoverable identity outcome and bounded evidence for an exact unique marker, logical type, template version, parseable owned payload, and empty local identity.
- [x] 1.2 Validate listener-route ownership against the complete live inventory and block duplicate markers, same-name external Channels, malformed payloads, identity contradictions, and known or ambiguous port claims.
- [x] 1.3 Add pure domain tests for successful recovery classification and every identity and route blocking case without weakening existing external/read-only behavior.

## 2. Atomic Mapping Recovery

- [x] 2.1 Add a single-logical-type expected-empty compare-and-bind repository operation that persists recovered identity and bounded audit evidence atomically while preserving unrelated settings and mappings.
- [x] 2.2 Add repository tests for successful binding, concurrent/stale rejection, repeat idempotence, transaction rollback, and audit payload allowlisting.
- [x] 2.3 Add a guarded lifecycle recovery operation that refreshes complete inventory, revalidates candidate identity and route ownership, and invokes only the atomic mapping bind without OIE mutation.

## 3. Startup Convergence

- [x] 3.1 Sequence recoverable identity binding before existing create-missing handling, refresh classification after binding, and reconcile the two logical types independently.
- [x] 3.2 Preserve the current deployment state of rebound Channels, including deliberately stopped or undeployed Channels, while retaining create-and-deploy behavior for genuinely missing Channels.
- [x] 3.3 Record per-logical-type startup recovery, blocked, stale, and failure outcomes using secret- and PHI-safe bounded metadata.

## 4. Persistence Matrix and Operations

- [x] 4.1 Add service/integration tests for retained/retained, retained/reset, reset/retained, and reset/reset persistence combinations plus repeated-start idempotence and one-type-blocked independence.
- [ ] 4.2 Update bootstrap and OIE operating documentation with recovery behavior, blocked-recovery guidance, stopped-state preservation, and rollback via bootstrap mode `off`.
- [ ] 4.3 Run focused lifecycle/bootstrap/settings tests, the complete regression suite, Python compilation, `git diff --check`, and strict OpenSpec validation.
