---
change: decompose-workflow-services
date: 2026-07-16
---

# ZAC-62 Development Log

## Context

ZAC-62 decomposes oversized Lab, FHIR, Order/dcm4chee, Patient, and GDT
workflow services after the repository/domain/template/mapper boundaries from
ZAC-56 through ZAC-61. ZAC-46 is merged into the branch and its OIE management
composition wiring is a protected baseline.

## Implementation

- Recorded the service responsibility, caller, focused-owner, and narrow-port
  inventory.
- Added characterization for the ZAC-46 OIE extension and the ordering of OIE
  and GDT runtime-extension composition before Blueprint construction.
- Product service decomposition has not started; OpenSpec tasks 1.5 through
  7.4 remain incomplete.

## Decisions

- Product implementation is based on the mainline containing ZAC-46 merge
  `d3bae1a`.
- Runtime extensions are characterized against the actual composition seam;
  `create_app` does not call a separate `start_background_runtime(app)` hook.

## Validation Plan

- Run focused service/composition tests after every bounded-context extraction.
- Run the complete unittest suite, Python compilation, strict OpenSpec
  validation, and whitespace checks before review.
- Use disposable databases and external doubles only.

## Follow-ups

- Implement the remaining OpenSpec service-decomposition and architecture tasks
  before requesting review.

## Verification

### Round 1 (2026-07-16)

- Tested head: `909efb0587139c25fd60a35a28ab4a2d98f1bf9a`
- Status: `incomplete`
- Checks: `python -m unittest tests.services.test_zac62_composition_baseline` — pass (2 tests); `python -m unittest discover -s tests -p "test_*.py"` — pass (385 tests); `python -m compileall -q backend tests` — pass; `openspec validate decompose-workflow-services --strict` — pass; `git diff --check` — pass; post-check product state remained clean.
- Unresolved failures: OpenSpec implementation tasks 1.5 through 7.4 remain incomplete, so the tested HEAD does not implement the proposed service decomposition.
- Next action: `/dev-fix "ZAC-62 implementation tasks 1.5 through 7.4 remain incomplete"`

### Round 2 (2026-07-16)

- Tested head: `ba6db2370a5f5cddf44eb92c623a5dbe9d004676`
- Status: `fail`
- Checks: Lab service/composition/integration regression — pass (141 tests); complete unittest discovery — fail (387 passed, 2 failures); Python compilation — pass; strict OpenSpec validation — pass; `git diff --check` — pass; checks changed no product files.
- Unresolved failures: `backend/app_factory.py` grew to 514 lines and violates the 500-line compact composition-root contract in `tests.services.test_protocol_repository_wiring` and `tests.test_architecture_contract`; remaining ZAC-62 tasks are also incomplete.
- Next action: `/dev-fix "backend/app_factory.py is 514 lines and exceeds the 500-line composition-root limit"`

### Round 3 (2026-07-16)

- Tested head: `8cd7cd502ca25da90c4c69d8b42ab6d7030c8c3a`
- Status: `fail`
- Checks: Lab service/composition/integration regression — fail (140 passed, 1 error); complete unittest discovery — fail (388 passed, 1 error); Python compilation — pass; strict OpenSpec validation — pass; `git diff --check` — pass; checks changed no product files.
- Unresolved failures: integration compatibility patches require `backend.app_factory.run_lab_server_health_check`, which was removed when Lab composition moved to `backend/lab_composition.py`; remaining ZAC-62 tasks are also incomplete.
- Next action: `/dev-fix "preserve the backend.app_factory.run_lab_server_health_check patch seam through Lab composition"`

### Round 4 (2026-07-16)

- Tested head: `cf26e6d7a2c604bd0903d03b88c8665aa13edda9`
- Status: `incomplete`
- Checks: Lab service/composition/integration regression — pass (141 tests); complete unittest discovery — pass (389 tests); Python compilation — pass; strict OpenSpec validation — pass; `git diff --check` — pass; checks changed no product files.
- Unresolved failures: automated checks are green, but OpenSpec tasks 1.5 and 3.1 through 7.4 remain incomplete, so the tested HEAD implements only the Lab decomposition portion of ZAC-62.
- Next action: `/dev-fix "ZAC-62 FHIR, Order/dcm4chee, Patient/GDT, architecture, documentation, and closure tasks remain incomplete"`

### Round 5 (2026-07-16)

- Tested head: `fbcee6b8940d9ce24cb3b7f923f509f2b3e04442`
- Status: `incomplete`
- Checks: `python -m unittest discover -s tests -p "test_*.py"` — pass (395 tests); `python -m compileall -q backend tests` — pass; `node --check frontend/static/app.js` — pass; `openspec validate decompose-workflow-services --strict` — pass; `git diff --check` — pass; post-check product state remained clean and only this workflow devlog was dirty.
- Unresolved failures: automated verification is green, but task 1.5 has not been completed in `tasks.md` and composition, documentation, baseline, and final safety-audit tasks 6.1 through 7.4 remain incomplete.
- Next action: `/dev-fix "ZAC-62 tasks 1.5 and 6.1 through 7.4 remain incomplete"`

### Round 6 (2026-07-18)

- Tested head: `98680cde4d2fe29eca2cd91d5ab620b393d8cd9b`
- Status: `pass`
- Checks: service discovery — pass (47 tests); API discovery — pass (2 tests); runtime discovery — pass (5 tests); composition/repository-wiring/architecture/integration regression — pass (175 tests); complete unittest discovery — pass (396 tests); `python -m compileall -q backend tests` — pass; `node --check frontend/static/app.js` — pass; `openspec validate decompose-workflow-services --strict` — pass; `git diff --check` — pass; pre- and post-check product state remained clean and only this workflow devlog was dirty.
- Unresolved failures: none.
- Next action: `/dev-review`

### Round 7 (2026-07-18)

- Tested head: `fb62948208cdda4c9bcded24f7471eb09a5c48c5`
- Status: `pass`
- Checks: service discovery — pass (48 tests); API discovery — pass (2 tests); runtime discovery — pass (5 tests); composition/repository-wiring/architecture/integration regression — pass (175 tests); complete unittest discovery — pass (397 tests); `python -m compileall -q backend tests` — pass; `node --check frontend/static/app.js` — pass; `openspec validate decompose-workflow-services --strict` — pass; `git diff --check` — pass; pre- and post-check product state remained clean while review/devlog workflow records remained dirty.
- Unresolved failures: none.
- Next action: `/dev-review`

## Code Review

### Round 1 (2026-07-18)

- Source: `openspec/changes/decompose-workflow-services/review/2026-07-18_feature-zac-62-decompose-workflow-services_codex-review-r1.md`
- Mode: `initial`
- Verdict: `changes-requested`
- Reviewed head: `98680cde4d2fe29eca2cd91d5ab620b393d8cd9b`
- Transitions: none
- Open blockers: `REV-001`, `REV-002`, `REV-003`
- Follow-ups: none
- Next action: `/dev-fix --review "openspec/changes/decompose-workflow-services/review/2026-07-18_feature-zac-62-decompose-workflow-services_codex-review-r1.md"`

### Round 2 (2026-07-18)

- Source: `openspec/changes/decompose-workflow-services/review/2026-07-18_feature-zac-62-decompose-workflow-services_codex-review-r2.md`
- Mode: `closure`
- Verdict: `approved`
- Reviewed head: `fb62948208cdda4c9bcded24f7471eb09a5c48c5`
- Transitions: `REV-001 resolved; REV-002 resolved; REV-003 resolved`
- Open blockers: none
- Follow-ups: none
- Next action: commit only review/devlog workflow records, then `/dev-done`
