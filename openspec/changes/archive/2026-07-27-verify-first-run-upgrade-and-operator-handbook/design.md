## Context

ZAC-77 established the supported zero-edit Compose path, create-only legacy
environment bootstrap, persisted Settings precedence, and Dashboard handoff.
Those behaviors have focused automated coverage, but ZAC-78 is the cross-series
closure gate: it must verify the assembled operator journey against disposable
runtime state and publish instructions matching the released UI and commands.

The repository already contains large English and Traditional Chinese handbook
sources plus generated `.docx` editions. Existing handbook installation and
configuration chapters predate ZAC-77 and describe `.env` as mandatory.
Verification must use synthetic data, protect credentials, preserve shared
developer environments, and distinguish a product defect from missing evidence
or documentation.

## Goals / Non-Goals

**Goals:**

- Make fresh-install and representative legacy-upgrade verification repeatable
  from explicitly disposable databases, Compose projects, and volumes.
- Exercise required success, persistence, migration, diagnostic, and safety
  paths with bounded evidence.
- Make English and Traditional Chinese operator guidance agree with the current
  Settings UI, supported wrapper, and configuration ownership model.
- Keep generated handbook deliverables synchronized with their Markdown
  sources.

**Non-Goals:**

- Add new integration settings or change existing runtime behavior.
- Repair unrelated defects inside this change.
- claim production security, regulated clinical use, or support outside the
  declared local `linux/amd64` lab boundary.
- Delete or reuse an existing operator's Compose project, database, or volume.

## Decisions

### Use isolated verification fixtures and named project identities

Live verification will use an explicit disposable Compose project identity,
fresh named volumes, synthetic settings, and bounded fixture databases.
Pre-flight checks must reject collisions with existing containers, ports, or
volumes. This is preferred to testing against the developer's normal stack
because state provenance and cleanup boundaries remain reviewable.

### Define one canonical legacy-upgrade fixture

The upgrade matrix will build or retain a versioned pre-unified-Settings
database fixture and pair it with representative eligible legacy environment
values. Assertions cover schema migration, secret configured-state
preservation, effective precedence, UI override, and a second restart where
environment bootstrap must not run again. Ad hoc local databases are not valid
release evidence because they cannot be reproduced.

### Separate automated contracts from live evidence

Fast unit, integration, frontend, Compose, and migration tests will enforce the
stable matrix where possible. A dated evidence record will capture the
disposable live run, environment identity, exact tested commit, bounded
outcomes, and precise skips. This keeps CI deterministic while retaining proof
of Docker and cross-service behavior.

### Treat failure evidence as a closed, sensitive-data-safe projection

Each failure case will assert its owning layer, stable category, and recovery
action, plus negative canaries for credentials, PHI, messages, FHIR bodies, and
arbitrary upstream text. Screenshots are allowed only with synthetic records
and inspected redaction. Raw upstream dumps are not attached as evidence.

### Rewrite handbook sources by operator journey, then regenerate Word editions

Installation and configuration guidance will lead with one wrapper start
command, Dashboard/Settings guided setup, and integration-specific validation.
Advanced deployment overrides will be separated from application Settings.
English and Traditional Chinese sections will share the same command, UI-label,
activation, backup, and URL/path facts; the `.docx` files will be regenerated
from the reviewed Markdown sources rather than edited independently.

### Route reproducible product defects out of the closure change

A discovered behavior defect will be documented with a minimal reproduction
and linked to a separate Linear issue. It blocks ZAC-78 when it prevents an
acceptance path. This preserves a clear distinction between verifying the
Settings series and silently extending its implementation scope.

## Risks / Trade-offs

- **Docker resources or ports are already owned** → fail pre-flight without
  mutation and record a precise environment-dependent skip only when exclusive
  ownership cannot be established.
- **Legacy fixture does not represent a supported upgrade** → pin its schema
  boundary and provenance in the fixture contract and review it against the
  migration chain.
- **Bilingual instructions drift** → compare stable UI labels, commands, tables,
  and activation categories, then regenerate both Word editions in one change.
- **Evidence leaks secrets or synthetic clinical payloads unnecessarily** →
  use canaries, bounded result capture, screenshot inspection, and explicit
  negative checks before committing evidence.
- **Live services make checks flaky** → use bounded timeouts and distinguish
  unavailable dependencies from incorrect application behavior.

## Migration Plan

This change does not alter persisted schemas or runtime behavior. Land the
verification contracts, handbook sources, generated editions, and dated
evidence together. If verification finds a blocking defect, keep ZAC-78 open
until its linked fix completes and rerun the affected matrix against the fixed
commit. Documentation rollback is a normal Git revert because it introduces no
runtime migration.

## Open Questions

- Which existing released commit or migration boundary is the canonical
  pre-unified-Settings fixture source?
- Is Windows Docker Desktop the required live witness with equivalent Linux
  recorded as an explicit environment-dependent skip?
