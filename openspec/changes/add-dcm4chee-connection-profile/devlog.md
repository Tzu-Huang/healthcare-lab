---
change: add-dcm4chee-connection-profile
date: 2026-07-08
---

## Context

ZAC-35 adds the Healthcare Lab dcm4chee-arc connection profile needed before future MWL order creation, MWL verification, C-STORE reconciliation, and viewer-link work can share one environment-specific configuration source.

This builds on ZAC-34, which defined the dcm4chee MWL order model and identifier/reconciliation contract.

## Implementation

- Added a named `local-dcm4chee` profile loaded from Flask config/environment values.
- Added profile fields for display/environment identity, Web UI URL, DIMSE host/port and AE titles, MWL AE title, default Scheduled Station AE Title, DICOMweb endpoints, viewer-link template, auth placeholders, and TLS placeholders.
- Added `/api/dcm4chee/profile`, `/api/dcm4chee/profiles/<profile_name>`, and `/api/dcm4chee/profile/diagnostics`.
- Integrated dcm4chee profile diagnostics and DIMSE smoke behavior into the existing dcm4chee smoke profile.
- Documented local defaults in `.env.example` and README.
- Added tests for default profile loading, unknown profile lookup, missing/invalid diagnostics, malformed env diagnostics, and out-of-range DIMSE port smoke behavior.

## Decisions

- The profile is a dedicated dcm4chee workflow configuration shape rather than overloading the generic lab-server registry.
- The local profile defaults are `local-dcm4chee`, `DCM4CHEE`, `HEALTHCARE_LAB`, and `ECG_AP`, matching the Docker lab defaults.
- Invalid dcm4chee numeric/boolean config values are preserved into profile diagnostics instead of crashing app startup.
- Local auth/TLS defaults are explicit lab-only placeholders, not production security.

## Validation Plan

- Run `python -m py_compile app.py tests\test_app.py`.
- Run `python -m unittest tests.test_app -v`.
- Run `openspec validate add-dcm4chee-connection-profile --strict`.
- Review the branch from a Codex code-review stance.

## Code Review

### Round 1 (2026-07-08)

- Review file: `openspec/changes/add-dcm4chee-connection-profile/review/2026-07-08_codex-review.md`.
- Verdict: changes requested.
- Finding: malformed dcm4chee env values could crash startup before diagnostics could report them.
- Resolution: `fix(ZAC-35): report malformed dcm4chee config diagnostics`.

### Round 2 (2026-07-08)

- Review file: `openspec/changes/add-dcm4chee-connection-profile/review/2026-07-08_codex-review-r2.md`.
- Verdict: changes requested.
- Finding: out-of-range dcm4chee DIMSE ports could still crash smoke checks.
- Resolution: `fix(ZAC-35): guard dcm4chee smoke port range`.

### Round 3 (2026-07-08)

- Review file: `openspec/changes/add-dcm4chee-connection-profile/review/2026-07-08_codex-review-r3.md`.
- Verdict: approved; no issues found.
- Residual risk: manual dcm4chee Docker/UI smoke was not run.

## Follow-ups

- Manual dcm4chee Docker/UI smoke was not run in this implementation pass.
- Future tickets still need MWL order creation, AP MWL query behavior, C-STORE reconciliation, and viewer-link consumption.
