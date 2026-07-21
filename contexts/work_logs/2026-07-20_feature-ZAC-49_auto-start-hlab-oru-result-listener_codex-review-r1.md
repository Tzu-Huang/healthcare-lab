---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-49_auto-start-hlab-oru-result-listener
base: main
reviewed_head: 73d46e56e41d37d6e6ec69aff9c98f3ed89539d8
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | A fresh Settings module initializes `runtimeReloadRequired` to false, and refresh only clears it on a match; it never restores the reminder when persisted and active listener configurations differ. |

## New blocking findings

### [P2][REV-001] Browser reload drops the required unapplied-listener reminder

- Files: `frontend/static/js/state/settings.js:4`, `frontend/static/js/views/settings.js:37`, `frontend/static/js/views/settings.js:41`, `tests/frontend/test_oie_interactions.py:145`
- Impact: after an operator saves changed listener settings while the old listener remains running, reloading the browser resets `runtimeReloadRequired` to `false`. `refreshSettings()` only assigns `false` when settings match status and leaves the initial false value unchanged when they do not match, so the warning disappears even though the socket still uses the old configuration. The same loss occurs after navigating from a newly loaded page to Settings.
- Evidence: the accepted delta spec requires a persistent reminder and explicitly says browser refresh must not imply a listener rebind. The Playwright test proves Save then Retry in one page lifetime, but never reloads or reconstructs the Settings module between those actions.
- Classification: explicit-requirement blocker introduced by this change.
- Required resolution: derive unapplied state on every Settings refresh from persisted intent plus runtime status, including stopped/auto-start semantics, and add a browser test that reloads after Save while status still reflects the old listener configuration, verifies the reminder remains visible, then proves it clears only after matching running status (or the intended disabled/stopped state) is observed.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed the full `main...73d46e56e41d37d6e6ec69aff9c98f3ed89539d8` diff, the three OpenSpec delta specifications, runtime/service/API/composition paths, Settings and OIE frontend paths, and focused lifecycle/browser tests.
- The recorded verification round passed 499 repository tests plus focused Playwright coverage, but the current browser test does not exercise page reload persistence.
- No additional blocking correctness, security, privacy, or data-loss findings were identified.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-20_feature-ZAC-49_auto-start-hlab-oru-result-listener_codex-review-r1.md"`

Reason: REV-001 violates the explicit persistent-reminder acceptance contract.
