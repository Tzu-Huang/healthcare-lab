---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-73_add-persisted-medplum-connection-and-oauth-setup
base: main
reviewed_head: 947ecb8bdba16c26389a8279f6de922427d685bf
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] Normal workflow failures persist and return upstream FHIR bodies

`backend/clients/medplum.py:127-128`, `backend/clients/medplum.py:169-171`, and
`backend/clients/medplum.py:215-224` embed upstream token or FHIR response bodies
in `UpstreamFhirError`. Normal workflow paths then copy that text and payload
into durable sync attempts and user-facing results at
`backend/services/fhir_workflow.py:157-162` and
`backend/services/fhir_workflow.py:353-388`.

Impact: an upstream OperationOutcome, resource body, echoed credential, token,
or authorization value can be persisted and returned by Patient, Order,
preview, or synchronization workflows. This violates the explicit requirement
that credentials, tokens, authorization headers, and FHIR resource bodies never
appear in logs, errors, audits, APIs, or diagnostics.

Classification: initial blocking privacy finding.

Required resolution: translate Medplum boundary failures to bounded,
allowlisted messages before they enter workflow state or API responses, avoid
persisting raw upstream response payloads, retain only safe status/category
metadata needed for retry behavior, and add canary regression coverage for
normal workflow failures in addition to diagnostic-only tests.

### [P2][REV-002] Medplum validation errors are not mapped to their owning controls

`frontend/static/js/settings/medplum.js:101-116` handles a rejected save only by
rendering `error.message` in the shared result paragraph. It never consumes the
backend's structured validation issues or associates an issue with
`baseUrl`, `webUiUrl`, `tokenUrl`, `authGraceSeconds`, or `timeoutSeconds`.

Impact: invalid typed input does not satisfy the explicit Settings acceptance
criterion requiring stable field errors to be mapped to the owning controls.
Operators receive only a generic save failure.

Classification: initial P2 finding that blocks because it violates an explicit
acceptance criterion.

Required resolution: preserve the structured validation response in the API
client, render each issue at or associate it with its owning input (including
accessible invalid state), clear stale errors on resubmission/success, and add
focused interaction tests for field mapping.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...947ecb8bdba16c26389a8279f6de922427d685bf`
  against the ZAC-73 proposal, design, tasks, and four delta specifications.
- The prior verification record reports focused backend, frontend,
  architecture/static, OpenSpec, and full-suite success at the same commit.
- Passing tests do not cover the normal-workflow sensitive-body path or
  field-level browser validation behavior identified above.
- No product-code or test changes were present in the worktree during review.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-73_add-persisted-medplum-connection-and-oauth-setup_codex-review-r1.md"`

Reason: `REV-001` and `REV-002` are blocking findings.
