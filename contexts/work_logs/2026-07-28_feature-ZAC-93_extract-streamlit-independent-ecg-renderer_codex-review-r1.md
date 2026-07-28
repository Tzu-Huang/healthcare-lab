---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-93_extract-streamlit-independent-ecg-renderer
base: main
reviewed_head: b6649103db32c0e44ba7d4fad27ed10cd1fcadfd
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | `backend/presentation/ecg_renderer.py:31,208-211` admits 2,000,000 samples per lead while `:81-149` serializes every render; measured 10,000 samples/lead at 6.6 s and 50,000 at 23.9 s. |
| REV-002 | P2 | open | `backend/presentation/ecg_renderer.py:145-149` can skip buffer close and lock release if `Figure.clear()` raises; the failure test at `tests/presentation/test_ecg_renderer.py:209-224` does not exercise cleanup failure. |

## New blocking findings

### [P2][REV-001] Accepted input can monopolize the process-wide render lock

- Location: `backend/presentation/ecg_renderer.py:31`, `backend/presentation/ecg_renderer.py:81-149`, `backend/presentation/ecg_renderer.py:208-211`
- Impact: The renderer accepts as many as 2,000,000 samples for each of 12 leads, builds full Python time tuples, creates all Matplotlib artists, and serializes the SVG while holding the only renderer lock. A valid request near that limit can consume extreme memory and hold all four threaded Gunicorn request paths behind the lock far beyond the 120-second worker timeout. This contradicts the explicit concurrent-rendering and Flask/Gunicorn safety contract even though small-fixture concurrency tests pass.
- Evidence: A read-only local benchmark at the reviewed HEAD took approximately 6.6 seconds and emitted 1.3 MB for 10,000 samples/lead; 50,000 samples/lead took approximately 23.9 seconds and emitted 6.2 MB. The accepted maximum is forty times larger than the slower case.
- Classification: initial explicit-requirement blocker.
- Required resolution: Establish and test a defensible pre-allocation workload bound suitable for the intended resting-ECG duration, or implement a documented bounded rendering/decimation strategy that preserves the agreed display semantics. Add boundary tests proving oversized normalized waveforms are rejected before acquiring the render lock or allocating a Figure.

### [P2][REV-002] Cleanup failure can leave the render lock permanently held

- Location: `backend/presentation/ecg_renderer.py:145-149`, `tests/presentation/test_ecg_renderer.py:209-224`
- Impact: The `finally` block calls `figure.clear()` before closing the buffer and releasing `_RENDER_LOCK`. If Matplotlib cleanup raises because an artist or callback is malformed, execution skips both later operations. The owning thread retains the reentrant lock and other Gunicorn threads can block indefinitely. This violates the requirements that failure paths deterministically release per-call resources and that concurrent calls remain independent.
- Evidence: The existing failure test makes `print_svg()` fail, but `Figure.clear()` still succeeds; it therefore cannot prove lock or buffer release when cleanup itself fails.
- Classification: initial explicit-requirement blocker.
- Required resolution: Structure cleanup with nested `try/finally` or context-managed lock ownership so buffer closure and lock release occur even when Figure cleanup fails. Preserve the primary typed render error where practical and add a focused test that forces cleanup failure while proving the synchronization primitive is released.

## Follow-up findings

None.

## Verification and residual risk

- `python -m unittest tests.presentation.test_ecg_renderer tests.domain.test_ecg_waveform -v`: 21 passed.
- `python -m unittest discover -s tests -p "test_*.py"`: 894 passed, 1 optional local Philips fixture check skipped.
- `python -m pip check`, `python -m py_compile`, strict OpenSpec validation, and diff hygiene passed during `/dev-test`.
- Review benchmark used only in-memory normalized fixtures and created no repository files.
- Residual risk after the required fixes: SVG size and render latency should be re-characterized at the new accepted boundary; diagnostic display conformance remains explicitly out of scope.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-28_feature-ZAC-93_extract-streamlit-independent-ecg-renderer_codex-review-r1.md"`

Reason: REV-001 and REV-002 are blocking P2 violations of explicit concurrency and deterministic-cleanup requirements.
