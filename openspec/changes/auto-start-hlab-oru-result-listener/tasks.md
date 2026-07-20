## 1. Persisted Listener Configuration Boundary

- [x] 1.1 Add and test a narrow private Settings repository projection for listener host, port, MLLP framing, and auto-start without exposing Management API secrets.
- [x] 1.2 Add lifecycle configuration/value comparison helpers that distinguish changed persisted intent from unrelated Settings updates.
- [x] 1.3 Extend Settings API tests so changed listener intent reports reload required while unrelated profile changes do not mutate or mark listener runtime.

## 2. Listener Runtime State and Idempotency

- [x] 2.1 Extend `OieResultListener` with explicit stopped, running, and degraded status plus last-attempted/effective configuration and actionable error state.
- [x] 2.2 Preserve same-configuration Start idempotency and prove repeated calls allocate no duplicate socket or thread.
- [x] 2.3 Handle bind failure, unexpected socket termination, Stop cleanup, and successful retry state transitions with focused runtime tests.
- [x] 2.4 Preserve MLLP framing/unframing, ORU handler invocation, ACK transmission, and receive timestamps through listener regression tests.

## 3. Persisted Lifecycle APIs

- [x] 3.1 Rewire listener Start to load the latest persisted Settings and remove request-body host, port, and MLLP overrides.
- [x] 3.2 Add an explicit Retry operation that reloads persisted Settings, recovers degraded listeners, and rejects changed configuration while a listener is still running.
- [x] 3.3 Keep Stop process-local without changing persisted auto-start intent and expose stable Status responses for stopped, running, and degraded states.
- [x] 3.4 Add service and API tests for Start, repeated Start, Stop, Retry recovery, changed-running configuration, and validation/error response shapes.

## 4. Best-effort Application Auto-start

- [x] 4.1 Add an injectable composition startup boundary that performs exactly one listener auto-start attempt after required application dependencies are available.
- [x] 4.2 Prove enabled defaults bind the persisted `0.0.0.0:6665` intent, disabled auto-start performs no bind, and persisted settings are reapplied after application restart.
- [x] 4.3 Prove a port conflict records degraded listener status while application creation and HTTP routes remain available.
- [x] 4.4 Keep direct application construction and the lazy WSGI entrypoint testable without uncontrolled real-port ownership.

## 5. Settings Reload Reminder

- [x] 5.1 Extend the modular Settings API/state owners to retain whether the saved listener intent is unapplied.
- [x] 5.2 Add the minimal Settings component/view/template/style behavior that shows a persistent Retry/Start-or-restart reminder after a changed listener save without implementing managed-Channel editing.
- [x] 5.3 Clear the reminder only after listener Status confirms that the persisted configuration is running, and verify that browser refresh alone is not presented as a runtime reload.
- [x] 5.4 Add focused frontend interaction tests for changed listener saves, unrelated saves, reminder persistence, and applied-state clearing.

## 6. Regression, Architecture, and Operations

- [x] 6.1 Run existing ORU parse, ACK, persistence, duplicate, Patient/Order matching, unmatched-result, workbench, and API regression coverage.
- [x] 6.2 Update architecture and operator documentation with persisted Settings ownership, temporary Stop semantics, degraded recovery, and the single-process listener limitation.
- [x] 6.3 Verify runtime, service, API, composition, frontend, architecture, full regression, syntax/compile, diff, and strict OpenSpec checks without requiring live OIE or AP services.
- [x] 6.4 Audit the final diff against ZAC-49 scope and record that OIE Channel mutation, multi-replica coordination, HLAB pull/fetch, and unrelated ZAC-50 managed-Channel UI remain unchanged.
