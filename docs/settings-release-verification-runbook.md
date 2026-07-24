# Settings release verification runbook

This runbook is the disposable live gate for ZAC-78. It never reuses, stops,
restarts, removes, or renames an existing Healthcare Lab project.

## Ownership pre-flight

Before starting a live matrix, record:

```powershell
git rev-parse HEAD
docker compose ls
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
docker network ls
docker volume ls
```

The verifier must have exclusive ownership of:

- a unique Compose project and network name;
- fresh named volumes for every declared service;
- a new bounded GDT host directory containing only synthetic files;
- host ports 5000, 6600, 6661, 8080, 8443, 8103, 3000, 8082, 11112,
  and 2575, or a reviewed isolated override for every publication;
- synthetic Medplum, OIE, GDT, dcm4chee, and AP identities.

Stop without mutation when any required project name, explicit network name,
volume, directory, or port is already owned. Do not use `down`, volume removal,
recursive deletion, or service restart to obtain ownership. Record the exact
collision as an environment-dependent skip.

The current Compose file declares the explicit network name
`interoperability-lab`. A parallel disposable run therefore requires a reviewed
Compose override that gives the network a unique name in addition to unique
ports and project-scoped volumes. `docker compose -p` alone is not sufficient.

## Fresh-install matrix

1. Confirm the disposable project has no `.env`, application database, named
   volumes, or pre-existing GDT directory.
2. Start through the supported wrapper-equivalent Compose contract and wait for
   the application endpoint.
3. Record initial readiness, built-in OIE/dcm4chee defaults, and the next
   required Settings action.
4. Create a synthetic Medplum ClientApplication, save its ID and write-only
   secret in Settings, and record metadata, OAuth, and authenticated-read
   stages without values.
5. Configure or explicitly disable GDT and AP. Record completion.
6. Restart the application, then recreate its container while retaining
   storage. Confirm completion and secret configured states persist.

## Upgrade matrix

1. Start from the canonical v8 fixture described by
   `tests/zac78_verification.py` and representative eligible legacy variables.
2. Upgrade without deleting volumes. Confirm all migrations, bootstrap audit
   count, secret configured states, and representative workflows.
3. Change a migrated field in Settings.
4. Start again with the old conflicting environment value. Confirm the
   persisted operator value wins and no second bootstrap occurs.

## Failure and evidence matrix

Exercise wrong Medplum secret, unreachable FHIR URL, missing GDT directory,
unwritable bridge, unreachable dcm4chee, invalid AE title, AP/OIE drift, and
partial service availability. Each retained result must identify a bounded
layer, category, and recovery action.

Pass all retained text and structured evidence through
`tests.zac78_verification.assert_bounded_evidence`. Screenshots must contain
synthetic data only and must be inspected for credentials before commit. Never
retain raw messages, FHIR bodies, Authorization values, arbitrary upstream
responses, or real host paths.

