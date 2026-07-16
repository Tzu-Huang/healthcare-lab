## Context

Operators currently create the two required OIE 4.5.2 Channels from exports named `Dashboard_to_OIE_to_AP` and `AP_RESULT_TO_LAB`. The exports prove the complete TCP Listener, TCP Sender, MLLP, HL7 v2, timeout, metadata, and serialization structure, but they contain environment-specific OIE IDs, revisions, timestamps, display names, and the current AP address `192.168.30.15`. They also leave the ORU destination queue disabled and use `DEFAULT_ENCODING`, while ZAC-47 requires resilient queue/retry and explicit UTF-8 defaults.

ZAC-45 persists Management API, result-listener, and managed Channel mapping data but does not yet persist the AP destination host. ZAC-46 owns Management API transport and deliberately does not construct Channels. ZAC-61 is adding the two exports to the repository and is concurrently finalizing OIE domain/template ownership. ZAC-47 therefore remains a pure offline compiler and must not wire persistence, transport, runtime, or application composition.

## Goals / Non-Goals

**Goals:**

- Compile exactly two complete OIE 4.5.2 Channel payloads with fixed connector topology and narrow approved inputs.
- Preserve the proven export structure while removing runtime identity and environment-specific data.
- Identify managed Channels independently of display name and OIE-generated Channel ID.
- Validate endpoint values and cross-template listener-port conflicts before transport use.
- Provide deterministic normalized state suitable for ZAC-48 preview and drift comparison.
- Guarantee that generated and normalized data cannot contain Management API credentials.

**Non-Goals:**

- A generic Channel, connector, transformer, filter, or raw XML/JSON builder.
- Persistence or UI for the configurable AP host.
- Calling OIE, assigning deployed Channel IDs/revisions, or performing lifecycle actions.
- Starting the HLAB listener or testing live message delivery.
- Implementing ZAC-48 through ZAC-52 behavior.

## Decisions

### Treat checked-in OIE 4.5.2 exports as canonical structural evidence

The template renderer will derive its complete required structure from `docs/Dashboard_to_OIE_to_AP.xml` and `docs/AP_RESULT_TO_LAB.xml` once the ZAC-61 source commit is merged or otherwise made available. Tests will compare generated payload structure with sanitized canonical fixtures and will explicitly assert every owned field. Copying the files into this proposal branch before ZAC-61 lands is rejected because it would create divergent ownership and merge conflicts.

### Compile two named recipes instead of exposing a generic builder

The OIE display names are `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB`, matching the Linear contract. Stable logical types such as `hlab-orm-to-ap` and `hlab-oru-to-hlab`, template version `1`, and a machine-readable `Managed by Healthcare Lab` description marker establish ownership even if a later operator changes a display name. Callers cannot select arbitrary connector classes, extra destinations, filters, transformers, or scripts.

### Keep AP host explicit and persistence-neutral

The ORM recipe requires an `ap_host` input suitable for a private IPv4 address or internal DNS hostname and defaults its destination port to `6671`. The current `192.168.30.15` address is fixture evidence, not a product constant. URL schemes, embedded ports, credentials, paths, whitespace, and empty values are rejected. Adding AP endpoint fields to the persisted Settings contract is deferred, but ZAC-48 cannot integrate the template until an explicit Settings source exists.

### Make ORU delivery resilience mandatory and bounded by the ticket

`HLAB_ORU_TO_HLAB` fixes the destination to `lab-app:6665`, enables the OIE destination queue, retries indefinitely every 10 seconds, retains a queue buffer of 1000, and queues response timeouts. Send and response timeouts remain 5000 ms. `HLAB_ORM_TO_AP` keeps queueing disabled because ZAC-47 only mandates downtime protection for OIE-to-HLAB results; broadening ORM delivery policy requires a separate decision.

### Separate wire payloads from normalized desired state

The renderer returns a complete OIE 4.5.2 payload, while a separate normalization projection includes only Healthcare Lab-owned identity, endpoint, MLLP, charset, timeout, queue, enabled, and initial-state values. OIE IDs, revisions, export timestamps, user IDs, and other server-managed fields are excluded so ZAC-48 does not report false drift. Stable key ordering and primitive values make previews and deep comparisons deterministic.

### Validate the pair as one managed route set

Each recipe validates host, port, timeout, boolean, and enum-like values without Flask, SQLite, client, or runtime dependencies. A route-set validator additionally rejects duplicate listener ports, including caller overrides, because conflicts are a relationship between templates rather than a property of one Channel.

## Risks / Trade-offs

- [Risk] The exports arrive through ZAC-61 rather than `main`. -> Require ZAC-47 apply to rebase after the export commit is available and never duplicate the files in parallel.
- [Risk] OIE may serialize harmless server-managed defaults differently after create/get. -> Compare normalized owned fields for drift and reserve full structural fixtures for renderer compatibility tests.
- [Risk] `DEFAULT_ENCODING` in the exports may reflect a runtime default rather than explicit UTF-8. -> Render the OIE 4.5.2 value that explicitly selects UTF-8 and test the wire field instead of inheriting an installation default.
- [Risk] AP host persistence is absent from ZAC-45. -> Keep the compiler input explicit and record the integration dependency; do not fall back to the current IP or an unrelated environment variable.
- [Risk] Infinite retry can accumulate messages during extended downtime. -> Preserve the agreed queue buffer and leave operational diagnostics/retention hardening to ZAC-51.

## Migration Plan

1. Make the ZAC-61 XML evidence available to the ZAC-47 branch and verify it is unchanged from the operator exports.
2. Add pure domain/template modules and characterization fixtures without application wiring.
3. Add deterministic validation, serialization, normalization, and dependency tests.
4. Leave existing manually configured OIE Channels and runtime behavior unchanged.

Rollback removes the new pure modules and tests; no database, live OIE Channel, runtime, or user data is changed.

## Open Questions

- Which later change will add the AP host/port fields to persistent OIE Settings before ZAC-48 composition: a bounded ZAC-48 prerequisite or an explicit amendment to the Settings profile capability?
