# Healthcare Lab Container Release

## Image tags

| Tag | Meaning |
| --- | --- |
| `1.0.0` | Immutable v1.0.0 application image |
| `1.0` / `1` | Moving aliases for the newest stable compatible release |
| `latest` | Newest stable published GitHub Release |
| `edge` | Newest verified `main` build; not a stable release |
| `sha-<commit>` | Traceable image for one source revision |

The public registry name is `ghcr.io/tzu-huang/healthcare-lab`. Pull requests
build and test without publishing. A failed `main` or release verification does
not update tags, and later `main` pushes never repoint `1.0.0`.

## v1.0.0 verified image matrix

The release Compose defaults identify every third-party image by both its
human-readable tag (when upstream provides one) and its verified repository
digest. Operators can override an image variable deliberately, but doing so
creates a deployment outside the verified v1.0.0 matrix.

| Service | v1.0.0 default |
| --- | --- |
| lab-app | `ghcr.io/tzu-huang/healthcare-lab:1.0.1` |
| OIE | `nextgenhealthcare/connect:4.5.2@sha256:4afa295cfe7c5ffd596efee69594157fea87202e33d66bb4a98a52db4598f836` |
| Medplum server | `medplum/medplum-server@sha256:4d2c8e926fe536176a88a7e24555f97f92226e39f171bd0b5f0c7f667d0bf9f0` |
| Medplum app | `medplum/medplum-app@sha256:79f162f7124a8932c2a76fc2c7c72df4b080d5fef43496c64bc34ad68e65ca56` |
| Medplum PostgreSQL | `postgres:16-alpine@sha256:e013e867e712fec275706a6c51c966f0bb0c93cfa8f51000f85a15f9865a28cb` |
| Medplum Redis | `redis:7-alpine@sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` |
| dcm4chee database | `dcm4che/postgres-dcm4chee:16.13-35@sha256:1fced918fa507a133ec98db6ad2af92be2db0399c4061d5d59a4405ac445cd70` |
| dcm4chee LDAP | `dcm4che/slapd-dcm4chee:2.6.13-35.0@sha256:ca45eaf70d92c4008612ab345a566e06c13b553b079ccf6c652ceda4c9a98b98` |
| dcm4chee archive | `dcm4che/dcm4chee-arc-psql:5.35.0@sha256:20a195c0c53336e1d0c7bdc30536d46611a939f0a2e25dec3318c8d99d7fba29` |

## Persistence contract

The `lab-app-instance` named volume owns `/app/instance`, including the SQLite
database. The operator-selected GDT bridge folder is mounted at
`/data/gdt-bridge`. Neither location is part of the application image.

Container replacement was verified by creating the SQLite database and a
marker in the named volume, removing the first container, starting a second
container from the same image and volume, and reading both files from the
replacement container.

Before an upgrade, stop `lab-app` and copy `/app/instance` plus the configured
GDT bridge host folder to operator-controlled backup storage. Do not rely on an
image rollback to reverse a database migration: restore the matching instance
backup when the older application schema is not forward-compatible.

## Backup, upgrade, and rollback

Create a backup directory, stop only `lab-app`, and copy its instance data plus
the host-side GDT bridge folder:

```powershell
New-Item -ItemType Directory -Force backup\v1.0.0
.\deploy\lab.ps1 stop lab-app
docker compose -f deploy\docker-compose.yml cp lab-app:/app/instance backup\v1.0.0\instance
Copy-Item -Recurse instance\gdt-bridge backup\v1.0.0\gdt-bridge
```

To upgrade, optionally set `LAB_APP_IMAGE` in an Advanced `.env` to the target
immutable tag, pull it, and recreate only `lab-app`:

```powershell
docker compose -f deploy\docker-compose.yml pull lab-app
.\deploy\lab.ps1 restart lab-app
Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing
```

To roll back, stop `lab-app`, restore the backup when schema compatibility
requires it, select the previous immutable `LAB_APP_IMAGE`, and recreate the
container. When an Advanced `.env` exists, keep it and all deployment secrets
outside backup artifacts intended for publication. Application Settings remain
in the separately backed-up instance database.

## Supported boundary

v1.0.0 supports Docker Compose with `linux/amd64` on a trusted local machine or
internal lab. It does not claim public-Internet, regulated production-healthcare,
ARM, or multi-replica support. HTTPS termination, application authentication,
and public ingress are outside this release.

`lab-app` retains the `/var/run/docker.sock` mount for Dashboard container
inspection and control. A process with that access can administer the host
Docker daemon. Do not run untrusted images, expose the application directly to
untrusted networks, or mount production patient data.
