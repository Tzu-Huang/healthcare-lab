---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-65_remove-demostore-facade-and-obsolete-compatibility-exports
base: main
reviewed_head: 6214f740e5f8e58d8a638e4bbece5a6eb0f8d6d5
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | `backend/application_defaults.py` replaces the deleted facade export surface with a cross-domain defaults/helper module. |

## New blocking findings

### [P2][REV-001] Remove the replacement cross-domain compatibility surface

`backend/application_defaults.py:15` through `backend/application_defaults.py:135`
imports and re-exports symbols from GDT, DICOM, FHIR, OpenEMR, repository,
mapper, maintenance, schema, service, and status owners. Static AST usage shows
more than 70 of those imported names are not consumed by this module; they exist
only as transitive exports. The same file then owns unrelated patient, order,
OIE, FHIR, GDT, lab-server, timestamp, URL, HL7, and GDT helper definitions
through line 369. `backend/app_factory.py:142` consumes this centralized surface
instead of importing status, lab, OpenEMR, GDT, and other symbols from their
responsibility-specific owners.

This is a blocking P2 because it violates the explicit ZAC-65 acceptance
requirement that remaining constants and helpers be imported from their
responsibility-specific owners and that the removed facade not be replaced by
another broad compatibility export. Runtime tests pass, but the architectural
service-locator/export boundary remains effectively renamed.

Classification: initial-review acceptance-criterion violation.

Required resolution: remove unused transitive imports/re-exports; move the
remaining locally defined constants and helpers to focused configuration,
domain, or protocol owners (or reuse existing owners); update production and
test callers to import those owners directly; and add an architecture contract
that rejects a new cross-domain compatibility/defaults grab bag rather than
checking only the deleted `DemoStore` spellings.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...6214f740e5f8e58d8a638e4bbece5a6eb0f8d6d5`, the OpenSpec proposal,
  design, requirements, tasks, production composition/wiring, and migrated test
  support.
- The persisted verification round passed 486 complete regression tests and
  313 focused composition/repository/service/API/runtime/architecture tests,
  plus strict OpenSpec, syntax, diff-hygiene, and removed-spelling scans.
- Those checks establish behavioral stability but do not cover the replacement
  cross-domain export pattern identified by REV-001.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-20_feature-ZAC-65_remove-demostore-facade-and-obsolete-compatibility-exports_codex-review-r1.md" REV-001`

Reason: the explicit responsibility-owner and no-replacement-facade acceptance
criteria remain violated.
