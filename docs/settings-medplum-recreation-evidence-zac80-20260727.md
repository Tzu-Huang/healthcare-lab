# ZAC-80 Medplum retained-recreation evidence — 2026-07-27

## Tested state

- Branch: `fix/ZAC-80_preserve-degraded-medplum-readiness-across-restart`
- Commit: `ef058f8f797dd62ba0b1a7333c00bafc26cefc4e`
- Local image revision label: `ef058f8f797dd62ba0b1a7333c00bafc26cefc4e`
- Host: Windows, PowerShell, Docker Desktop
- Data: synthetic configuration and credentials only

## Isolation

The verification used resources dedicated to this run:

- container: `zac80-verification-app`
- network: `zac80-verification-net`
- instance volume: `zac80-verification-instance`
- host port: `15080`

The running `interoperability-lab-lab-app-1`, its fixed network, port 5000,
and retained volumes were not stopped, recreated, mounted, or modified.

## Procedure and bounded results

1. Built the tested commit as a local image and started only `lab-app` with
   OIE bootstrap off, the dedicated network, port, and instance volume.
2. Confirmed initial Medplum readiness was `needs-setup` and overall
   `complete` was `false`.
3. Saved an enabled Medplum profile using a synthetic client identity,
   synthetic write-only secret, one-second timeout, and an unreachable
   synthetic endpoint.
4. Save-and-test returned `saved: true` and the following bounded stages:
   - metadata: `failed` / `connection-failure`
   - OAuth: `failed` / `authorization-failure`
   - authenticated read: `skipped` / `oauth-unavailable`
5. Confirmed Medplum readiness was `degraded`, overall `complete` was `false`,
   and the next section remained `medplum`.
6. Removed the first container while retaining the named instance volume,
   then recreated the container from the same image with the same volume.
   The container identity changed from `f58bfd9ab0dd...` to
   `2388c4aa4d38...`.
7. After recreation, Medplum remained `degraded`, overall `complete` remained
   `false`, and the next section remained `medplum`.

## Safety evidence

- Direct inspection of `medplum_verification_state` confirmed the persisted
  row contained only overall state and the bounded stage projection.
- Negative scans confirmed the submitted secret, client identity, endpoint,
  authorization header, FHIR resource markers, and Patient body markers were
  absent from the persisted verification projection and container logs.
- No request payload, credential, token, FHIR body, PHI, or arbitrary upstream
  response was retained in this evidence.

## Cleanup

The dedicated container, named instance volume, three anonymous GDT volumes,
network, and local verification image were removed after capture. Read-only
post-cleanup inspection confirmed no `zac80-verification-*` container, volume,
or network remained and the pre-existing `interoperability-lab-lab-app-1`
continued running on port 5000.
