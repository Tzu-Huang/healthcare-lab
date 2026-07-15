---
change: extract-lab-oie-openemr-repositories
date: 2026-07-15
---

## Context

ZAC-57 extracts lab control-plane persistence, OIE result persistence, and OpenEMR MariaDB query ownership from the mixed `DemoStore` while preserving existing APIs, stored projections, transaction behavior, and compatibility seams.

## Implementation

- Added focused `LabRepository` and `OieRepository` owners over the shared `SQLiteDatabase` connection factory and write lock.
- Moved OIE settings validation and serialization into the settings repository module.
- Moved OpenEMR procedure-order querying into `backend/clients/openemr.py` and pure row normalization/mapping into `backend/domain/openemr.py`.
- Injected narrow repository and coordination ports into lab/OIE workflows and runtime composition.
- Retained only explicit `DemoStore` delegates and the required OpenEMR compatibility re-export.
- Added lazy WSGI construction so importing the application module does not initialize the default database.
- Relocated focused tests into repository/client/runtime suites and strengthened architecture enforcement around the exact retained composition surface.

## Decisions

- Repositories share the existing `SQLiteDatabase.lock`; no schema or migration change was introduced.
- OIE workbench assembly stays in the service layer because it coordinates patient, order, and result contexts.
- OpenEMR MariaDB access is modeled as an external client rather than a local repository.
- Legacy architecture entries are removal-only; approved compatibility delegates and composition assignments are matched structurally instead of adding baseline exceptions.
- Automated verification uses disposable SQLite databases and external-service doubles.

## Validation Plan

- Run focused repository, client, service, runtime, and selected integration tests.
- Run the architecture contract and verify the legacy baseline diff contains removals only.
- Run the complete unittest suite while comparing the repository database SHA-256 and modification timestamp before and after.
- Run direct OIE settings module execution and `git diff --check main...HEAD`.

## Follow-ups

- Exercise live OpenEMR/OIE connectivity and Docker lifecycle behavior only in an explicitly provisioned integration environment.
- Deployment, merge, and release remain separate workflow steps.

## Verification

### Round 1 (2026-07-15)

- Focused extraction scope: 45 passed.
- Architecture contract: 37 passed.
- Full automated suite: 263 passed.
- Direct OIE settings module execution: 4 passed.
- `instance/healthcare-lab.db` SHA-256 and `LastWriteTimeUtc` remained unchanged.
- Legacy baseline diff against `main` contains removals only; `git diff --check main...HEAD` passes.
- No live services, Docker lifecycle, deployment, push, merge, or release action was used.

## Code Review

### Round 1 (2026-07-15)

- Source: `review/2026-07-15_codex-review.md`
- Verdict: Approved; no findings.
- Resolved during review cycles: interpreter portability, repository-test relocation and import ordering, baseline churn, delegate/composition bypasses, class-shell exemption scope, and diff hygiene.
- Residual risk: live OpenEMR/OIE and Docker lifecycle behavior were intentionally not exercised locally.
