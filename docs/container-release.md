# Healthcare Lab Container Release

## v1.0.0 verified image matrix

The release Compose defaults identify every third-party image by both its
human-readable tag (when upstream provides one) and its verified repository
digest. Operators can override an image variable deliberately, but doing so
creates a deployment outside the verified v1.0.0 matrix.

| Service | v1.0.0 default |
| --- | --- |
| lab-app | `ghcr.io/tzu-huang/healthcare-lab:1.0.0` |
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
