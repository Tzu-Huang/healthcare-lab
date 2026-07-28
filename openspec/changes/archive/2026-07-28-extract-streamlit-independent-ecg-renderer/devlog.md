---
change: extract-streamlit-independent-ecg-renderer
date: 2026-07-28
---

## Context

ZAC-93 extracts the ECG graphing boundary from the Streamlit prototype so the
normalized immutable ECG model can produce an in-memory browser SVG without
DICOM, JSON, file-selection, authentication, or batch-processing concerns.

## Implementation

- Added a presentation-layer 12-lead SVG renderer with immutable configuration,
  typed results/errors, normalized-frequency timing, and optional display-only
  baseline centering.
- Added request-local Figure/canvas/buffer ownership and serialized the complete
  Matplotlib lifecycle for threaded Gunicorn safety.
- Added the pinned Matplotlib runtime range and focused contract, validation,
  immutability, cleanup, repeated-render, and concurrent-render tests.

## Decisions

- Output is SVG-only and visibly demonstration-only, not for diagnostic use.
- Default layout is two columns by six rows at nominal 25 mm/s and 10 mm/mV;
  browser physical calibration is not claimed.
- The renderer does not directly depend on NumPy, Streamlit, or `ecg_plot`.

## Validation Plan

- Run focused ECG renderer and normalized-domain suites.
- Run the complete repository test discovery.
- Check dependencies, compile the new modules, validate OpenSpec strictly, and
  audit the final diff for excluded runtime and integration responsibilities.

## Follow-ups

- Flask route and frontend viewer integration remain separately scoped work.
- Diagnostic display conformance and PNG/PDF output remain out of scope.

## Verification

### Round 1 (2026-07-28 10:24:11 +08:00)

- Tested head: `b6649103db32c0e44ba7d4fad27ed10cd1fcadfd`
- Status: `pass`
- Checks:
  - pass — `python -m unittest tests.presentation.test_ecg_renderer tests.domain.test_ecg_waveform -v`: 21 tests passed.
  - pass — `python -m unittest discover -s tests -p "test_*.py"`: 894 tests passed; 1 optional local Philips fixture check skipped.
  - pass — `python -m pip check`: no broken requirements.
  - pass — `python -m py_compile backend\presentation\ecg_renderer.py tests\presentation\test_ecg_renderer.py`.
  - pass — `openspec validate extract-streamlit-independent-ecg-renderer --strict`.
  - pass — prohibited-runtime/scope scan and `git diff --check`; no product or test files changed during verification.
- Unresolved failures: none
- Next action: `/dev-review`

### Round 2 (2026-07-28 10:37:29 +08:00)

- Tested head: `13d6c4ef1ce64256a258a08a41101bb5d9a12b6d`
- Status: `pass`
- Checks:
  - pass — `python -m unittest tests.presentation.test_ecg_renderer tests.domain.test_ecg_waveform -v`: 23 tests passed, including REV-001 workload rejection before lock/Figure allocation and REV-002 cleanup-failure buffer/lock release.
  - pass — `python -m unittest discover -s tests -p "test_*.py"`: 896 tests passed; 1 optional local Philips fixture check skipped.
  - pass — `python -m pip check`: no broken requirements.
  - pass — `python -m py_compile backend\presentation\ecg_renderer.py tests\presentation\test_ecg_renderer.py`.
  - pass — `openspec validate extract-streamlit-independent-ecg-renderer --strict`.
  - pass — `git diff --check`; no product or test files changed during verification.
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-28 10:27:25 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-93_extract-streamlit-independent-ecg-renderer_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `b6649103db32c0e44ba7d4fad27ed10cd1fcadfd`
- Transitions: `REV-001 open; REV-002 open`
- Open blockers: `REV-001, REV-002`
- Follow-ups: none
- Next action: `/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-93_extract-streamlit-independent-ecg-renderer_codex-review-r1.md"`

### Round 2 (2026-07-28 10:39:18 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-93_extract-streamlit-independent-ecg-renderer_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `13d6c4ef1ce64256a258a08a41101bb5d9a12b6d`
- Transitions: `REV-001 resolved; REV-002 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: `/dev-done`
