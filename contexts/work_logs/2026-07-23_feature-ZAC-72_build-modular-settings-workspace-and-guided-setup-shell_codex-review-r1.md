---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-72_build-modular-settings-workspace-and-guided-setup-shell
base: main
reviewed_head: 2dfd36232405fb6f518f5eb106ac37c7aea06194
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | open | A fresh database returns `complete: true` with every required section `ready`. |
| REV-002 | P2 | open | Sections without check providers are projected as readiness results instead of unavailable checks. |
| REV-003 | P1 | open | The frontend registry has metadata only and cannot register integration-owned view/API/state/style modules. |

## New blocking findings

### [P1][REV-001] Fresh instances are incorrectly reported as fully ready

`backend/settings_readiness_composition.py:36-40` marks Medplum ready from
`enabled` and `baseUrl` alone. Lines 55-77 mark OIE ready when seeded fields
exist even if the desired auto-start listener is stopped, and lines 128-132
unconditionally mark Deployment ready. The default OIE password is also seeded
as `admin` (`backend/config.py:26`).

Creating a brand-new database at the reviewed head and requesting
`GET /api/settings/readiness` returns `complete: true`, `nextAction: null`, and
`ready` for Medplum, OIE, and Deployment while runtime activation is disabled.
This defeats the first-run flow and violates the explicit requirement that
readiness derive from persisted configuration and bounded diagnostics rather
than non-empty/default fields alone.

Classification: initial blocking correctness finding.

Required resolution: introduce authoritative fresh/setup evidence and bounded
health/runtime evidence for required providers. A fresh instance must expose at
least one required `needs-setup` or `degraded` state and a next action until the
required setup contract is genuinely satisfied. Add a fresh-database API test
that asserts overall completion is false.

### [P2][REV-002] Run all checks reports readiness for integrations with no check provider

`backend/services/settings_readiness.py:84-94` falls back from a missing
`check()` method to `provider.assess()`. Consequently,
`POST /api/settings/readiness/checks` reports Medplum and Deployment as
`ready`, and optional placeholder integrations as ordinary `disabled`
readiness results, even though none supplies a bounded diagnostic provider.

This violates the explicit acceptance scenario requiring a section without a
diagnostic provider to be reported as unavailable or disabled without an
invented probe. It also makes the UI claim that checks completed for providers
that were never checked.

Classification: initial P2 blocker because it violates an explicit
requirement.

Required resolution: model diagnostic availability separately from readiness.
Invoke only registered checks, return an explicit bounded unavailable/disabled
check result for absent providers, and add service/API tests proving no
readiness assessment is presented as a completed diagnostic.

### [P1][REV-003] The frontend does not implement the promised integration module contract

`frontend/static/js/settings/registry.js:1-9` registers only `id`, `label`, and
`required`. `frontend/static/js/views/settings.js:1-6` special-cases OIE and the
workspace through direct imports, while
`frontend/templates/views/settings.html` hardcodes every section panel.
There is no registration surface for an integration-owned view initializer,
API adapter, state owner, or styling owner.

The primary extensibility requirement says a later integration implementing
the shared contract can be exposed without adding its form state/API calls to a
monolithic controller. At the reviewed head, a later ticket must edit the
central template, registry, and composition root and invent its own lifecycle
convention, so the required contract and extension point do not exist.

Classification: initial blocking architecture/correctness finding.

Required resolution: define and exercise a real module registration contract
covering metadata and lifecycle/ownership hooks (with integration-local API,
state, view, and styling boundaries), register OIE through it rather than a
special import path, and add an architecture test using a representative
extension module.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...2dfd36232405fb6f518f5eb106ac37c7aea06194`
  and the changed backend/frontend/test/OpenSpec files.
- The prior verification round passed 726 automated tests plus compilation,
  JavaScript syntax, diff hygiene, and strict OpenSpec validation.
- Reproduction against a fresh temporary database confirmed REV-001.
- Reproduction of `POST /api/settings/readiness/checks` confirmed REV-002.
- Existing green tests do not assert fresh-instance incompleteness, diagnostic
  availability semantics, or a usable module registration lifecycle.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-72_build-modular-settings-workspace-and-guided-setup-shell_codex-review-r1.md"`

Reason: three blocking findings remain.
