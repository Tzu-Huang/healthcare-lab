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

## Precise environment-dependent skips

- Fresh full-stack startup and guided browser setup: **skipped** because
  exclusive project, network, and port ownership was not available.
- Live restart and container-recreation persistence: **skipped** for the same
  ownership reason.
- Live legacy-volume upgrade and second restart: **skipped** because it requires
  an exclusively owned disposable project and volumes.
- External failure matrix and screenshots: **skipped** because the required
  isolated services were not started.

These scenarios are not reported as passed. Run
`docs/settings-release-verification-runbook.md` in an exclusive lab window with
a reviewed unique-network override before ZAC-78 closure.

## Product defects

No new product defect was established by the automated checks. The skipped live
scenarios remain required evidence rather than defect findings.
