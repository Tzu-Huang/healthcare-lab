---
reviewer: codex
mode: closure
round: 2
branch: feature/ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics
base: main
reviewed_head: 4cbe71b2607c63a998d4fa24be0e77d4a10381fe
previous_review: contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r1.md
previous_reviewed_head: 6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | still-open | Auth modes reach DICOMweb and diagnostic HTTP requests through a secret-safe runtime profile, but local TLS/certificate setup failures remain unmapped and mTLS/diagnostic transport behavior lacks regression coverage. |
| REV-002 | P1 | resolved | `_Dcm4cheeProvider` retains only the bounded latest diagnostic assessment and projects degraded readiness without network I/O; a regression test proves degraded then healthy transitions. |
| REV-003 | P1 | resolved | Settings now provides a write-only OAuth client-secret input, configured projection, validation mapping, payload mutation, and API/frontend coverage. |
| REV-004 | P2 | resolved | Shared Patient, Order, retry, fixture, result, verification, evidence, and simulated-return boundaries reject an explicitly disabled profile before transport or workflow mutation. |
| REV-005 | P2 | resolved | Public fields omit certificate/private-key paths, expose only configured/readable projections, and preserve stored paths when blank replacements are submitted; API/frontend canary tests cover the behavior. |

## New blocking findings

None.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed the closure delta `6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a..4cbe71b2607c63a998d4fa24be0e77d4a10381fe` against the prior findings and accepted OpenSpec scope.
- Verification Round 2 pins `4cbe71b2607c63a998d4fa24be0e77d4a10381fe`: Python compile and JavaScript syntax passed; 70 focused tests passed; the full suite passed 779 tests with one non-required skip; strict OpenSpec validation passed.
- `backend/clients/dcm4chee.py:167-174` builds and loads the certificate chain before `urlopen`. A readable malformed certificate, key mismatch, or local SSL setup error raises `ssl.SSLError`/`OSError`; `_send()` at `backend/clients/dcm4chee.py:229-240` maps only `HTTPError` and `URLError`. The raw local exception can therefore escape to server logging with certificate-path or filesystem details, contrary to REV-001's required secret-safe transport outcome.
- `tests/clients/test_dcm4chee_security.py:45-67` covers Basic, Bearer, and OAuth2 headers, but does not prove certificate-chain/context application, bounded TLS setup failure mapping, or that default diagnostic HTTP transport uses the same secured opener.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r2.md"`

Reason: REV-001 remains blocking until TLS setup failures are bounded and mTLS/diagnostic transport behavior is covered by regression tests.
