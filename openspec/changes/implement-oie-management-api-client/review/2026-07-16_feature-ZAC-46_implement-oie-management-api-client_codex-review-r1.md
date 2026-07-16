---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-46_implement-oie-management-api-client
base: main
reviewed_head: e16365a1b25d42f8e8d6de31061e904f8937595c
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] Failed LoginStatus responses establish a local authenticated session

- Evidence: `backend/clients/oie_management.py:127-138` treats every 2xx login
  response containing a JSON object as success, sets `_authenticated = True`,
  and never examines the documented `LoginStatus.status`. The official 4.5.2
  model includes `FAIL`, `FAIL_EXPIRED`, `FAIL_LOCKED_OUT`, and
  `FAIL_VERSION_MISMATCH`. A direct scripted response
  `{"status":"FAIL","message":"bad credentials"}` reproduces an authenticated
  client.
- Impact: rejected credentials can be reported as a successful authenticated
  session; subsequent calls then fail under misleading classifications and the
  authentication contract is false.
- Classification: initial blocking correctness/security finding.
- Required resolution: accept only documented successful login states,
  classify all failure states (including version mismatch), keep local state
  unauthenticated on any rejection or malformed status, and add focused tests.

### [P1][REV-002] An invalid TLS mode silently selects insecure certificate handling

- Evidence: `backend/domain/oie_management.py:57-97` does not validate that
  `tls_mode` is an `OieTlsMode`; `backend/clients/oie_management.py:63-69`
  selects verified TLS only by identity comparison and sends every other value
  to `_create_unverified_context()`. Constructing the typed dataclass with
  `tls_mode="verified"` is accepted and reproducibly selects the insecure
  branch.
- Impact: a configuration adapter mistake or unvalidated runtime value can
  disable certificate and hostname verification while appearing to request
  verified TLS, violating the no-automatic-insecure-fallback requirement.
- Classification: initial blocking security finding.
- Required resolution: validate or safely coerce the closed TLS enum at the
  inward contract, reject every unknown value, and make the transport's default
  branch fail closed. Add regression tests for string and unknown values.

### [P2][REV-003] Mutation operations can run before version compatibility is established

- Evidence: `backend/clients/oie_management.py:166-177` provides an optional
  `require_supported_version()` call, but create/update/delete and deployment
  methods at lines 199-231 do not require that gate. A caller can login and
  immediately mutate an unsupported runtime without any
  `unsupported-version` result.
- Impact: callers can rely on and execute a 4.5.2 mutation contract against an
  incompatible server, contrary to the explicit requirement that unsupported
  versions surface before mutation behavior is relied upon.
- Classification: initial P2 blocker because it violates an explicit
  acceptance criterion.
- Required resolution: establish and retain supported-version state before
  mutation, or otherwise make the mutation boundary enforce an equivalent
  explicit gate; cover unsupported versions with zero mutation requests.

### [P2][REV-004] Nominally successful object responses accept semantically empty structures

- Evidence: `backend/clients/oie_management.py:326-342` validates only that a
  response is a JSON object. Empty objects and objects lacking required user,
  system, channel identifier, revision, or status structure are returned as
  successful normalized results. Existing tests cover malformed JSON but not
  semantically incomplete 2xx objects.
- Impact: callers receive success-shaped results without the identifiers and
  revision/status information required for lifecycle coordination, violating
  the explicit malformed-success acceptance criterion.
- Classification: initial P2 blocker because it violates an explicit
  acceptance criterion.
- Required resolution: define operation-specific minimum response invariants
  supported by the recorded 4.5.2 evidence, reject incomplete values as
  `unexpected-response`, and add missing-field/wrong-type tests.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...e16365a1b25d42f8e8d6de31061e904f8937595c`, the
  OpenSpec requirements/design/tasks, production modules, and focused tests.
- The persisted verification round reports 357 full-suite and 16 focused tests
  passing at the reviewed head.
- Reproduced REV-001 and REV-002 with in-process scripted/mocked probes; no
  product files or live OIE resources were changed.
- The concrete read-timeout implementation relies on CPython urllib response
  internals to replace the socket timeout after headers. This remains a
  portability/residual risk but is not an additional blocker for the current
  supported runtime evidence.

## Next Action

`/dev-fix --review "openspec/changes/implement-oie-management-api-client/review/2026-07-16_feature-ZAC-46_implement-oie-management-api-client_codex-review-r1.md"`

Reason: four blocking findings remain.
