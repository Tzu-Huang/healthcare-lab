## 1. Evidence and Client Contracts

- [x] 1.1 Record authoritative OIE 4.5.2 evidence for login/logout, current-user, system-info, Channel CRUD, deploy/redeploy/undeploy, status, ports-in-use, request headers, encodings, and response shapes before implementing endpoints.
- [x] 1.2 Add focused characterization tests for the persistence-neutral client configuration, authenticated lifecycle, normalized results, error categories, and secret-safe representations without opening network sockets.
- [x] 1.3 Define inward OIE Management configuration, normalized result, version-support, and stable error contracts without Flask, SQLite, repository, mapper, or public Settings JSON dependencies.

## 2. Authenticated Transport Boundary

- [x] 2.1 Add the dedicated `backend/clients/oie_management.py` owner while retaining `backend/clients/oie.py` as the MLLP-only transport.
- [x] 2.2 Implement login, per-client cookie retention and reuse, required `X-Requested-With` behavior, explicit logout cleanup, and unauthenticated-operation protection.
- [x] 2.3 Implement verified TLS and explicitly selected local self-signed mode with bounded connect/read behavior and no automatic insecure fallback.
- [x] 2.4 Centralize redaction for passwords, cookies, authorization values, sensitive headers, URLs, response summaries, exceptions, object representations, and routine logs.

## 3. OIE Inspection and Mutation Operations

- [x] 3.1 Implement current-user and system-information operations with OIE version detection and `4.5.2` support classification.
- [x] 3.2 Implement Channel list/get and Channel-status/ports-in-use operations with normalized identifiers, revisions, and status values.
- [x] 3.3 Implement Channel create and delete primitives using the verified OIE 4.5.2 request and response contracts.
- [x] 3.4 Implement Channel update with `override=false` by default and preserve revision conflict as an explicit non-overriding failure.
- [x] 3.5 Implement deploy, redeploy, and undeploy as exact caller-selected primitives without lifecycle sequencing or ownership decisions.

## 4. Failure Mapping and Phase A Verification

- [x] 4.1 Map authentication, permission, TLS, connection, timeout, revision-conflict, validation, unsupported-version, server, and malformed-response failures to stable client errors.
- [x] 4.2 Add mocked request-shape and response tests for every supported operation, session isolation/reuse, headers, encodings, status handling, and cleanup.
- [x] 4.3 Add exhaustive failure and secret-leakage tests proving credentials, cookies, authorization material, and complete sensitive bodies never appear in public strings, results, representations, or captured logs.
- [x] 4.4 Run focused domain/client tests, architecture dependency tests, Python compilation, `git diff --check`, and strict OpenSpec validation with no live OIE access.
- [x] 4.5 Confirm Phase A did not modify the protected ZAC-61 integration files, settings/schema/public contracts, managed templates, lifecycle services, listener runtime, APIs, or frontend assets.

## 5. Post-ZAC-61 Integration

- [x] 5.1 After ZAC-61 is merged, rebase the ZAC-46 branch and review the final OIE settings validation, mapper, repository, and compatibility ownership before wiring composition.
- [x] 5.2 Add the narrow settings-to-client configuration adapter/factory, conservatively mapping the existing persisted timeout to bounded client behavior without changing `/api/oie/settings`.
- [x] 5.3 Wire the client at the composition boundary for later service consumption without performing login, diagnostics, or Channel mutation during application startup.
- [x] 5.4 Add focused composition tests proving the configured password reaches only client construction, public settings remain secret-safe, and no database or live OIE dependency is required by client tests.
- [ ] 5.5 Run the complete regression suite and final architecture/OpenSpec checks, recording that ZAC-47 templates, ZAC-48 lifecycle orchestration, ZAC-49 listener behavior, and ZAC-50 UI remain out of scope.
