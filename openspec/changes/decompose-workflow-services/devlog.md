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
