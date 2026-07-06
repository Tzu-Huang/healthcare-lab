---
change: patient-centered-oie-console
date: 2026-07-06
---

## Context

ZAC-20 implements a patient-centered OIE console for Healthcare Lab, connecting local ADT patient inventory, local ORM order send/resend, and OIE-routed ORU result receipt.

## Implementation

- Added ORU result persistence in SQLite with parsed MSH-10, PID-3, OBR-2, and OBR-3 fields.
- Added ORU matching by PID-3 plus OBR-2 or OBR-3, with patient-only and fully unmatched result visibility.
- Added a local OIE -> lab-app MLLP result listener with start, stop, and status APIs, defaulting to port 6665.
- Added successful and failure HL7 ACK generation for accepted, unsupported, and invalid result messages.
- Reworked the OIE page into a patient-centered workflow with ADT patients, selected patient orders/results, unmatched results, listener controls, and shared HL7 preview.

## Decisions

- Listener settings are runtime-only for this version.
- Patient result counts include order-matched and patient-only unmatched ORU results.
- Fully unknown-patient ORU messages remain visible in the Unmatched Results area.

## Validation Plan

- Run backend tests for ORU parsing, persistence, matching, unmatched handling, ACK behavior, and listener lifecycle.
- Run frontend JavaScript syntax checks.
- Run OpenSpec strict validation.
- Treat full ADT -> ORM -> OIE -> ORU listener loop as manual because it requires an external OIE/MLLP runtime.

## Follow-ups

- Decide whether `/api/oie/results` should remain as a manual JSON injection endpoint or whether production-like ORU ingress should be listener-only.

## Verification

### Round 1 (2026-07-06)

- pass: `python -m py_compile app.py backend\lab_store.py`
- pass: `node --check frontend\static\app.js`
- pass: `python -m unittest discover -s tests -p "test*.py"` (44 tests)
- pass: `openspec validate patient-centered-oie-console --strict`
- pass: `git diff --check`
- skip: full ADT -> ORM -> OIE -> ORU listener runtime loop, pending external OIE/MLLP runtime.

## Code Review

### Round 1 (2026-07-06)

- Source: `openspec/changes/patient-centered-oie-console/review/2026-07-06_codex-review.md`
- Verdict: Approved for `/dev-done`.
- Findings: No issues found in the current `main...HEAD` diff.
- Note: The prior listener startup finding was fixed by binding/listening synchronously before returning success and adding an occupied-port regression test.
- Residual risk: full OIE runtime loop still requires external OIE/MLLP validation.
