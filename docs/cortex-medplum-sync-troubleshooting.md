# Cortex Note: Medplum Sync Connection Refused

Date: 2026-07-08

## Summary

Healthcare Lab Medplum sync can fail after cloning the repo to a new machine
even when Docker containers are running and Medplum smoke checks report
healthy.

Observed error:

```text
Medplum request failed: [Errno 111] Connection refused
```

## Root Cause

The Medplum sync path reads the FHIR API URL from the Lab Server inventory
record for `Medplum`, not from `.env` values such as `MEDPLUM_PUBLIC_BASE_URL`.

On a Docker Compose runtime, the persisted Lab Server value may still be:

```text
http://127.0.0.1:8103/fhir/R4
```

From inside the `lab-app` container, `127.0.0.1` points to the `lab-app`
container itself, not to the Medplum container. Because `lab-app` is not
listening on port `8103`, sync fails with connection refused.

## Fix

Set the Lab Server Medplum record to use the Docker Compose service name:

```text
host    = medplum
baseUrl = http://medplum:8103/fhir/R4
```

PowerShell one-liner:

```powershell
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:5000/api/lab/servers/2" -ContentType "application/json" -Body '{"name":"Medplum","serverType":"FHIR Server","description":"FHIR R4 API server","host":"medplum","port":8103,"baseUrl":"http://medplum:8103/fhir/R4","protocol":"FHIR","enabled":true}'
```

Confirm the stored value:

```powershell
(Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/lab/servers").items | Where-Object {$_.name -eq "Medplum"} | Select-Object name,host,baseUrl
```

Expected result:

```text
name    host     baseUrl
----    ----     -------
Medplum medplum  http://medplum:8103/fhir/R4
```

Optional container-to-container connectivity check:

```powershell
docker-compose --env-file .env -f deploy\docker-compose.yml exec lab-app python -c "import urllib.request; print(urllib.request.urlopen('http://medplum:8103/fhir/R4/metadata').status)"
```

Expected output:

```text
200
```

## Notes

- `MEDPLUM_CLIENT_ID` and `MEDPLUM_CLIENT_SECRET` should stay in `.env` or the
  operator environment only.
- Do not copy OAuth client secrets, access tokens, refresh tokens, or PHI into
  Cortex.
- A Medplum smoke check can report healthy while sync still fails because smoke
  checks use Docker service URLs internally, while sync uses the persisted Lab
  Server `baseUrl`.
