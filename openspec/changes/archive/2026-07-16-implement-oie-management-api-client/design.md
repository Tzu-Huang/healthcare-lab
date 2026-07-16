## Context

ZAC-45 established the persisted OIE connection profile, including a write-only password, base URL, TLS mode, and request timeout. The application currently has only an OIE MLLP sender in `backend/clients/oie.py`; it has no authenticated HTTP boundary for the OIE 4.5.2 Client API. ZAC-48 will later coordinate managed Channel lifecycle operations, but it must not own cookies, request encoding, OIE response parsing, or transport failure classification.

This proposal is intentionally split around ZAC-61. Phase A creates a persistence- and framework-neutral client from `main`, while ZAC-61 moves OIE settings validation and presentation to their final owners. Phase B rebases after ZAC-61 and adds only the narrow settings-to-client composition seam. The implementation must use mocked transports and must not access a live OIE runtime during apply or test.

## Goals / Non-Goals

**Goals:**

- Provide one typed, testable owner for OIE Management API authentication and operations.
- Preserve one authenticated cookie session across sequential calls and close it explicitly.
- Model TLS, bounded timeouts, OIE version targeting, response parsing, and actionable failures without Flask or SQLite dependencies.
- Make safe update behavior explicit, including `override=false` by default.
- Prevent passwords, cookies, authorization material, and sensitive response metadata from escaping through logs, exceptions, or result objects.
- Keep ZAC-46 parallel-safe with ZAC-61 and leave orchestration to later OIE services.

**Non-Goals:**

- Generate managed Channel payloads or determine Channel ownership.
- Implement create/update/deploy workflows, previews, audit persistence, UI, or listener lifecycle.
- Change the persisted settings schema or public `/api/oie/settings` JSON contract.
- Add a generic OIE Administrator replacement or support arbitrary OIE versions.
- Exercise a real OIE instance in automated verification.

## Decisions

### Isolate Management HTTP from the existing MLLP client

Add `backend/clients/oie_management.py` for the session-based HTTP API and retain `backend/clients/oie.py` as the MLLP transport owner. Shared OIE-independent transport abstractions are permitted only when they reduce test coupling without mixing the two protocols.

Combining both transports in `oie.py` was rejected because cookie sessions, XML/form encoding, TLS, and management failures are unrelated to MLLP framing and ACK handling.

### Define persistence-neutral configuration and domain errors

The client accepts an explicit immutable configuration containing base URL, username, password, TLS verification mode, connect timeout, and read timeout. It does not read `OieSettingsRepository`, Flask configuration, environment variables, or application extensions. OIE client errors live in an inward domain-owned module and carry a stable category plus redacted actionable detail.

Passing the persisted profile dictionary directly was rejected because it would couple transport behavior to API presentation keys that ZAC-61 is actively moving. Exposing raw transport exceptions was rejected because callers could not reliably distinguish remediation paths and exception text may contain secrets or URLs with sensitive material.

### Use an injectable cookie-aware synchronous transport

Use a synchronous cookie-aware HTTP transport because Healthcare Lab's current services are synchronous and OIE authentication is session based. The concrete transport must retain cookies between requests, add `X-Requested-With`, apply TLS policy, and enforce bounded connection/read behavior. Tests inject a scripted transport or opener so every request and response is deterministic and no network socket is opened.

Adding an async stack or new HTTP dependency is rejected unless implementation exploration proves the standard runtime cannot satisfy a required, testable OIE 4.5.2 behavior and the scope is explicitly re-approved. Endpoint paths, methods, accepted content types, login/logout form details, and response shapes must be verified against OIE 4.5.2 official source or runtime API evidence before being encoded.

### Keep protocol parsing at the client boundary and return normalized results

The client owns OIE-specific request serialization and response parsing. It returns normalized domain/client result values rather than raw cookie jars, response objects, or unbounded response bodies. XML or JSON parsing must reject malformed or semantically incomplete success responses as an unexpected-response error.

Returning raw response objects was rejected because it leaks transport details into ZAC-48 and makes redaction and version checks inconsistent.

### Make authentication and update safety explicit

Login establishes the session; subsequent operations require that authenticated state and reuse it. Logout is safe to call during cleanup and clears local session state even when the remote logout fails. Channel update passes `override=false` unless a caller explicitly requests otherwise; ZAC-46 exposes the flag but never chooses an automatic override policy. Revision-conflict responses are classified and returned to the future lifecycle service without retrying as an override.

Implicit login before every operation was rejected because it obscures session lifetime and increases credential exposure. Automatic conflict override was rejected because it violates ZAC-48's ownership and safety requirements.

### Centralize secret redaction

Sensitive request headers, password fields, cookies, session identifiers, and authorization values are redacted before diagnostic text is constructed. Configuration and client representations must not include password values. Error mapping uses bounded summaries and never embeds complete response bodies.

Relying only on callers to avoid logging client objects was rejected because the client is the only layer that knows every OIE-specific secret location.

### Integrate composition only after ZAC-61

Phase A is limited to the client, inward configuration/error contracts, and mocked tests. It must not modify `backend/repositories/oie_settings.py`, `backend/mappers/oie.py`, `backend/lab_store.py`, `backend/app_factory.py`, `backend/api/oie.py`, or frontend assets. After ZAC-61 is merged, Phase B rebases and adds a narrow factory/adapter from the final OIE settings owner to the client configuration, plus focused composition tests.

If Phase A cannot proceed without changing one of those protected files or changing the settings contract, implementation stops for integration rather than creating a temporary duplicate owner.

## Risks / Trade-offs

- [OIE 4.5.2 operations are not conventional JSON REST endpoints] → Verify exact paths, verbs, form/XML encodings, response status semantics, and version fields against authoritative 4.5.2 evidence and freeze them in request-shape tests.
- [Cookie behavior can leak authentication state across tests or callers] → Give each client its own cookie store, expose explicit login/logout lifecycle, and assert isolation and cleanup.
- [Transport exception strings may expose secrets] → Map failures through a centralized redactor and assert forbidden values are absent from all public strings and representations.
- [A single persisted timeout currently exists while the client distinguishes connect/read bounds] → Phase B maps the existing timeout conservatively to both bounds unless a later settings ticket explicitly changes the public contract.
- [Parallel development can conflict with ZAC-61 OIE ownership changes] → Enforce the Phase A protected-file list, use a separate worktree, and rebase before composition wiring.
- [Mocked tests can diverge from the real runtime] → Keep live verification out of this ticket but record authoritative request/response evidence; ZAC-52 remains the real-runtime gate.

## Migration Plan

1. Implement and verify the isolated client and error contracts on the ZAC-46 worktree without application wiring.
2. Merge ZAC-61, rebase ZAC-46, and resolve only ownership/import changes.
3. Add the final settings-to-client configuration adapter and composition characterization tests without changing the public settings response.
4. Make the client available to ZAC-48; do not activate automatic mutations or startup calls.

Rollback removes the unused client/composition binding. No schema, stored data, managed Channel, or live OIE rollback is required.

## Open Questions

- Which exact OIE 4.5.2 source or runtime API artifact will be recorded as evidence for each endpoint and response shape during implementation?
