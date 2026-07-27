## Why

The documented zero-edit Docker startup path fails before guided setup when optional secret environment variables are absent, and current dcm4chee Compose defaults form an invalid typed profile. The default published application image also predates the readiness API required by the operator handbook, so release assets do not deliver the first-run behavior they promise.

## What Changes

- Make optional application integration credentials safe to omit during Compose interpolation and container startup without exposing or inventing secret values.
- Align built-in dcm4chee TLS defaults so the local non-TLS profile passes typed validation.
- Update the supported default `lab-app` image contract to a release that contains the guided Settings readiness API.
- Add Compose, wrapper, startup, and image-contract verification for a clean checkout with no `.env` or application credentials.
- Preserve advanced deployment overrides and the existing write-only Settings secret model.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-container-release`: Require the release Compose and wrapper path to start without optional secret variables and to select an application image that implements the documented readiness API.
- `healthcare-lab-dcm4chee-connection-profile`: Require the built-in local non-TLS dcm4chee security defaults to be internally valid.
- `healthcare-lab-typed-integration-settings`: Clarify that absent optional secret bootstrap inputs produce an unconfigured, secret-safe profile instead of a deployment or startup failure.

## Impact

- `deploy/docker-compose.yml`, `.env.example`, and the supported PowerShell wrapper contract.
- dcm4chee typed bootstrap/default configuration and its validation tests.
- Container release/version selection and publication/release coordination.
- Compose rendering, clean-start, readiness-route, and regression test suites.
