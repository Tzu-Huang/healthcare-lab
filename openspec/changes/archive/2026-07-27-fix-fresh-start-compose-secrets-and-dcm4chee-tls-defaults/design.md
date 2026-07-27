## Context

ZAC-78 live verification found three failures in the supported first-run path. Compose top-level secrets use environment-backed sources that are mandatory at render time, although application integration credentials are intentionally configured later in Settings. After empty values are supplied manually, the local dcm4chee bootstrap still fails because Compose emits `tlsEnabled=false` with `tlsVerify=true`. Finally, the default `lab-app:1.0.1` image predates the readiness route described by the current handbook and tested by current source.

The fix crosses deployment configuration, typed-settings bootstrap, contract tests, and release-version selection. It must preserve secret redaction, one-time bootstrap precedence, immutable stable tags, and the distinction between deployment credentials and application Settings secrets.

## Goals / Non-Goals

**Goals:**

- Make the supported Compose and wrapper entry points render and start from a clean checkout without a repository `.env` or optional application integration credentials.
- Seed a valid built-in local dcm4chee profile.
- Ensure the default selected `lab-app` image implements the guided readiness contract.
- Detect all three regressions with deterministic automated contracts and a bounded disposable smoke check.

**Non-Goals:**

- Persisting placeholder credentials or weakening write-only secret handling.
- Changing the Settings API schema, readiness vocabulary, or one-time bootstrap authority model.
- Solving ZAC-80 operational-readiness persistence.
- Re-tagging immutable published images or performing a release as part of product-code implementation.

## Decisions

### Treat absent application credentials as optional bootstrap input

The release Compose contract will represent omitted application credentials in a way that allows Compose rendering and startup while delivering no credential value to typed settings. The application will continue interpreting absence or empty bootstrap input as `configured: false`.

This is preferred over requiring a generated `.env`, because the documented path promises no prerequisite edit, and over dummy defaults, because placeholder credentials blur configured state and can leak into diagnostics. The exact Compose mechanism will be selected only if it works on the documented Docker Compose baseline and does not print values during rendering or wrapper failures.

### Align deployment defaults with the typed dcm4chee invariant

The local profile keeps TLS disabled and defaults TLS verification to false. The validator remains strict: an explicit `tlsVerify=true` while TLS is disabled is still rejected.

Weakening validation was rejected because it would allow contradictory persisted profiles and obscure operator mistakes. Enabling TLS by default was rejected because the bundled local archive endpoints are plain HTTP/DIMSE.

### Advance the default image through the normal release contract

Compose and `.env.example` will reference a semantic version that is built from code containing `/api/settings/readiness`; tests will assert the selected version and exercise the route from the corresponding image during release verification. Existing immutable tags remain untouched.

Pointing the default at mutable `edge` was rejected because it would break reproducible release composition. Repointing `1.0.1` was rejected because stable tags are immutable.

### Verify at configuration, application, and disposable-runtime layers

Static Compose tests will render without optional variables and inspect defaults without printing secret values. Application tests will bootstrap a fresh database from the resolved environment and assert secret-safe readiness. A disposable container check will confirm that the selected image becomes healthy and exposes the readiness route.

Unit-only coverage was rejected because ZAC-79 was caused by disagreement between individually valid layers.

## Risks / Trade-offs

- [Compose secret behavior varies by implementation/version] → Pin the supported Compose baseline and exercise the no-variable render/start contract in CI or record a precise environment-dependent runtime skip.
- [An empty mounted secret could be mistaken for configured] → Assert the public typed profile reports `configured: false` and readiness remains `needs-setup`.
- [Changing the image default before publication creates an unavailable deployment] → Merge product fixes first, publish and verify the semantic image, then update the release asset/default in the coordinated release commit.
- [A disposable smoke run could collide with an active lab] → Use unique project/network names, alternate ports, fresh volumes, and stop without mutation on ownership conflicts.

## Migration Plan

1. Correct Compose secret/default contracts and add source-level regression tests.
2. Verify clean application bootstrap and readiness using the locally built image.
3. Merge through the normal quality gate and publish a new immutable semantic-version image.
4. Update the default image reference and `.env.example`, then verify the pulled image in a disposable environment.
5. Re-run the ZAC-78 fresh-install matrix.

Rollback selects the previous immutable application tag and prior release deployment files. No database migration or persisted-profile rewrite is required.

## Open Questions

- What minimum Docker Compose version is the documented compatibility floor for optional environment-backed secret handling?
- Which semantic version will carry the corrected image after the code is merged?
- Should the pulled-image smoke check run on every main publication or only stable release publication?
