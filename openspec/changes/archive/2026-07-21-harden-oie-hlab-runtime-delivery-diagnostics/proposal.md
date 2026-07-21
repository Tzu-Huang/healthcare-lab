## Why

The AP-to-OIE-to-HLAB result path must preserve accepted ORU messages while Healthcare Lab is temporarily unavailable and must make failures diagnosable without exposing credentials or PHI. The existing queue template, listener lifecycle, result persistence, and Settings workspace provide the foundation, but their runtime port contract, recovery evidence, diagnostic coverage, and Settings audit behavior are not yet complete or consistently documented.

## What Changes

- Make the managed `HLAB_ORU_TO_HLAB` Channel and its canonical export consistently queue failed or timed-out deliveries and retry them after `lab-app:6665` returns.
- Separate OIE listener host-publication settings from the HLAB result-listener settings so ports `6600`, `6661`, and `6665` have one unambiguous runtime meaning.
- Add secret- and PHI-safe Settings diagnostics for Management API reachability, HLAB listener state, managed Channel deployment, port conflicts, Docker endpoint guidance, and OIE destination queued/error conditions where the API exposes them.
- Strengthen HLAB result redelivery behavior and automated failure/recovery coverage around message-control identifiers, ACK handling, listener downtime, and retry delivery.
- Record bounded Settings mutation audit events alongside the existing managed Channel lifecycle audit events.
- Document which changes require Channel redeploy and which host-published port changes require container recreation.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-runtime-diagnostics`: Layered, safe diagnostics for the OIE Management API, HLAB result listener, managed Channel deployment, runtime ports, and destination delivery state.

### Modified Capabilities

- `healthcare-lab-oie-managed-channel-templates`: Require the canonical and compiled ORU Channel definitions to share the durable queue, timeout, retry, MLLP, and ACK contract.
- `healthcare-lab-oie-settings-profile`: Give OIE and HLAB ports unambiguous configuration meanings and add bounded, secret-safe Settings mutation audit records.
- `healthcare-lab-oie-settings-workspace`: Present layered diagnostics, recovery guidance, queue/error state, and container-recreation versus Channel-redeploy guidance.
- `healthcare-lab-patient-centered-oie-console`: Strengthen idempotent inbound ORU redelivery behavior and define the response to messages without a usable message-control identifier.

## Impact

Affected areas include the managed OIE Channel templates and canonical XML, Management API client/service projections, OIE Settings persistence and UI, HLAB MLLP result listener and result repository, Docker Compose environment/port documentation, audit schema or repository methods, and focused unit/integration failure-recovery tests. No high-availability design, production secret-manager integration, or pull-based HLAB workflow is introduced.
