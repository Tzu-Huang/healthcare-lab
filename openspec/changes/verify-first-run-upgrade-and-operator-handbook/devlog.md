---
change: verify-first-run-upgrade-and-operator-handbook
date: 2026-07-27
---

## Context

ZAC-78 is the closure gate for the unified Settings series. Its original
exclusive disposable run found ZAC-79 and ZAC-80, so closure resumed only after
both fixes reached `main`.

## Implementation

- Integrated current `main`, including `v1.1.0`, ZAC-79, and ZAC-80.
- Expanded the ZAC-78 release harness across defaults, upgrade workflow
  assembly, filesystem safety, independent integration failures, and
  cross-surface evidence scanning.
- Reconciled original live evidence with the post-fix ZAC-79 and ZAC-80
  evidence records.

## Decisions

- Preserve the running operator-owned `interoperability-lab` project.
- Treat the original exclusive ZAC-78 run plus linked post-fix live evidence as
  the live closure record.
- Retain no screenshots; enforce screenshot-OCR safety through the common
  synthetic canary gate.

## Validation Plan

- Run the focused ZAC-78, GDT, dcm4chee, AP, OIE, readiness, migration, and
  persisted-settings suites.
- Run the full repository test suite, compile checks, OpenSpec strict
  validation, handbook checks, and diff hygiene under `/dev-test`.

## Verification

### Apply round 1 (2026-07-27 Asia/Taipei)

- Tested head: `d882d05`
- Status: `pass`
- Checks: focused release matrix passed 70 tests with 1 Windows symlink
  capability skip; Docker ownership pre-flight found the normal
  `interoperability-lab` project active, so no shared resources were mutated;
  linked ZAC-79 and ZAC-80 post-fix live evidence is present.
- Unresolved failures: none in requested implementation tasks.
- Next action: `/dev-test`
