## Why

Healthcare Lab has a persistent, secret-safe OIE settings profile but no server-side client for authenticating to and operating the OIE 4.5.2 Management API. This boundary is needed now so connection diagnostics and the later managed Channel lifecycle can be built without coupling HTTP session behavior, OIE-specific failures, or secrets to persistence and UI code.

## What Changes

- Add an OIE 4.5.2 Management API client that logs in, retains and reuses the server-side session cookie, adds the required `X-Requested-With` header, and logs out safely.
- Add current-user, system-information, version-detection, Channel list/get/create/update/delete, deploy/redeploy-all/undeploy, Channel-status, and ports-in-use operations.
- Support verified TLS and an explicitly configured local-lab self-signed mode with bounded connect and read timeouts.
- Introduce one OIE client error model that distinguishes authentication, permission, TLS, connection, timeout, revision-conflict, validation, unsupported-version, server, and malformed-response failures.
- Redact passwords, cookies, authorization material, and other session secrets from logs, exceptions, representations, and returned results.
- Characterize every supported operation and major failure class with mocked transport tests; this change does not require a live OIE runtime.
- Keep the first implementation phase isolated from the OIE settings repository, mapper, Flask API, application composition, managed Channel templates, and lifecycle orchestration so it can proceed in parallel with ZAC-61. Add the narrow settings-to-client composition only after the ZAC-61 ownership changes are integrated.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-management-client`: Define authenticated OIE 4.5.2 Management API operations, session reuse, TLS and timeout behavior, error classification, version targeting, update conflict safety, and secret redaction.

### Modified Capabilities

None.

## Impact

- Affected production areas: a dedicated OIE Management API client, its persistence-neutral configuration and error contracts, and later composition wiring from the existing OIE settings service.
- Affected verification: mocked client/transport tests for all operations, failure mapping, cookie reuse, headers, update defaults, version checks, and secret-safety behavior.
- Dependencies: consumes the completed ZAC-45 settings contract; its isolated client phase may run beside ZAC-61, while settings/composition wiring waits for ZAC-61 integration.
- No database migration, public Settings API change, managed Channel template generation, lifecycle service, listener startup change, UI work, or live OIE mutation is introduced.
