# ZAC-78 Settings release verification evidence — 2026-07-24

## Tested state

- Branch: `feature/ZAC-78_verify-first-run-upgrade-and-operator-handbook`
- Automated foundation commit: `3580a2c`
- Handbook alignment commit: `f41f444`
- Host: Windows, PowerShell, Docker Desktop
- Data: synthetic canaries only

## Automated evidence

- `python -m unittest tests.test_zac78_settings_release_verification -v`
  passed 6 tests.
- Focused Compose, wrapper, and ZAC-78 verification group passed 32 tests.
- The canonical generated fixture records migration ledger version 8, directly
  before `add-typed-integration-settings`, and upgrades through the current
  migration chain.
- Tests cover clean default/readiness projection, one-time legacy bootstrap,
  secret configured-state redaction, persisted-value precedence, dependency
  recreation, bounded evidence rejection, and absence of Docker/Compose
  execution authority in Settings API/service surfaces.
- English and Traditional Chinese Markdown handbooks passed diff hygiene.
  Generated Word editions passed ZIP/XML parsing and round-trip key-content
  checks. PDF rendering was not available because the bundled LibreOffice
  helper does not support this Windows Python socket environment.

## Disposable live pre-flight

Read-only pre-flight found:

```text
Compose project: interoperability-lab
Container: interoperability-lab-lab-app-1
Published port: 5000 -> 5000
Explicit Compose network name: interoperability-lab
```

The active project already owns the supported project/network identity and
port 5000. The Compose file also fixes the network name explicitly, so a
parallel `docker compose -p` run would not provide full network isolation.

No container, service, network, volume, port, database, or GDT directory was
stopped, recreated, deleted, or repurposed.

## Initial environment-dependent skips

- Fresh full-stack startup and guided browser setup was initially **skipped** because
  exclusive project, network, and port ownership was not available.
- Live restart and container-recreation persistence was initially **skipped** for the same
  ownership reason.
- Live legacy-volume upgrade and second restart was initially **skipped** because it requires
  an exclusively owned disposable project and volumes.
- External failure matrix and screenshots were initially **skipped** because the required
  isolated services were not started.

The exclusive run later in this record supersedes these initial skips except for
the explicitly incomplete scenarios and screenshots called out below.

## Product defects

The later exclusive run established two blocking defects:

- `ZAC-79` — fresh startup requires otherwise undocumented empty secret
  environment variables, current-code startup rejects the shipped dcm4chee
  `tlsEnabled=false` / `tlsVerify=true` defaults, and the published `1.0.1`
  image does not expose the Settings readiness API.
- `ZAC-80` — failed Medplum OAuth/connectivity diagnostics do not survive
  container recreation; readiness returns Medplum to `ready` and can report
  overall setup complete.

Both issues block ZAC-78.

## Exclusive disposable run

After the earlier owner released all containers, two isolated projects were
created with unique networks, alternate host ports, fresh volumes, and
repository-local synthetic GDT paths:

- `zac78-settings-verification` for fresh install and failure checks;
- `zac78-settings-upgrade` for the canonical v8 upgrade.

No `interoperability-lab` network or volume was reused or removed.

### Fresh install

- Compose resolved to project/network `zac78-settings-verification`, host port
  15000, fresh project-scoped volumes, and an isolated GDT bind.
- Startup without secret variables failed before container convergence because
  Compose secrets required their source variables to exist (`ZAC-79`).
- With explicit empty secret sources, the published `1.0.1` image returned HTTP
  200 but `/api/settings/readiness` returned 404 (`ZAC-79`).
- A local image built from the tested branch failed startup because shipped
  dcm4chee defaults set TLS verification while TLS was disabled (`ZAC-79`).
- With the verification-only `DCM4CHEE_TLS_VERIFY=false` override, the local
  image became healthy. Initial readiness correctly reported Medplum
  `needs-setup`, OIE and dcm4chee ready, and GDT/AP disabled.
- Save-and-test with a synthetic wrong Medplum secret returned independently
  bounded stages: metadata passed, OAuth `authorization-failure`, and
  authenticated read skipped.
- An unreachable `.invalid` FHIR URL returned bounded `connection-failure` and
  no upstream body.
- Missing GDT paths returned per-role `missing` results. `/proc` remained
  readable but lacked the diagnostic directory; no unsafe path was created.
- Unreachable dcm4chee hosts returned independent bounded web UI, QIDO-RS,
  HL7-TCP, and DIMSE-TCP failures.
- After GDT/AP were disabled, readiness reported complete and retained the
  persisted profile/secret configured state across container recreation.
  However, the failed Medplum operational result was lost and readiness returned
  it to ready (`ZAC-80`).

### Upgrade

- A generated canonical migration-ledger v8 database was copied into a new
  `zac78-settings-upgrade_lab-app-instance` volume.
- Current code upgraded it in place and bootstrapped the representative legacy
  Medplum client ID and secret once; the public projection exposed only
  `configured: true`.
- The client ID was changed through the Settings API to
  `operator-zac78-client`.
- `lab-app` was recreated with conflicting
  `MEDPLUM_CLIENT_ID=conflicting-zac78-client`; the persisted operator value and
  secret configured state remained authoritative.

### Evidence safety and cleanup

- Fresh and upgrade logs passed the secret, PHI, raw-message, FHIR-body, and
  upstream-response canary scan.
- No screenshots were retained.
- Both disposable projects were removed with their project-scoped volumes and
  networks after evidence capture.
- The previously retained `interoperability-lab` networks and volumes were not
  changed.

## Closure rerun after ZAC-79 and ZAC-80

The ZAC-78 branch was updated from `main` at merge commit `5b80bdc`, which
includes the published `v1.1.0` release, the ZAC-79 clean-start correction, and
the ZAC-80 persisted Medplum verification correction.

Post-fix live evidence is retained in:

- `docs/settings-fresh-start-evidence-zac79-20260727.md`, covering the
  credential-free Compose render/start, valid dcm4chee defaults, stable-image
  readiness route, and synthetic clean-start safety scan;
- `docs/settings-medplum-recreation-evidence-zac80-20260727.md`, covering a
  synthetic failed Medplum result across retained-container recreation with
  bounded projections and clean secret-canary scans.

At commit `d882d05`, the ZAC-78 release matrix ran 70 focused tests across its
closure harness, GDT, dcm4chee, AP, OIE, readiness, schema migration, and
persisted settings. All passed; the single Windows directory-symlink capability
test was skipped, while the non-mutation path-escape contract remains covered.
The matrix explicitly confirms:

- built-in OIE and dcm4chee projections plus disabled GDT/AP behavior;
- complete atomic migration ledgers and assembled patient/order, GDT, DICOM,
  and FHIR workflow dependencies after upgrade;
- missing and unwritable GDT paths without unsafe target creation or retained
  probe artifacts;
- unreachable dcm4chee layers, invalid AP AE title rejection, OIE degradation,
  AP partial protocol availability, and independent peer preservation;
- rejection of secret, Authorization, PHI, raw-message, FHIR-body, and upstream
  canaries on API, UI, wrapper, selected-log, and screenshot-OCR surfaces.

The closure pre-flight found the normal `interoperability-lab` project running
and owning its explicit network, port 5000, and retained volumes. No shared
container, network, port, or volume was changed. A second concurrent disposable
stack was therefore skipped under the documented collision policy rather than
mutating the operator environment.

No screenshots exist in the retained ZAC-78, ZAC-79, or ZAC-80 evidence set, so
there were no image artifacts requiring credential inspection. Screenshot OCR
content remains covered by the same synthetic canary gate as other retained
surfaces.
