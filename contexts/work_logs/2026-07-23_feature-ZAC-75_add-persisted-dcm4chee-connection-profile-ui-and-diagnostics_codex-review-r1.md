---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics
base: main
reviewed_head: 6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | open | Effective secrets are separated from the profile passed to every transport. |
| REV-002 | P1 | open | Enabled readiness is returned as `ready` without using diagnostic state. |
| REV-003 | P1 | open | OAuth2 requires `clientSecret`, but the Settings form cannot submit it. |
| REV-004 | P2 | open | Disabled profiles still execute Patient and Order DICOM workflows. |
| REV-005 | P2 | open | Public profile fields return full mounted private-key and certificate paths. |

## New blocking findings

### [P1][REV-001] Authenticated and TLS profiles are persisted but never applied to transport

`backend/dcm4chee_settings_composition.py:13-20` returns only
`get_effective("dcm4chee").profile`, discarding the separately loaded secrets.
The DICOMweb client builds requests with static Accept/Content-Type headers
(`backend/clients/dcm4chee.py:15-31`, `46-74`, `77-142`) and neither it nor the
diagnostic transport applies `authMode`, username/password, bearer/OAuth
credentials, certificate paths, private keys, or TLS verification settings.

Impact: basic, bearer, OAuth2, and mTLS profiles can be saved and reported as
configured, but ADT/MWL/result/diagnostic operations against an authenticated
external PACS cannot work. This violates the accepted external-profile and
canonical-effective-profile requirements.

Classification: initial blocking correctness/security finding.

Required resolution: construct a secret-safe effective transport configuration
and apply each supported auth/TLS mode consistently to workflow and diagnostic
requests. Add tests proving credentials/certificates are applied without being
returned or logged.

### [P1][REV-002] Settings Overview loses degraded diagnostic state

`backend/settings_readiness_composition.py:170-175` returns `ready` for every
enabled profile without consulting any diagnostic result. The bounded check
path can return `degraded`, but that result is not retained, so a subsequent
`GET /api/settings/readiness` immediately returns `ready` again.

Impact: a profile with partial or completely failed connectivity is presented
as ready, contrary to the explicit scenario requiring Settings Overview to
report `degraded` when one or more independent checks fail.

Classification: initial blocking acceptance finding.

Required resolution: retain a bounded, secret-safe latest diagnostic
assessment (or equivalent local runtime state) and make `assess()` project it
without initiating network I/O. Add a test that runs a partial diagnostic and
then observes degraded readiness through the normal GET endpoint.

### [P1][REV-003] OAuth2 cannot be configured from the Settings UI

The backend requires the `clientSecret` secret for `oauth2`
(`backend/services/integration_settings.py:486-499`), but the form exposes only
password and bearer-token inputs
(`frontend/templates/settings/dcm4chee.html:95-109`) and the payload builder
submits only `password` and `token`
(`frontend/static/js/settings/dcm4chee.js:172-175`).

Impact: selecting OAuth2 always produces a validation failure unless the secret
was seeded out-of-band, so an external OAuth2 PACS profile cannot be entered
from Settings as required.

Classification: initial blocking acceptance finding.

Required resolution: add a write-only OAuth client-secret control, configured
state, payload mapping, validation mapping, and frontend/API coverage.

### [P2][REV-004] Disabled dcm4chee profiles do not disable DICOM workflows

Diagnostics checks `enabled`, but Patient and Order operations do not.
`backend/services/patient_workflow.py:132-144` always invokes Patient ADT sync
for DICOM records, and `backend/services/order_workflow.py:194-200` invokes MWL
sync without checking the effective profile's enabled state.

Impact: an operator can disable the optional integration in Settings while new
Patient/Order actions continue making archive calls and mutating workflow
state. This contradicts the persisted enablement contract and makes the
disabled state operationally misleading.

Classification: initial P2 finding that blocks because it violates the explicit
enabled/disabled behavior of this change.

Required resolution: enforce disabled state at the shared workflow boundary
with a stable, non-network outcome, and cover Patient, Order, retry, fixture,
result, and diagnostic entry points.

### [P2][REV-005] Public projection exposes full mounted credential paths

`backend/services/integration_settings.py:350-365` returns the complete
persisted fields object before adding bounded reference state. That fields
object still contains `security.certificatePath` and
`security.privateKeyPath`, and the frontend repopulates both raw values.

Impact: profile reads disclose container filesystem layout for private-key
material even though the accepted design requires basename-free,
configured/readable reference state and identifies path disclosure as sensitive
infrastructure leakage.

Classification: initial P2 privacy finding that blocks because it violates the
explicit redacted public-projection requirement.

Required resolution: remove mounted credential paths from public fields, expose
only bounded configured/readable state, and make replacement references
write-only/preserve-by-blank like secrets. Add API and frontend canary tests.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...6b79baa0fee8f816a2acb2ae1b0de56b7cb82e7a`
  against the ZAC-75 OpenSpec requirements and changed product/test files.
- The persisted verification round records 68 focused tests and 774 full-suite
  tests passing with one skip, plus Python compile, JavaScript syntax, and
  strict OpenSpec validation.
- Existing tests do not exercise authenticated transport, post-diagnostic
  readiness projection, OAuth client-secret entry, disabled workflow
  suppression, or path-redacted public replacement semantics.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-75_add-persisted-dcm4chee-connection-profile-ui-and-diagnostics_codex-review-r1.md"`

Reason: blocking findings REV-001 through REV-005 remain.
