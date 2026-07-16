## 1. Canonical OIE 4.5.2 Evidence

- [x] 1.1 Rebase after the ZAC-61 export commit is available and inventory every structural and environment-specific field in `Dashboard_to_OIE_to_AP.xml` and `AP_RESULT_TO_LAB.xml`.
- [x] 1.2 Add sanitized canonical fixtures or characterization helpers that remove OIE IDs, revisions, timestamps, user IDs, current display names, and the current AP IP without weakening the required 4.5.2 structure.
- [x] 1.3 Record the exact OIE 4.5.2 wire value for explicit UTF-8 and characterize the fixed TCP Listener, TCP Sender, HL7 v2, and MLLP defaults.

## 2. Managed Channel Domain Contract

- [x] 2.1 Add persistence-neutral typed contracts for the two logical identities, template version, endpoints, timeouts, queue policy, enabled state, and initial state.
- [x] 2.2 Implement actionable validation for private IPv4/internal DNS hosts, ports, timeouts, booleans, and supported states while rejecting schemes, paths, credentials, embedded ports, and unsupported inputs.
- [x] 2.3 Implement managed route-set validation that rejects duplicate listener ports and proves validation has no client, repository, Flask, SQLite, or runtime dependency.
- [x] 2.4 Define and test the machine-readable `Managed by Healthcare Lab` marker independently of Channel display name, OIE ID, and revision.

## 3. Complete OIE Templates

- [x] 3.1 Implement the complete `HLAB_ORM_TO_AP` OIE 4.5.2 payload for `0.0.0.0:6600` to the explicit AP host on port `6671`, preserving MLLP/HL7/UTF-8 defaults and disabled destination queueing.
- [x] 3.2 Implement the complete `HLAB_ORU_TO_HLAB` payload for `0.0.0.0:6661` to `lab-app:6665`, with indefinite 10-second queue/retry, buffer 1000, response-timeout queueing, and 5000 ms send/response timeouts.
- [x] 3.3 Restrict the public template interface to the approved fields and prove arbitrary connectors, extra destinations, filters, transformers, scripts, credentials, and raw payload editing cannot be supplied.
- [x] 3.4 Add canonical serialization tests for both Channel payloads and prove environment-specific fixture identity never leaks into generated templates.

## 4. Normalization and Architecture Safety

- [x] 4.1 Implement deterministic normalized desired-state projections containing only managed identity, endpoint, protocol, charset, timeout, queue, enabled, and initial-state fields.
- [x] 4.2 Add comparison tests proving OIE IDs, revisions, export metadata, timestamps, and user IDs do not create drift while every approved field change remains visible.
- [x] 4.3 Add secret-leakage tests for payloads, normalized output, errors, and representations, plus architecture tests preventing dependencies on persistence, transport, Flask, or runtime modules.

## 5. Verification and Handoff

- [x] 5.1 Run focused domain/template tests, architecture contracts, the complete unittest suite, Python compilation, `git diff --check`, and strict OpenSpec validation without calling a live OIE instance.
- [x] 5.2 Document that AP host persistence remains an explicit prerequisite for ZAC-48 integration and confirm ZAC-46 client, ZAC-49 runtime, ZAC-50 UI, Docker, database, and live Channels remain unchanged.
