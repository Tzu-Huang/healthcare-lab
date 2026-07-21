## 1. Runtime Port and Channel Contract

- [x] 1.1 Split ambiguous OIE host-publication and HLAB listener environment settings, preserve an explicitly bounded migration path, and add Compose contract tests.
- [x] 1.2 Align the canonical and compiled `HLAB_ORU_TO_HLAB` XML queue, retry, timeout, MLLP, and ACK-validation settings.
- [x] 1.3 Add template tests proving connection failure and response timeout remain queueable and ORM queue behavior remains unchanged.

## 2. Idempotent HLAB Result Delivery

- [x] 2.1 Require and validate a non-empty `MSH-10` before supported ORU persistence and return a bounded failure ACK when it is absent.
- [x] 2.2 Make duplicate `MSH-10` redelivery return a successful duplicate-recognition ACK without inserting another result.
- [x] 2.3 Add repository, service, and listener tests for first delivery, duplicate delivery, missing control ID, persistence failure, ACK failure, and listener recovery.

## 3. Layered Runtime Diagnostics

- [x] 3.1 Add bounded Management API client support for managed Channel deployment and destination queued/error statistics with explicit unsupported/unavailable results.
- [x] 3.2 Implement a diagnostic service that independently composes Management API, HLAB listener, Channel deployment, port-contract, and delivery-state probes.
- [x] 3.3 Expose a secret- and PHI-safe diagnostics API with stable categories, timestamps, and recovery guidance.
- [x] 3.4 Add tests for partial probe failure, unavailable statistics, port conflicts, deployment failures, listener degradation, and sensitive upstream error redaction.

## 4. Settings Audit and Workspace

- [x] 4.1 Add append-only bounded Settings mutation audit persistence in the same transaction as successful profile updates.
- [x] 4.2 Add audit tests proving changed field paths are recorded while values, credentials, PHI, HL7, and arbitrary payloads are excluded.
- [x] 4.3 Add the layered diagnostic presentation to Settings, including distinct zero/unavailable delivery state and per-layer recovery guidance.
- [x] 4.4 Add frontend coverage for diagnostics, safe errors, and Apply/Redeploy versus Retry/restart versus container-recreation guidance.

## 5. Documentation and End-to-End Verification

- [x] 5.1 Document Docker service-name versus host-published-port behavior and the `6600`, `6661`, `6665`, HTTP, and HTTPS contracts.
- [x] 5.2 Document which endpoint changes require Channel Apply/Redeploy, listener Retry/restart, or Docker container recreation.
- [x] 5.3 Add locally simulatable outage/recovery tests proving accepted ORUs remain retryable, deliver after listener recovery, and do not create uncontrolled duplicates.
- [x] 5.4 Run focused OIE suites, the full automated suite, syntax/compile checks, secret/PHI leakage assertions, and strict OpenSpec validation.
