---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-50_build-oie-settings-channel-management-ui
base: main
reviewed_head: fe8e52d6555fa95a2af332c1c0893df28de0ec6e
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P1 | open | Managed lifecycle composition captures one Management API client at process startup, independently of later Settings updates. |
| REV-002 | P1 | open | The bounded Edit flow cannot create a valid missing mapping and does not refresh inventory/actions after save. |
| REV-003 | P2 | open | Lifecycle audit data exists but inventory never projects last-operation status. |
| REV-004 | P2 | open | The Settings sidebar entry has no visual separator from operational workspaces. |

## New blocking findings

### [P1][REV-001] Saved connection changes do not reach managed-Channel operations

[backend/app_factory.py](../../backend/app_factory.py) constructs one `OieManagementClient` from persisted configuration at lines 329-331 and injects that concrete client into the process-long lifecycle service. [backend/services/oie_settings.py](../../backend/services/oie_settings.py) persists later connection changes and creates a fresh client only for Test Connection. Consequently, an operator can save and successfully test a new URL, username, password, or TLS policy while every managed-Channel inspect/preview/mutation continues using the old startup configuration and possibly its old authenticated session until lab-app restarts.

Impact: the central ZAC-50 workflow can report the new connection as healthy but operate against the wrong OIE instance or stale credentials. This violates the single Settings workspace contract and is a P1 correctness/safety blocker.

Required resolution: make lifecycle operations obtain a client from the latest private settings at operation time, or explicitly and safely rotate the lifecycle client after a successful profile update. Add a regression proving that a saved connection change is used by the next inspect/preview/mutation and that the superseded session is closed.

Classification: initial blocking finding.

### [P1][REV-002] Saving Channel edits does not provide the promised Apply path

[frontend/static/js/views/settings.js](../../frontend/static/js/views/settings.js) lines 177-189 builds a new mapping with only `logicalType` plus edited fields when the expected Channel has no persisted mapping. The backend requires `channelName` at [backend/domain/oie.py](../../backend/domain/oie.py) lines 73-77, so editing a default Missing Channel fails validation. For an existing mapping, the save only calls `renderProfile(result.item)` and leaves `state.items` and `permittedActions` unchanged; an Unchanged card therefore remains without the newly required Apply/update action even though the saved desired state is now drifted.

Impact: the explicit Edit → Save desired values → Preview Apply acceptance path is unusable both before first Create and for an existing unchanged Channel without a manual full refresh. The UI nevertheless tells the operator to “Preview Apply,” creating a misleading success state.

Required resolution: preserve/add the required Channel display identity when creating a desired mapping, refresh lifecycle inventory after a successful edit save, and prove in browser coverage that Missing and Unchanged cards can save valid edits and immediately expose the correct Recreate/Apply action.

Classification: initial blocking finding.

### [P2][REV-003] Managed inventory never reports last-operation status

[frontend/static/js/views/settings.js](../../frontend/static/js/views/settings.js) line 144 renders `item.lastOperation`, but [backend/services/oie_channel_lifecycle.py](../../backend/services/oie_channel_lifecycle.py) inventory projection never supplies that field. The repository already exposes ordered lifecycle audits at [backend/repositories/oie_settings.py](../../backend/repositories/oie_settings.py) line 215, so every card permanently renders `-` even after operations.

Impact: ZAC-50 explicitly requires last-operation status in managed Channel inventory; the delivered surface cannot distinguish the last success, failure, or partial failure after refresh.

Required resolution: project the latest bounded audit outcome per logical type into inventory without leaking audit internals or secrets, and add service/API/UI coverage.

Classification: initial blocking finding; P2 blocks because it violates an explicit ticket requirement.

### [P2][REV-004] Settings is not visually separated from operational navigation

[frontend/templates/shell/sidebar.html](../../frontend/templates/shell/sidebar.html) lines 10-33 places Settings as another ordinary `.sidebar-link`; [frontend/static/css/layout.css](../../frontend/static/css/layout.css) defines no Settings divider, grouping, or auto-margin treatment. Being last in DOM order does not satisfy the requirement that Settings be visually separated from operational workspaces.

Impact: the primary information architecture requested by ZAC-50 is absent, and Settings appears to be another operational workspace.

Required resolution: add semantic/sidebar grouping or a dedicated Settings modifier with visible separation that remains correct in responsive layouts, plus a focused template/style or browser assertion.

Classification: initial blocking finding; P2 blocks because it violates an explicit requirement.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...fe8e52d6555fa95a2af332c1c0893df28de0ec6e` against the ZAC-50 workspace, managed lifecycle, and modular frontend delta specifications.
- Verification Round 1 passed at the reviewed head: 553 tests plus Python compile, recursive JavaScript syntax, strict OpenSpec validation, and diff hygiene.
- No live OIE 4.5.2 mutation was run; controlled doubles cover the required safety behavior, leaving ordinary environment integration risk.
- The uncommitted `devlog.md` is a workflow record only and does not alter the reviewed product state.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-21_feature-ZAC-50_build-oie-settings-channel-management-ui_codex-review-r1.md" REV-001 REV-002 REV-003 REV-004`

Reason: four blocking findings remain against the pinned reviewed head.
