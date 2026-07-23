## Context

ZAC-67 introduced a bounded startup coordinator that inspects the complete OIE inventory and creates/deploys only Channels classified as `Missing`. Managed identity is split between local SQLite mapping rows and OIE appdata. Current reconciliation intentionally treats a valid marked Channel without a local mapping as `Conflict`, preventing unsafe adoption but also preventing recovery after local-volume loss.

ZAC-68 must distinguish recovery from adoption. The system may bind an existing Channel only from strong, unique ownership evidence and must retain the existing external/read-only boundary. Recovery also has to compose with the existing guarded create/deploy workflow, compare-and-update persistence, asynchronous startup, and bounded audit contract.

## Goals / Non-Goals

**Goals:**

- Converge safely for all four combinations of retained/reset local DB and OIE appdata.
- Recover exactly one canonical mapping from a uniquely marked, valid, route-compatible live Channel.
- Recreate only a mapped Channel proven absent from OIE.
- Preserve a recovered Channel's deployment state and make restart behavior idempotent.
- Block ambiguous or contradictory evidence without mutating any candidate.
- Persist bounded recovery evidence without credentials, payloads, HL7, or PHI.

**Non-Goals:**

- Recover OIE message history after appdata deletion.
- Adopt unmarked Channels or infer ownership from display names.
- Automatically correct configuration drift or redeploy existing Channels.
- Coordinate recovery across multiple lab-app processes, hosts, or replicas.

## Decisions

### Model recovery as a distinct conservative reconciliation outcome

Domain reconciliation will distinguish a uniquely recoverable unmapped Channel from ordinary `Missing` and `Conflict` states. A candidate is recoverable only when its exact marker identifies the expected logical type and template version, its complete owned payload is parseable, it is unique for that logical type, no contradictory mapped identity exists, no same-name external collision exists, and its listener route is not claimed by another Channel.

Alternative considered: reinterpret every `unmapped-managed-marker` as `Unchanged`. Rejected because ownership has not yet been durably rebound and bootstrap could incorrectly treat ambiguous evidence as a normal no-op.

### Recover mappings before create-missing mutation

After the first complete authenticated inventory read, bootstrap will process each logical type independently. A recoverable snapshot is bound atomically, inventory is refreshed, and the rebound Channel is then expected to classify as unchanged or drifted. Existing create/deploy handling runs only for a genuine `Missing` snapshot. A recovery blocker for one logical type does not prevent safe reconciliation of the other.

Alternative considered: allow the create preview to recover mappings implicitly. Rejected because creation and identity recovery have different authorization evidence and remote mutation semantics.

### Bind with an expected-empty compare-and-update contract

The settings repository will expose a single-logical-type compare-and-bind operation that succeeds only when the current mapping identity is empty and the expected canonical intent still matches. It writes the observed Channel ID, name, template version, and revision together with the recovery audit event in one transaction. A concurrent or stale mapping change fails closed and triggers no OIE mutation.

Alternative considered: replace the full settings profile. Rejected because it broadens the write surface and risks overwriting unrelated operator settings or the other mapping.

### Validate identity and route ownership from the complete live payload set

Candidate selection will use the machine-readable description marker rather than Channel name. Marker-looking payloads must normalize successfully. Route ownership validation will compare the candidate's owned listener endpoint against every other live Channel with a parseable listener route; an unknown or conflicting claimant blocks recovery. Same-name external Channels remain explicit blockers even if one valid marked candidate also exists.

Alternative considered: validate only the two managed candidates. Rejected because an external Channel may already own the listener port and recovery must not claim an unsafe route.

### Preserve live state and record recovery separately from deployment

Binding an existing Channel does not call deploy, redeploy, undeploy, update, or delete. Its observed state is retained, including `STOPPED` or undeployed. Recovery and blocked recovery use bounded startup audit metadata so operators can distinguish rebinding from creation.

Alternative considered: deploy recovered Channels to converge with template initial state. Rejected because a stopped Channel may represent deliberate operator intent.

## Risks / Trade-offs

- [Risk] Older or manually edited managed payloads cannot be normalized. -> Block recovery and require explicit operator resolution rather than weakening ownership proof.
- [Risk] Inventory changes between classification and persistence. -> Refresh/revalidate immediately before an expected-empty atomic bind and fail closed on stale evidence.
- [Risk] Listener ownership cannot be extracted from an external payload. -> Treat uncertainty as a blocker when it could affect a desired managed port.
- [Risk] One logical type is blocked while the other is safe. -> Reconcile independently and report per-type outcomes without widening mutation scope.
- [Risk] Recovery succeeds but audit persistence fails. -> Keep mapping and audit in one transaction so the bind is not claimed without durable evidence.

## Migration Plan

1. Extend pure inventory reconciliation and tests with recoverable identity and route-ownership evidence.
2. Add the atomic expected-empty mapping bind and recovery audit contract.
3. Sequence guarded recovery before existing create-missing behavior in the startup coordinator.
4. Add persistence-matrix, blocker, state-preservation, retry, and idempotence tests plus operator documentation.
5. Roll back operationally with bootstrap mode `off`; existing mappings and OIE Channels remain usable through manual lifecycle controls.

## Open Questions

None. This proposal chooses a distinct recoverable state, expected-empty atomic rebinding, fail-closed route validation, and independent per-logical-type convergence.
