## Context

ZAC-47 through ZAC-50 established constrained OIE templates, a Management API client, safe lifecycle operations, listener auto-start, and the Settings workspace. The ORU template compiler enables durable destination queueing, but the checked-in canonical XML does not; Docker configuration also reuses one result-port variable for two different endpoints. Runtime status is distributed across the Management API, process-local listener, Compose topology, Channel deployment, and OIE message statistics. Diagnostics must remain useful while excluding credentials and complete PHI-bearing HL7.

## Goals / Non-Goals

**Goals:**

- Preserve an ORU accepted by OIE while lab-app is unavailable and deliver it after recovery.
- Make port ownership and runtime-versus-published endpoints explicit.
- Return layered, independently actionable, bounded diagnostics.
- Make redelivery idempotent and auditable without storing diagnostic PHI.
- Cover locally simulatable outage and recovery behavior with automated tests.

**Non-Goals:**

- Multi-replica listener ownership, HA OIE, a production secret manager, or HLAB pull/fetch.
- Arbitrary OIE Channel editing or exposing full upstream responses.
- Proving external firewall behavior from within the application.

## Decisions

### Use one diagnostic report composed from independent probes

The backend will compose separate Management API, HLAB listener, managed Channel, port-contract, and delivery-state probes. Each probe reports a stable layer, state, category, safe summary, evidence timestamp, and recovery guidance. Partial probe failure will not erase successful evidence from other layers. A single boolean health endpoint was rejected because it cannot identify the responsible layer.

### Treat OIE queueing as the durable boundary

`HLAB_ORU_TO_HLAB` will retain indefinite retry, ten-second intervals, a 1000-message buffer, queue-on-response-timeout, and five-second send/response timeouts. The canonical XML and compiled output will agree. HLAB returns `AA` only after persistence or recognition of an existing idempotency key; transport/application failure remains retryable through OIE.

### Require MSH-10 for supported persisted ORU results

The listener will reject a supported ORU without a usable `MSH-10` using a failure ACK and bounded diagnostic. Reusing the same `MSH-10` returns successful duplicate recognition without inserting another result. A content hash fallback was rejected because semantically repeated results can differ in formatting and distinct messages can share content.

### Separate internal listener ports from host publication

Configuration and documentation will distinguish OIE container listeners (`6600`, `6661`), HLAB container listener (`6665`), OIE Management API container ports, and host-published ports. Channel endpoint or queue changes require Channel apply/redeploy; a changed Compose host-published port requires container recreation. Backward-compatible environment aliases may be read during migration but ambiguous names will not drive two endpoints.

### Persist bounded Settings audit metadata

Settings updates will append an audit event in the same local transaction as the profile mutation. Events contain actor, operation, changed approved field paths, outcome, and timestamp, but never old/new values, password state beyond a non-secret field name, headers, channel payloads, or HL7.

### Prefer OIE API statistics, degrade explicitly when unavailable

Queue/error counts will be queried only through a bounded Management API adapter. Unsupported endpoints or versions produce `unavailable` diagnostics rather than scraping UI pages or claiming zero queued messages.

## Risks / Trade-offs

- [OIE 4.5.2 statistics responses vary by endpoint/version] → isolate parsing in the client and expose unsupported/unavailable distinctly.
- [Rejecting missing MSH-10 is stricter than current acceptance] → document the requirement and return a clear HL7 failure ACK so OIE retains/retries visibly.
- [Indefinite retry can retain poison messages] → expose queued/error state and operator guidance without auto-dropping data.
- [Environment variable migration can surprise existing deployments] → document old/new mappings, preserve safe aliases for one transition, and add Compose contract tests.
- [Diagnostics can accidentally leak upstream content] → allowlist fields and assert that passwords, authorization values, and full HL7 never appear in responses, audits, or routine logs.

## Migration Plan

1. Add audit and diagnostic persistence/API changes with backward-compatible database initialization.
2. Introduce distinct port variables and update Compose examples and documentation while retaining safe legacy interpretation where possible.
3. Align canonical and compiled Channel queue settings; operators preview/apply the managed ORU Channel and redeploy it.
4. Recreate containers only when host-published port mappings changed; otherwise restart/retry the HLAB listener as directed.
5. Roll back application code and managed Channel revision independently; retained queues and audit rows remain compatible.

## Open Questions

- Confirm the exact OIE 4.5.2 message-statistics resource and response shapes available in the managed image.
- Decide the deprecation window, if any, for the ambiguous `OIE_MLLP_RESULT_PORT` environment name.
