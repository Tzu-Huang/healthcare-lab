---
change: parse-normalize-dicom-ecg-waveforms
date: 2026-07-28
---

## Context

ZAC-92 introduces the framework-independent parser and normalized domain model
required by later DICOM ECG retrieval and rendering work.

## Implementation

- Declared pydicom as a bounded runtime dependency.
- Added strict DICOM ECG waveform validation, decoding, calibration, canonical
  SCPECG lead mapping, immutable output models, safe metadata, and typed errors.
- Added constructed dataset coverage and optional local Philips fixture
  compatibility tests.

## Decisions

- Decode signed 16-bit multiplexed samples without adding NumPy.
- Treat local DICOM fixtures as Git-excluded compatibility inputs.
- Expose renderer-facing metadata only through an explicit allowlist.

## Validation Plan

- Run focused parser and fixture tests.
- Run architecture and container/deployment contract suites.
- Validate Python compilation, installed dependencies, and OpenSpec artifacts.

## Follow-ups

- ZAC-93 and ZAC-94 can consume the normalized model for rendering and WADO-RS
  retrieval without adding transport concerns to the parser.

## Verification

### Round 1 (2026-07-28 09:44:48 +08:00)

- Tested head: `0b66f63e76823fb01df81b1abc1be8e3c00051b0`
- Status: `pass`
- Checks:
  - PASS — `python -m py_compile backend/domain/ecg_waveform.py tests/domain/test_ecg_waveform.py`
  - PASS — `python -m unittest tests.domain.test_ecg_waveform -v` (11 tests, including both local fixtures)
  - PASS — `python -m unittest tests.test_architecture_contract -v` (46 tests)
  - PASS — container workflow, release, and Compose contract suites (33 tests)
  - PASS — `python -m pip check`
  - PASS — `openspec validate parse-normalize-dicom-ecg-waveforms`
  - PASS — post-check product worktree remained identical to the tested head
- Unresolved failures: none
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-28 09:46:46 +08:00)

- Source: `contexts/work_logs/2026-07-28_feature-ZAC-92_parse-normalize-dicom-ecg-waveforms_codex-review-r1.md`
- Mode: `initial`
- Verdict: `approved`
- Reviewed head: `0b66f63e76823fb01df81b1abc1be8e3c00051b0`
- Transitions: `REV-001 follow-up`
- Open blockers: `none`
- Follow-ups: remove duplicate Unicode micro-unit aliases
- Next action: commit review records, then `/dev-done`
