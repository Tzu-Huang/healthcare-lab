---
change: add-persistent-oie-settings-profile
date: 2026-07-14
---

## Context

ZAC-45 establishes one persistent OIE settings profile shared by future OIE administration, managed Channel lifecycle operations, and the HLAB result listener. The implementation remains backend-only and does not call OIE, deploy Channels, start the listener, or add a Settings UI.

## Implementation

- Added additive SQLite tables for the singleton local OIE profile and its managed Channel mappings.
- Seeded the confirmed local defaults: `http://oie:8080`, `admin` / `Admin`, TLS verification disabled, 10-second timeout, and `0.0.0.0:6665` with MLLP and auto-start intent enabled.
- Added atomic store read/update behavior, full managed Channel replacement, duplicate logical-type protection, and migration-safe initialization.
- Added `GET /api/oie/settings` and `PUT /api/oie/settings` with secret-safe responses and actionable validation.
- Added regression coverage for defaults, persistence, migration compatibility, validation, secret masking, malformed URLs, and verbatim password storage.

## Decisions

- Store the local-lab password in restricted SQLite state while never returning or logging it; API responses expose only `passwordConfigured`.
- Preserve an omitted password, replace only with a non-empty string, reject non-string values, and store accepted passwords verbatim.
- Persist listener configuration as desired state without changing the currently running listener.
- Use child mapping rows with one normalized logical type per profile instead of a JSON blob.

## Validation Plan

- Compile changed Python modules and tests.
- Run `tests.test_lab_store` and `tests.test_app` together.
- Run `git diff --check` and strict OpenSpec validation.
- Confirm invalid updates are atomic and responses/logs never contain the password.

## Verification

### Round 1 (2026-07-14)

- PASS: 155 store/API tests.
- PASS: Python compilation, `git diff --check`, and strict OpenSpec validation.
- FAIL during review probes: malformed bracketed-host URLs escaped as `ValueError`; password input was coerced and trimmed.

### Round 2 (2026-07-14)

- PASS: 155 store/API tests after both review fixes.
- PASS: malformed URL validation returns an actionable 400 response.
- PASS: passwords reject non-string values and preserve accepted strings verbatim.
- PASS: Python compilation, `git diff --check`, and strict OpenSpec validation.

## Code Review

### Round 1 (2026-07-14)

- Verdict: Changes requested.
- Must fix: translate malformed Management API URL parser failures into actionable validation errors.
- Must fix: accept passwords only as opaque strings without coercion or trimming.
- Source: `review/2026-07-14_codex-review.md`.

### Round 2 (2026-07-14)

- Verdict: Approved; no findings.
- Confirmed `f6ceddc` resolves malformed URL handling.
- Confirmed `0258ccb` resolves password coercion and whitespace loss.
- Source: `review/2026-07-14_codex-review-r2.md`.

## Follow-ups

- Later OIE Settings work may consume this profile to authenticate to OIE, manage Channels, and apply listener auto-start intent.
- Production-grade external secret storage remains outside the local-lab scope.
