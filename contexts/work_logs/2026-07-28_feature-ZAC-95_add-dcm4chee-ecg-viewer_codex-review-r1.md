---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-95_add-dcm4chee-ecg-viewer
base: main
reviewed_head: 2745f748c689c266a6707709a47b02d2115cff1f
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | Frontend tests inspect JavaScript/template source text but do not execute the required UI behavior. |

## New blocking findings

### [P2][REV-001] Frontend acceptance behavior is not executed by tests

The ZAC-95 acceptance contract explicitly requires frontend tests for action visibility, URL construction, `noopener`, loading, success, and failure rendering. The added tests in `tests/frontend/test_dcm4chee_view_module.py:38` and `tests/frontend/test_ecg_viewer.py:28` only load files with `Path.read_text()` and assert that selected strings are present. They never execute `dcm4cheeEcgViewerUrl()`, `dcm4cheeActionsForResult()`, `loadEcgViewer()`, DOM state transitions, `fetch`, image load/error events, or `window.open`.

Impact: regressions such as an action always being hidden, a broken click handler, loading/content/error regions changing incorrectly, or `noopener` not reaching `window.open` can still pass the current suite as long as the expected source fragments remain. This leaves an explicit acceptance criterion unverified.

Classification: initial-review acceptance blocker. P2 blocks because it directly violates the required frontend test coverage in the issue and OpenSpec tasks 4.1-4.3.

Required resolution: add executable frontend behavior tests using the project's supported JavaScript/DOM test approach (or a bounded browser harness). Cover at minimum:

- supported versus unsupported result action visibility and the generated result-ID URL;
- `window.open` receiving `_blank` and `noopener`;
- viewer loading to successful metadata/graph state;
- controlled metadata failure and independent SVG load failure states;
- direct route parsing/reload initialization.

Keep source-ownership characterization assertions only as supplementary coverage.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...2745f748c689c266a6707709a47b02d2115cff1f` against the ZAC-95 proposal, design, specs, and completed task list.
- Prior `/dev-test` evidence passed 18 backend tests, 13 frontend/source-characterization tests, JavaScript syntax checks, OpenSpec strict validation, Python compile, and diff hygiene.
- No confirmed P0/P1 correctness, security, privacy, or disclosure defect was found in the implementation.
- Live AP/dcm4chee browser exercise remains an environment-only residual risk; mocked WADO-RS integration passed.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-95_add-dcm4chee-ecg-viewer_codex-review-r1.md"`

Reason: REV-001 blocks approval because the explicit frontend behavior acceptance criterion is not executed by the current tests.
